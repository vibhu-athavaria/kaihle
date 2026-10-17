"""Integration tests for `EvalRunService` on real Postgres (MLH-T18 slice 5b-i).

Only the judge is faked (a spy returning a canned verdict); sampling, scrubbing names, settings,
results and run persistence are real.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.eval_results import EvalResult, EvalRun
from app.models.llm_usage import LlmUsageEvent
from app.models.school import School
from app.models.user import User
from app.services.eval_prod.sampler import SYSTEM_EVAL_ACTOR
from app.services.eval_run_service import EvalRunService
from app.services.platform_settings_service import PlatformSettingsService

TASK = "question_generation"
JUDGE = "judgevendor/judge-1"
NOW = datetime.now(UTC)
PROMPT = "- Subject:   Mathematics (MATH)\n- Grade:   7\n- Subtopic:   Adding fractions\n"
REPLY = json.dumps({"pass": True, "answer": "A", "correct_options": ["A"], "evidence": "ok"})


class _Judge:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return REPLY


def _batch(text: str) -> str:
    question = {
        "difficulty_level": 3,
        "question_type": "multiple_choice",
        "question_text": text,
        "options": {"A": "3/4", "B": "2/6", "C": "1/8", "D": "1"},
        "correct_answer": "A",
        "learning_objectives": ["Add fractions"],
        "explanation": "A is right.",
    }
    return json.dumps({"questions": [question]})


async def _seed_event(db: AsyncSession, school_id: uuid.UUID | None, text: str) -> uuid.UUID:
    event = LlmUsageEvent(
        id=uuid.uuid4(),
        task=TASK,
        model="other/gen-1",
        latency_ms=5,
        created_at=NOW - timedelta(hours=1),
        succeeded=True,
        school_id=school_id,
        prompt_text=PROMPT,
        response_text=_batch(text),
    )
    db.add(event)
    await db.commit()
    return event.id


async def _service(db: AsyncSession, admin: User, judge: _Judge) -> EvalRunService:
    await PlatformSettingsService(db).update_eval_settings(
        actor_id=admin.id,
        monthly_budget_usd=Decimal("50"),
        enabled_tasks=[TASK],
        sample_size_per_task=10,
        window_days=7,
        include_indicative=False,
        acknowledge_student_text_tasks=[],
    )
    config = settings.model_copy(
        update={"llm_eval_judge_model": JUDGE, "llm_usage_tracking_enabled": True, "eval_unpriced_call_cost_usd": 0.01}
    )
    return EvalRunService(
        db,
        config=config,
        status_of=lambda spec: "CALIBRATED",
        completion_factory=lambda run_id: judge,
        price_estimator=lambda model, prompt_tokens, completion_tokens: Decimal("0.001"),
    )


async def _request(service: EvalRunService, seed: str = "seed-1") -> EvalRun:
    run, _ = await service.request_run(
        task=TASK,
        window_start=NOW - timedelta(days=7),
        window_end=NOW + timedelta(minutes=1),
        seed=seed,
        trigger="manual",
    )
    return run


async def test_run_when_events_evaluated_then_results_stored_with_school_id_copied_and_no_text(
    db_session: AsyncSession, kaihle_admin: User, school: School
) -> None:
    judge = _Judge()
    school_event = await _seed_event(db_session, school.id, "Zebra stem for school")
    platform_event = await _seed_event(db_session, None, "Zebra stem for platform")
    service = await _service(db_session, kaihle_admin, judge)
    run = await service.execute_run((await _request(service)).id, SYSTEM_EVAL_ACTOR)

    assert run.status == "completed" and run.judge_model == JUDGE
    assert (run.sampled_count, run.evaluated_count) == (2, 2)
    assert run.spend_usd == Decimal("0.001") * len(judge.prompts) > 0
    rows = (await db_session.execute(select(EvalResult).where(EvalResult.run_id == run.id))).scalars().all()
    assert len(rows) == 2 * (4 + 7)
    assert {r.school_id for r in rows if r.usage_event_id == school_event} == {school.id}
    assert {r.school_id for r in rows if r.usage_event_id == platform_event} == {None}
    assert all(r.passed is not None and not r.indeterminate for r in rows)
    assert "Zebra" not in repr([vars(r) for r in rows])


async def test_run_when_same_task_window_seed_requested_twice_then_one_run_and_no_duplicate_results(
    db_session: AsyncSession, kaihle_admin: User
) -> None:
    judge = _Judge()
    await _seed_event(db_session, None, "Stem")
    service = await _service(db_session, kaihle_admin, judge)
    first = await _request(service)
    again = await _request(service)
    assert again.id == first.id
    await service.execute_run(first.id, SYSTEM_EVAL_ACTOR)
    calls = len(judge.prompts)
    await service.execute_run(first.id, SYSTEM_EVAL_ACTOR)  # already finished: no-op
    assert len(judge.prompts) == calls
    runs = await db_session.scalar(select(func.count()).select_from(EvalRun).where(EvalRun.task == TASK))
    results = await db_session.scalar(select(func.count()).select_from(EvalResult).where(EvalResult.run_id == first.id))
    assert runs == 1 and results == 4 + 7


async def test_run_when_no_events_in_window_then_status_empty(db_session: AsyncSession, kaihle_admin: User) -> None:
    service = await _service(db_session, kaihle_admin, _Judge())
    run = await service.execute_run((await _request(service)).id, SYSTEM_EVAL_ACTOR)
    assert run.status == "empty" and run.sampled_count == 0


async def test_run_when_budget_is_zero_then_failed_without_judge_call(
    db_session: AsyncSession, kaihle_admin: User
) -> None:
    judge = _Judge()
    await _seed_event(db_session, None, "Stem")
    service = await _service(db_session, kaihle_admin, judge)
    await PlatformSettingsService(db_session).update_eval_settings(
        actor_id=kaihle_admin.id,
        monthly_budget_usd=Decimal("0"),
        enabled_tasks=[TASK],
        sample_size_per_task=10,
        window_days=7,
        include_indicative=False,
        acknowledge_student_text_tasks=[],
    )
    run = await service.execute_run((await _request(service, "seed-0")).id, SYSTEM_EVAL_ACTOR)
    assert run.status == "failed" and run.error_type == "BudgetRefusedError" and judge.prompts == []
