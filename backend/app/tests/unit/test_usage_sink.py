"""Unit tests for the LLM usage sink and its attribution context.

One invariant dominates this file: **recording usage must never fail an LLM call.** A student
waiting on an explanation does not get an error because a telemetry insert deadlocked. Every
failure path below asserts that no exception escapes.

The second theme is contextvar hygiene. A leaked `llm_component` would misattribute every
subsequent call in the same worker process, and because the value would still look plausible,
the resulting cost report would be wrong without appearing wrong.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.ai.usage_context import (
    current_component,
    current_correlation_id,
    current_run_id,
    current_school_id,
    llm_component,
)
from app.ai.usage_sink import record_usage, usage_kwargs_from_response


def _session_ctx(session: MagicMock) -> MagicMock:
    """Build an async-context-manager stand-in for CeleryAsyncSessionLocal()."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.mark.asyncio
class TestRecordUsageNeverRaises:
    async def test_record_usage_when_tracking_disabled_then_no_database_call_attempted(self) -> None:
        with (
            patch("app.ai.usage_sink.settings.llm_usage_tracking_enabled", False),
            patch("app.ai.usage_sink.CeleryAsyncSessionLocal") as maker,
        ):
            await record_usage(task="t", model="m", latency_ms=10)
        maker.assert_not_called()

    async def test_record_usage_when_insert_fails_then_logs_warning_and_does_not_raise(self) -> None:
        session = MagicMock()
        session.add = MagicMock()
        session.commit = AsyncMock(side_effect=RuntimeError("deadlock detected"))

        with (
            patch("app.ai.usage_sink.settings.llm_usage_tracking_enabled", True),
            patch("app.ai.usage_sink.CeleryAsyncSessionLocal", return_value=_session_ctx(session)),
            patch("app.ai.usage_sink.logger") as log,
        ):
            await record_usage(task="t", model="m", latency_ms=10)

        log.warning.assert_called_once()
        assert log.warning.call_args.args[0] == "llm_usage_record_failed"

    async def test_record_usage_when_session_unavailable_then_does_not_raise(self) -> None:
        with (
            patch("app.ai.usage_sink.settings.llm_usage_tracking_enabled", True),
            patch("app.ai.usage_sink.CeleryAsyncSessionLocal", side_effect=RuntimeError("no DATABASE_URL")),
        ):
            await record_usage(task="t", model="m", latency_ms=10)

    async def test_record_usage_when_succeeds_then_row_contains_task_model_and_latency(self) -> None:
        session = MagicMock()
        session.add = MagicMock()
        session.commit = AsyncMock()

        with (
            patch("app.ai.usage_sink.settings.llm_usage_tracking_enabled", True),
            patch("app.ai.usage_sink.CeleryAsyncSessionLocal", return_value=_session_ctx(session)),
        ):
            await record_usage(
                task="question_generation",
                model="test/model-a",
                latency_ms=4127,
                prompt_tokens=892,
                completion_tokens=1455,
                total_tokens=2347,
                estimated_cost_usd=Decimal("0.00187"),
            )

        row = session.add.call_args.args[0]
        assert row.task == "question_generation"
        assert row.model == "test/model-a"
        assert row.latency_ms == 4127
        assert row.estimated_cost_usd == Decimal("0.00187")
        assert row.succeeded is True

    async def test_record_usage_when_latency_negative_then_clamped_to_zero(self) -> None:
        # A CHECK constraint rejects negatives; clamping keeps a clock anomaly from
        # discarding the row entirely.
        session = MagicMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        with (
            patch("app.ai.usage_sink.settings.llm_usage_tracking_enabled", True),
            patch("app.ai.usage_sink.CeleryAsyncSessionLocal", return_value=_session_ctx(session)),
        ):
            await record_usage(task="t", model="m", latency_ms=-5)
        assert session.add.call_args.args[0].latency_ms == 0

    async def test_record_usage_when_failure_recorded_then_error_type_persisted(self) -> None:
        session = MagicMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        with (
            patch("app.ai.usage_sink.settings.llm_usage_tracking_enabled", True),
            patch("app.ai.usage_sink.CeleryAsyncSessionLocal", return_value=_session_ctx(session)),
        ):
            await record_usage(
                task="t", model="m", latency_ms=10, succeeded=False, error_type="RateLimitError", error_detail="429"
            )
        row = session.add.call_args.args[0]
        assert row.succeeded is False
        assert row.error_type == "RateLimitError"

    async def test_record_usage_when_error_detail_very_long_then_truncated(self) -> None:
        session = MagicMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        with (
            patch("app.ai.usage_sink.settings.llm_usage_tracking_enabled", True),
            patch("app.ai.usage_sink.CeleryAsyncSessionLocal", return_value=_session_ctx(session)),
        ):
            await record_usage(
                task="t", model="m", latency_ms=10, succeeded=False, error_type="E", error_detail="x" * 10000
            )
        assert len(session.add.call_args.args[0].error_detail) == 2000


