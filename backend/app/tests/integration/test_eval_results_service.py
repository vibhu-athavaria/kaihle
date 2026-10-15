"""Integration tests for `EvalResultsService` against a real database.

The unit tests mock the session; these prove the SQL actually behaves: ON CONFLICT
idempotency, the `school_id` copy from the usage event, and the run lifecycle.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.eval_results import EvalResult
from app.models.llm_usage import LlmUsageEvent
from app.models.school import School
from app.services.eval_results_service import CheckOutcome, EvalResultsService, RunCounts

NOW = datetime.now(UTC)
RUN_ARGS = {
    "task": "question_generation",
    "window_start": NOW - timedelta(days=7),
    "window_end": NOW,
    "seed": "seed-1",
    "trigger": "manual",
}


async def _event(db: AsyncSession, school_id: uuid.UUID | None) -> LlmUsageEvent:
    event = LlmUsageEvent(
        id=uuid.uuid4(),
        task="question_generation",
        model="test/model-a",
        latency_ms=1,
        created_at=NOW,
        school_id=school_id,
    )
    db.add(event)
    await db.commit()
    return event


@pytest.mark.asyncio
class TestEvalResultsServiceDb:
    async def test_create_run_when_called_twice_with_same_key_then_second_returns_existing(
        self, db_session: AsyncSession
    ) -> None:
        service = EvalResultsService(db_session)
        first, created_first = await service.create_run(**RUN_ARGS)
        second, created_second = await service.create_run(**RUN_ARGS)

        assert (created_first, created_second) == (True, False)
        assert first.id == second.id

    async def test_record_results_when_event_has_school_then_copies_school_id_and_is_idempotent(
        self, db_session: AsyncSession, school: School
    ) -> None:
        service = EvalResultsService(db_session)
        run, _ = await service.create_run(**RUN_ARGS)
        event = await _event(db_session, school.id)
        outcomes = [
            CheckOutcome("has_four_options", "deterministic", True),
            CheckOutcome("clarity", "judge", None, rubric_hash="h1", rubric_status="CALIBRATED"),
        ]

        first = await service.record_results(run.id, event.id, outcomes)
        retry = await service.record_results(run.id, event.id, outcomes)

        rows = (await db_session.execute(select(EvalResult))).scalars().all()
        assert (first, retry) == (2, 0)
        assert {r.school_id for r in rows} == {school.id}
        assert {r.check_name: r.indeterminate for r in rows} == {"has_four_options": False, "clarity": True}

    async def test_record_results_when_event_is_platform_level_then_school_id_null(
        self, db_session: AsyncSession
    ) -> None:
        service = EvalResultsService(db_session)
        run, _ = await service.create_run(**RUN_ARGS)
        event = await _event(db_session, None)

        await service.record_results(run.id, event.id, [CheckOutcome("a", "deterministic", False)])

        row = (await db_session.execute(select(EvalResult))).scalar_one()
        assert row.school_id is None and row.passed is False

    async def test_record_results_when_event_missing_then_raises_lookup_error(self, db_session: AsyncSession) -> None:
        service = EvalResultsService(db_session)
        run, _ = await service.create_run(**RUN_ARGS)
        with pytest.raises(LookupError):
            await service.record_results(run.id, uuid.uuid4(), [CheckOutcome("a", "deterministic", True)])

    async def test_run_lifecycle_when_started_then_finished_then_state_persisted(
        self, db_session: AsyncSession
    ) -> None:
        service = EvalResultsService(db_session)
        run, _ = await service.create_run(**RUN_ARGS)
        run_id = run.id  # the rejected call below rolls back and expires ORM instances

        await service.mark_started(run_id, judge_model="test/judge")
        with pytest.raises(LookupError):  # no longer pending
            await service.mark_started(run_id, judge_model="test/judge")
        await service.finish_run(
            run_id,
            status="budget_exhausted",
            counts=RunCounts(sampled=10, evaluated=7, skipped_scrub_failed=3),
            spend_usd=Decimal("1.25"),
        )

        db_session.expire_all()
        stored = await service.get_run(run_id)
        assert stored is not None
        assert (stored.status, stored.judge_model) == ("budget_exhausted", "test/judge")
        assert (stored.sampled_count, stored.evaluated_count, stored.skipped_scrub_failed_count) == (10, 7, 3)
        assert stored.spend_usd == Decimal("1.25")
        assert stored.started_at is not None and stored.completed_at is not None
