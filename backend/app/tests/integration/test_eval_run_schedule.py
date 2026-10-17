"""Integration test for the weekly evaluation beat on real Postgres (MLH-T18 slice 5b-ii)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.eval_results import EvalRun
from app.models.user import User
from app.services.eval_run_admin_service import EvalRunAdminService
from app.services.platform_settings_service import PlatformSettingsService

TASK = "question_generation"
NOW = datetime(2026, 10, 19, 4, 0, tzinfo=UTC)


async def _settings(db: AsyncSession, admin: User, budget: str) -> None:
    await PlatformSettingsService(db).update_eval_settings(
        actor_id=admin.id,
        monthly_budget_usd=Decimal(budget),
        enabled_tasks=[TASK],
        sample_size_per_task=10,
        window_days=7,
        include_indicative=False,
        acknowledge_student_text_tasks=[],
    )


def _service(db: AsyncSession, enqueued: list[uuid.UUID]) -> EvalRunAdminService:
    config = settings.model_copy(update={"llm_eval_judge_model": "judgevendor/judge-1"})
    return EvalRunAdminService(db, enqueue=enqueued.append, config=config, clock=lambda: NOW)


async def test_beat_entry_when_run_twice_same_day_then_one_scheduled_run_and_one_enqueue(
    db_session: AsyncSession, kaihle_admin: User
) -> None:
    await _settings(db_session, kaihle_admin, "50")
    enqueued: list[uuid.UUID] = []
    service = _service(db_session, enqueued)

    first = await service.schedule_weekly_runs()
    run = (await db_session.execute(select(EvalRun))).scalar_one()
    # Simulate the worker finishing it, then the beat firing again the same day.
    run.status = "completed"
    await db_session.commit()
    second = await service.schedule_weekly_runs()

    assert (first.started, second.started, second.existing) == (1, 0, 1)
    assert enqueued == [run.id]
    assert run.trigger == "scheduled" and run.requested_by is None and run.seed == "scheduled-2026-10-19"


async def test_beat_entry_when_budget_zero_then_no_run_row_created(
    db_session: AsyncSession, kaihle_admin: User
) -> None:
    await _settings(db_session, kaihle_admin, "0")
    enqueued: list[uuid.UUID] = []

    outcome = await _service(db_session, enqueued).schedule_weekly_runs()

    assert outcome.refused_reason == "budget_zero" and enqueued == []
    assert (await db_session.execute(select(func.count()).select_from(EvalRun))).scalar_one() == 0
