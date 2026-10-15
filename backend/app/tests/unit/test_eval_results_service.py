"""Unit tests for `EvalResultsService` — persistence of production-evaluation runs and results.

`db.execute` is mocked, matching this codebase's `tests/unit/` convention. Constraint
behaviour is covered by `integration/test_eval_run_models.py`.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.eval_results import EvalRun
from app.services.eval_results_service import (
    CheckOutcome,
    EvalResultsService,
    EvalResultsValidationError,
    RunCounts,
)

NOW = datetime.now(UTC)
RUN_ID = uuid.uuid4()
EVENT_ID = uuid.uuid4()
SCHOOL_ID = uuid.uuid4()
WINDOW_START, WINDOW_END = NOW - timedelta(days=7), NOW
RUN_ARGS: dict[str, Any] = {
    "task": "question_generation",
    "window_start": WINDOW_START,
    "window_end": WINDOW_END,
    "seed": "s",
    "trigger": "manual",
}


def _result(**attrs: Any) -> MagicMock:
    result = MagicMock()
    for name, value in attrs.items():
        getattr(result, name).return_value = value
    return result


def _db(*results: MagicMock) -> AsyncMock:
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = list(results)
    return db


def _run(**overrides: Any) -> EvalRun:
    values: dict[str, Any] = {"id": RUN_ID, **RUN_ARGS, "status": "pending"}
    values.update(overrides)
    return EvalRun(**values)


class TestCreateRun:
    @pytest.mark.asyncio
    async def test_create_run_when_new_then_inserts_and_reports_created(self) -> None:
        run = _run()
        db = _db(_result(scalar_one_or_none=RUN_ID), _result(scalar_one=run))

        got, created = await EvalResultsService(db).create_run(**RUN_ARGS)

        assert created is True and got is run
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_run_when_task_window_seed_exists_then_returns_existing_not_created(self) -> None:
        run = _run(status="completed")
        db = _db(_result(scalar_one_or_none=None), _result(scalar_one=run))

        got, created = await EvalResultsService(db).create_run(**RUN_ARGS)

        assert created is False and got is run

    @pytest.mark.asyncio
    async def test_create_run_when_trigger_invalid_then_raises_validation_error(self) -> None:
        db = _db()
        with pytest.raises(EvalResultsValidationError):
            await EvalResultsService(db).create_run(**{**RUN_ARGS, "trigger": "cron"})
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_run_when_window_inverted_then_raises_validation_error(self) -> None:
        with pytest.raises(EvalResultsValidationError):
            await EvalResultsService(_db()).create_run(
                **{**RUN_ARGS, "window_start": WINDOW_END, "window_end": WINDOW_START}
            )

    @pytest.mark.asyncio
    async def test_create_run_when_seed_blank_then_raises_validation_error(self) -> None:
        with pytest.raises(EvalResultsValidationError):
            await EvalResultsService(_db()).create_run(**{**RUN_ARGS, "seed": " "})


class TestRecordResults:
    @pytest.mark.asyncio
    async def test_record_results_when_event_has_school_then_school_id_copied_to_every_row(self) -> None:
        db = _db(_result(one_or_none=(SCHOOL_ID,)), _result(all=[1, 2]))
        outcomes = [
            CheckOutcome("a", "deterministic", True),
            CheckOutcome("b", "judge", None, rubric_hash="h", rubric_status="CALIBRATED"),
        ]

        written = await EvalResultsService(db).record_results(RUN_ID, EVENT_ID, outcomes)

        assert written == 2
        params = db.execute.await_args_list[1].args[0].compile().params
        assert [params[f"school_id_m{i}"] for i in range(2)] == [SCHOOL_ID, SCHOOL_ID]
        assert [params[f"indeterminate_m{i}"] for i in range(2)] == [False, True]
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_results_when_event_is_platform_level_then_school_id_null(self) -> None:
        db = _db(_result(one_or_none=(None,)), _result(scalar_one_or_none=RUN_ID))

        await EvalResultsService(db).record_results(RUN_ID, EVENT_ID, [CheckOutcome("a", "deterministic", False)])

        assert db.execute.await_args_list[1].args[0].compile().params["school_id_m0"] is None

    @pytest.mark.asyncio
    async def test_record_results_when_event_missing_then_raises_lookup_error(self) -> None:
        db = _db(_result(one_or_none=None))
        with pytest.raises(LookupError):
            await EvalResultsService(db).record_results(RUN_ID, EVENT_ID, [CheckOutcome("a", "deterministic", True)])

    @pytest.mark.asyncio
    async def test_record_results_when_no_outcomes_then_writes_nothing(self) -> None:
        db = _db()
        assert await EvalResultsService(db).record_results(RUN_ID, EVENT_ID, []) == 0
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_results_when_judge_outcome_lacks_rubric_then_raises_validation_error(self) -> None:
        with pytest.raises(EvalResultsValidationError):
            await EvalResultsService(_db()).record_results(RUN_ID, EVENT_ID, [CheckOutcome("a", "judge", True)])

    @pytest.mark.asyncio
    async def test_record_results_when_deterministic_outcome_has_rubric_then_raises_validation_error(self) -> None:
        bad = CheckOutcome("a", "deterministic", True, rubric_hash="h", rubric_status="CALIBRATED")
        with pytest.raises(EvalResultsValidationError):
            await EvalResultsService(_db()).record_results(RUN_ID, EVENT_ID, [bad])

    @pytest.mark.asyncio
    async def test_record_results_when_rubric_status_untrusted_then_raises_validation_error(self) -> None:
        bad = CheckOutcome("a", "judge", True, rubric_hash="h", rubric_status="STALE")
        with pytest.raises(EvalResultsValidationError):
            await EvalResultsService(_db()).record_results(RUN_ID, EVENT_ID, [bad])

    @pytest.mark.asyncio
    async def test_record_results_when_kind_unknown_then_raises_validation_error(self) -> None:
        with pytest.raises(EvalResultsValidationError):
            await EvalResultsService(_db()).record_results(RUN_ID, EVENT_ID, [CheckOutcome("a", "human", True)])

    @pytest.mark.asyncio
    async def test_record_results_when_check_name_blank_then_raises_validation_error(self) -> None:
        with pytest.raises(EvalResultsValidationError):
            await EvalResultsService(_db()).record_results(RUN_ID, EVENT_ID, [CheckOutcome(" ", "deterministic", True)])


class TestRunLifecycle:
    @pytest.mark.asyncio
    async def test_mark_started_when_run_pending_then_updates_and_commits(self) -> None:
        db = _db(_result(scalar_one_or_none=RUN_ID))
        await EvalResultsService(db).mark_started(RUN_ID, judge_model="test/judge")
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mark_started_when_run_not_pending_then_raises_lookup_error(self) -> None:
        with pytest.raises(LookupError):
            await EvalResultsService(_db(_result(scalar_one_or_none=None))).mark_started(
                RUN_ID, judge_model="test/judge"
            )

    @pytest.mark.asyncio
    async def test_finish_run_when_status_terminal_then_updates_and_commits(self) -> None:
        db = _db(_result(scalar_one_or_none=RUN_ID))
        await EvalResultsService(db).finish_run(
            RUN_ID,
            status="budget_exhausted",
            counts=RunCounts(sampled=5, evaluated=4, skipped_scrub_failed=1),
            spend_usd=Decimal("0.5"),
        )
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_finish_run_when_status_not_terminal_then_raises_validation_error(self) -> None:
        with pytest.raises(EvalResultsValidationError):
            await EvalResultsService(_db()).finish_run(
                RUN_ID, status="running", counts=RunCounts(), spend_usd=Decimal("0")
            )

    @pytest.mark.asyncio
    async def test_finish_run_when_run_missing_then_raises_lookup_error(self) -> None:
        with pytest.raises(LookupError):
            await EvalResultsService(_db(_result(scalar_one_or_none=None))).finish_run(
                RUN_ID, status="failed", counts=RunCounts(), spend_usd=Decimal("0"), error_type="RuntimeError"
            )

    @pytest.mark.asyncio
    async def test_get_run_when_missing_then_returns_none(self) -> None:
        assert await EvalResultsService(_db(_result(scalar_one_or_none=None))).get_run(RUN_ID) is None
