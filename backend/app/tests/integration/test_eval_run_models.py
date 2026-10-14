"""Integration tests for the production-evaluation result tables (MLH-T18 slice 2).

These need a real database: what is under test is the schema's own guarantees (unique key,
CHECK constraints, ON DELETE behaviour), none of which a mock can exercise.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import delete, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.eval_results import EvalResult, EvalRun
from app.models.llm_usage import LlmUsageEvent
from app.models.platform_settings import PlatformSettings
from app.models.school import School
from app.models.user import User

NOW = datetime.now(UTC)


def _run(**overrides: Any) -> EvalRun:
    values: dict[str, Any] = {
        "task": "question_generation",
        "window_start": NOW - timedelta(days=7),
        "window_end": NOW,
        "seed": "seed-1",
        "trigger": "manual",
    }
    values.update(overrides)
    return EvalRun(**values)


def _event(**overrides: Any) -> LlmUsageEvent:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "task": "question_generation",
        "model": "test/model-a",
        "latency_ms": 10,
        "created_at": NOW,
        "school_id": None,
    }
    values.update(overrides)
    return LlmUsageEvent(**values)


def _result(run_id: uuid.UUID, event_id: uuid.UUID | None, **overrides: Any) -> EvalResult:
    values: dict[str, Any] = {
        "run_id": run_id,
        "usage_event_id": event_id,
        "school_id": None,
        "check_name": "has_four_options",
        "kind": "deterministic",
        "passed": True,
        "indeterminate": False,
    }
    values.update(overrides)
    return EvalResult(**values)


async def _persisted_run(db: AsyncSession, **overrides: Any) -> EvalRun:
    run = _run(**overrides)
    db.add(run)
    await db.flush()
    return run


@pytest.mark.asyncio
class TestEvalRun:
    async def test_eval_run_when_created_then_defaults_status_pending_and_counts_zero(
        self, db_session: AsyncSession
    ) -> None:
        run = await _persisted_run(db_session)
        await db_session.refresh(run)

        assert run.status == "pending"
        assert run.include_indicative is False
        assert (run.sampled_count, run.evaluated_count) == (0, 0)
        assert (run.skipped_not_independent_count, run.skipped_scrub_failed_count) == (0, 0)
        assert run.skipped_unsupported_count == 0
        assert run.spend_usd == Decimal("0")
        assert run.started_at is None and run.completed_at is None
        assert run.created_at is not None

    async def test_eval_run_when_same_task_window_seed_inserted_twice_then_unique_violation(
        self, db_session: AsyncSession
    ) -> None:
        await _persisted_run(db_session)
        db_session.add(_run())
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_eval_run_when_seed_differs_then_both_persist(self, db_session: AsyncSession) -> None:
        await _persisted_run(db_session)
        await _persisted_run(db_session, seed="seed-2")
        rows = (await db_session.execute(select(EvalRun))).scalars().all()
        assert len(rows) == 2

    @pytest.mark.parametrize(
        "overrides",
        [
            {"status": "bogus"},
            {"trigger": "bogus"},
            {"seed": "  "},
            {"sampled_count": -1},
            {"spend_usd": Decimal("-0.01")},
            {"window_end": NOW - timedelta(days=8)},
        ],
    )
    async def test_eval_run_when_value_breaks_constraint_then_integrity_error(
        self, db_session: AsyncSession, overrides: dict[str, Any]
    ) -> None:
        db_session.add(_run(**overrides))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_eval_run_when_requesting_user_deleted_then_run_kept_with_null_requester(
        self, db_session: AsyncSession, kaihle_admin: User
    ) -> None:
        run = await _persisted_run(db_session, requested_by=kaihle_admin.id)
        await db_session.execute(delete(User).where(User.id == kaihle_admin.id))
        await db_session.refresh(run)
        assert run.requested_by is None

    async def test_eval_runs_and_platform_settings_when_inspected_then_have_no_school_id_column(
        self, db_session: AsyncSession
    ) -> None:
        # Documents the deliberate CONSTITUTION Rule 2 deviation (MLH-T18 D13).
        assert "school_id" not in {c.name for c in inspect(EvalRun).columns}
        assert "school_id" not in {c.name for c in inspect(PlatformSettings).columns}


@pytest.mark.asyncio
class TestEvalResult:
    async def test_eval_result_when_created_then_has_no_text_columns(self, db_session: AsyncSession) -> None:
        # Guards D9: results hold metrics and ids only. If this fails, someone added a column;
        # it must be justified against the "never a copy of the text" decision, not just edited here.
        assert {c.name for c in inspect(EvalResult).columns} == {
            "id",
            "run_id",
            "usage_event_id",
            "school_id",
            "check_name",
            "kind",
            "passed",
            "indeterminate",
            "rubric_hash",
            "rubric_status",
            "created_at",
        }

    async def test_eval_result_when_run_deleted_then_cascades(self, db_session: AsyncSession) -> None:
        run = await _persisted_run(db_session)
        event = _event()
        db_session.add(event)
        await db_session.flush()
        db_session.add(_result(run.id, event.id))
        await db_session.flush()

        await db_session.delete(run)
        await db_session.flush()

        remaining = (await db_session.execute(select(EvalResult))).scalars().all()
        assert remaining == []

    async def test_eval_result_when_usage_event_deleted_then_result_kept_with_null_event_id(
        self, db_session: AsyncSession
    ) -> None:
        # SET NULL: retention may purge llm_usage_events; the pass/fail metric must outlive the text.
        run = await _persisted_run(db_session)
        event = _event()
        db_session.add(event)
        await db_session.flush()
        result = _result(run.id, event.id)
        db_session.add(result)
        await db_session.flush()

        await db_session.execute(delete(LlmUsageEvent).where(LlmUsageEvent.id == event.id))
        await db_session.refresh(result)

        assert result.usage_event_id is None
        assert result.passed is True

    @pytest.mark.parametrize("name", ["", "   "])
    async def test_eval_result_when_check_name_blank_then_integrity_error(
        self, db_session: AsyncSession, name: str
    ) -> None:
        run = await _persisted_run(db_session)
        db_session.add(_result(run.id, None, check_name=name))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_eval_result_when_event_has_school_then_school_id_is_copied(
        self, db_session: AsyncSession, school: School
    ) -> None:
        run = await _persisted_run(db_session)
        event = _event(school_id=school.id)
        db_session.add(event)
        await db_session.flush()
        db_session.add(_result(run.id, event.id, school_id=event.school_id))
        await db_session.flush()

        stored = (await db_session.execute(select(EvalResult))).scalar_one()
        assert stored.school_id == school.id

    async def test_eval_result_when_event_is_platform_level_then_school_id_is_null(
        self, db_session: AsyncSession
    ) -> None:
        # NULL means "platform-level (batch/curriculum) task", exactly as on llm_usage_events.
        run = await _persisted_run(db_session)
        event = _event(school_id=None)
        db_session.add(event)
        await db_session.flush()
        db_session.add(_result(run.id, event.id, school_id=event.school_id))
        await db_session.flush()

        stored = (await db_session.execute(select(EvalResult))).scalar_one()
        assert stored.school_id is None

    async def test_eval_result_when_school_deleted_then_result_kept_with_null_school_id(
        self, db_session: AsyncSession, school: School
    ) -> None:
        run = await _persisted_run(db_session)
        result = _result(run.id, None, school_id=school.id)
        db_session.add(result)
        await db_session.flush()

        await db_session.execute(text("DELETE FROM schools WHERE id = :id"), {"id": school.id})
        await db_session.refresh(result)

        assert result.school_id is None

    async def test_eval_result_when_school_unknown_then_integrity_error(self, db_session: AsyncSession) -> None:
        run = await _persisted_run(db_session)
        db_session.add(_result(run.id, None, school_id=uuid.uuid4()))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_eval_result_when_same_run_event_check_inserted_twice_then_unique_violation(
        self, db_session: AsyncSession
    ) -> None:
        run = await _persisted_run(db_session)
        event = _event()
        db_session.add(event)
        await db_session.flush()
        db_session.add(_result(run.id, event.id))
        await db_session.flush()
        db_session.add(_result(run.id, event.id))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.parametrize(
        "overrides",
        [
            {"kind": "bogus"},
            {"passed": None, "indeterminate": False},  # unknown outcome must be flagged indeterminate
            {"passed": True, "indeterminate": True},  # an indeterminate verdict has no pass/fail
            {"kind": "judge"},  # judge results must name the rubric hash and status
            {"rubric_hash": "abc", "rubric_status": "CALIBRATED"},  # deterministic checks have neither
            {"kind": "judge", "rubric_hash": "abc", "rubric_status": "NOT_CALIBRATED"},  # untrusted never stored
        ],
    )
    async def test_eval_result_when_values_inconsistent_then_integrity_error(
        self, db_session: AsyncSession, overrides: dict[str, Any]
    ) -> None:
        run = await _persisted_run(db_session)
        db_session.add(_result(run.id, None, **overrides))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_eval_result_when_judge_verdict_indeterminate_then_persists_with_null_passed(
        self, db_session: AsyncSession
    ) -> None:
        run = await _persisted_run(db_session)
        db_session.add(
            _result(
                run.id,
                None,
                kind="judge",
                passed=None,
                indeterminate=True,
                rubric_hash="abc123",
                rubric_status="HUMAN_VALIDATED",
            )
        )
        await db_session.flush()
        stored = (await db_session.execute(select(EvalResult))).scalar_one()
        assert stored.passed is None and stored.indeterminate is True
