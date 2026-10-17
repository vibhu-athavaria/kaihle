"""Integration test: a `grade_open_answer` run on real Postgres (MLH-T18 slice 5c).

Real: sampling, scrub names, settings (incl. the student-text acknowledgement), run and result
persistence. Faked: the judge (a spy). Rubrics G1/G2 have no stored calibration, so the real status
resolver excludes them and no judge call may happen; a forced CALIBRATED resolver proves that when they
do run the judge only sees scrubbed text.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.eval.rubric_core import RubricSpec
from app.core.config import settings
from app.models.eval_results import EvalResult, EvalRun
from app.models.llm_usage import LlmUsageEvent
from app.models.user import User
from app.services.eval_prod.grade_evaluators import GRADE_CHECKS, GRADE_TASK
from app.services.eval_prod.registry import StatusResolver, calibration_status_from_files
from app.services.eval_prod.sampler import SYSTEM_EVAL_ACTOR
from app.services.eval_run_service import EvalRunService
from app.services.mini_course_service import render_grade_prompt
from app.services.platform_settings_service import PlatformSettingsService

JUDGE = "judgevendor/judge-1"
NOW = datetime.now(UTC)
VERDICT = json.dumps({"pass": True, "evidence": "ok"})
EMAIL = "typed.by.student@example.com"


class _Judge:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return VERDICT


async def _seed(db: AsyncSession) -> None:
    db.add(
        LlmUsageEvent(
            id=uuid.uuid4(),
            task=GRADE_TASK,
            model="other/gen-1",
            latency_ms=5,
            created_at=NOW - timedelta(hours=1),
            succeeded=True,
            school_id=None,
            prompt_text=render_grade_prompt("Density", "Describe density.", "Why does ice float?", f"Ask {EMAIL}"),
            response_text=json.dumps({"grade": "partial", "feedback": "Good start, think about density."}),
        )
    )
    await db.commit()


async def _run(db: AsyncSession, admin: User, judge: _Judge, status_of: StatusResolver) -> EvalRun:
    await PlatformSettingsService(db).update_eval_settings(
        actor_id=admin.id,
        monthly_budget_usd=Decimal("50"),
        enabled_tasks=[GRADE_TASK],
        sample_size_per_task=10,
        window_days=7,
        include_indicative=False,
        acknowledge_student_text_tasks=[GRADE_TASK],
    )
    config = settings.model_copy(
        update={"llm_eval_judge_model": JUDGE, "llm_usage_tracking_enabled": True, "eval_unpriced_call_cost_usd": 0.01}
    )
    service = EvalRunService(
        db,
        config=config,
        status_of=status_of,
        completion_factory=lambda run_id: judge,
        price_estimator=lambda model, prompt_tokens, completion_tokens: Decimal("0.001"),
    )
    run, _ = await service.request_run(
        task=GRADE_TASK,
        window_start=NOW - timedelta(days=7),
        window_end=NOW + timedelta(minutes=1),
        seed="seed-1",
        trigger="manual",
    )
    return await service.execute_run(run.id, SYSTEM_EVAL_ACTOR)


async def _results(db: AsyncSession, run: EvalRun) -> list[EvalResult]:
    return list((await db.execute(select(EvalResult).where(EvalResult.run_id == run.id))).scalars().all())


async def test_grade_run_when_rubrics_uncalibrated_then_only_deterministic_results_and_no_judge_call(
    db_session: AsyncSession, kaihle_admin: User
) -> None:
    await _seed(db_session)
    judge = _Judge()
    run = await _run(db_session, kaihle_admin, judge, calibration_status_from_files)
    assert run.status == "completed" and judge.prompts == []
    assert (run.sampled_count, run.evaluated_count) == (1, 1)
    rows = await _results(db_session, run)
    assert sorted(r.check_name for r in rows) == sorted(GRADE_CHECKS)
    assert all(r.passed is True for r in rows)
    assert EMAIL not in repr([vars(r) for r in rows])


async def test_grade_run_when_rubrics_calibrated_then_judge_sees_scrubbed_text_and_verdicts_stored(
    db_session: AsyncSession, kaihle_admin: User
) -> None:
    await _seed(db_session)
    judge = _Judge()

    def calibrated(spec: RubricSpec) -> str:
        return "CALIBRATED"

    run = await _run(db_session, kaihle_admin, judge, calibrated)
    assert run.status == "completed"
    assert len(judge.prompts) == 2 and EMAIL not in "\n".join(judge.prompts) and "[EMAIL]" in judge.prompts[0]
    rows = await _results(db_session, run)
    assert len(rows) == len(GRADE_CHECKS) + 2
    assert {r.check_name for r in rows if r.kind == "judge"} == {
        "G1_feedback_constructive_calibrated",
        "G2_feedback_no_reveal",
    }