@pytest.mark.asyncio
class TestAttribution:
    async def test_record_usage_when_component_bound_in_context_then_persisted(self) -> None:
        session = MagicMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        with (
            patch("app.ai.usage_sink.settings.llm_usage_tracking_enabled", True),
            patch("app.ai.usage_sink.CeleryAsyncSessionLocal", return_value=_session_ctx(session)),
            llm_component("script:generate_gap_questions", run_id="run-42"),
        ):
            await record_usage(task="t", model="m", latency_ms=10)

        row = session.add.call_args.args[0]
        assert row.component == "script:generate_gap_questions"
        assert row.run_id == "run-42"

    async def test_record_usage_when_no_component_bound_then_persists_null_not_empty_string(self) -> None:
        # NULL and "" would split the same bucket in the report; only NULL is meaningful.
        session = MagicMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        with (
            patch("app.ai.usage_sink.settings.llm_usage_tracking_enabled", True),
            patch("app.ai.usage_sink.CeleryAsyncSessionLocal", return_value=_session_ctx(session)),
        ):
            await record_usage(task="t", model="m", latency_ms=10)
        assert session.add.call_args.args[0].component is None


class TestLlmComponentContext:
    def test_llm_component_when_entered_then_binds_component_name(self) -> None:
        with llm_component("api:subtopic_content"):
            assert current_component() == "api:subtopic_content"

    def test_llm_component_when_exited_then_unbinds_component_name(self) -> None:
        with llm_component("api:subtopic_content"):
            pass
        assert current_component() is None

    def test_llm_component_when_body_raises_then_still_unbinds(self) -> None:
        # A leaked contextvar misattributes every later call in this worker process.
        with pytest.raises(ValueError, match="boom"), llm_component("celery:x"):
            raise ValueError("boom")
        assert current_component() is None

    def test_llm_component_when_nested_then_inner_wins_and_outer_restored(self) -> None:
        with llm_component("outer"):
            with llm_component("inner"):
                assert current_component() == "inner"
            assert current_component() == "outer"
        assert current_component() is None

    def test_llm_component_when_run_id_given_then_available(self) -> None:
        with llm_component("script:x", run_id="run-1"):
            assert current_run_id() == "run-1"
        assert current_run_id() is None

    def test_llm_component_when_no_run_id_given_then_outer_run_id_preserved(self) -> None:
        with llm_component("script:x", run_id="run-1"), llm_component("script:y"):
            # The inner block names no run, so it belongs to the run already in progress.
            assert current_run_id() == "run-1"

    def test_current_correlation_id_when_nothing_bound_then_none(self) -> None:
        assert current_correlation_id() is None


class TestUsageKwargsFromResponse:
    def test_usage_kwargs_when_response_has_usage_then_extracted(self) -> None:
        response = MagicMock()
        response.usage.prompt_tokens = 10
        response.usage.completion_tokens = 20
        response.usage.total_tokens = 30
        assert usage_kwargs_from_response(response) == {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        }

    def test_usage_kwargs_when_response_has_no_usage_then_all_none(self) -> None:
        response = MagicMock(spec=[])
        assert usage_kwargs_from_response(response) == {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
        }


class TestCurrentSchoolId:
    """school_id rides the same contextvar channel as component.

    It is read on the telemetry path, so a malformed claim in a token must degrade to None
    rather than raise — an unparseable school id cannot be allowed to fail an LLM call.
    """

    def test_current_school_id_when_nothing_bound_then_none(self) -> None:
        assert current_school_id() is None

    def test_current_school_id_when_uuid_string_bound_then_parsed(self) -> None:
        value = uuid.uuid4()
        try:
            bind_contextvars(school_id=str(value))
            assert current_school_id() == value
        finally:
            clear_contextvars()

    def test_current_school_id_when_uuid_object_bound_then_returned(self) -> None:
        value = uuid.uuid4()
        try:
            bind_contextvars(school_id=value)
            assert current_school_id() == value
        finally:
            clear_contextvars()

    def test_current_school_id_when_unparseable_then_none_not_raised(self) -> None:
        try:
            bind_contextvars(school_id="not-a-uuid")
            assert current_school_id() is None
        finally:
            clear_contextvars()

    def test_current_school_id_when_none_bound_then_none(self) -> None:
        # An unauthenticated request binds school_id=None explicitly.
        try:
            bind_contextvars(school_id=None)
            assert current_school_id() is None
        finally:
            clear_contextvars()
