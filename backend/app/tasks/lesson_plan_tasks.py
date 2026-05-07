"""Lesson plan Celery tasks.

On-demand generation: teacher triggers via POST /classes/{class_id}/lesson-plans/generate.
No weekly beat schedule — replaced by on-demand model.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from pathlib import Path
from uuid import UUID

import celery
import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.lesson_plan import LessonPlan, LessonPlanFailureCode, LessonPlanStatus
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "ai" / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), autoescape=False)

TASK_NAME = "lesson_plan_tasks.generate_lesson_plan"


class GenerateLessonPlanTask(celery.Task):
    """Emits CRITICAL log and archives the plan on final retry exhaustion (CONSTITUTION Rule 18)."""

    def on_failure(self, exc, task_id, args, kwargs, einfo) -> None:  # type: ignore[override]
        lesson_plan_id = args[0] if args else kwargs.get("lesson_plan_id")
        class_id = args[1] if len(args) > 1 else kwargs.get("class_id")
        logger.critical(
            "generate_lesson_plan_permanently_failed",
            task_id=task_id,
            lesson_plan_id=lesson_plan_id,
            class_id=class_id,
            error=str(exc),
            exc_info=True,
        )
        if not lesson_plan_id:
            return

        async def _archive() -> None:
            from uuid import UUID

            async with AsyncSessionLocal() as session:
                from sqlalchemy import select

                result = await session.execute(select(LessonPlan).where(LessonPlan.id == UUID(str(lesson_plan_id))))
                plan = result.scalar_one_or_none()
                if plan and plan.status == LessonPlanStatus.GENERATING:
                    await _mark_archived(
                        plan,
                        session,
                        LessonPlanFailureCode.LLM_UNEXPECTED_ERROR,
                        "Generation failed after multiple retries. Please try again.",
                    )

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_archive())
        finally:
            loop.close()


@celery_app.task(
    bind=True,
    base=GenerateLessonPlanTask,
    max_retries=3,
    default_retry_delay=30,
    name=TASK_NAME,
    time_limit=120,
    queue="celery",
)
def generate_lesson_plan_task(
    self: GenerateLessonPlanTask,
    lesson_plan_id: str,
    class_id: str,
    focus_subtopic_ids: list[str],
    gap_summary: dict,
    duration_minutes: int = 45,
) -> dict:
    """Generate a lesson plan via LLM.

    Creates a new event loop per CONSTITUTION Rule 4.
    """
    logger.info(
        "lesson_plan_generation_started",
        lesson_plan_id=lesson_plan_id,
        class_id=class_id,
        duration_minutes=duration_minutes,
    )

    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            return await _generate(lesson_plan_id, class_id, focus_subtopic_ids, gap_summary, duration_minutes, session)

    try:
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(_run())
        finally:
            loop.close()

        logger.info("lesson_plan_generation_completed", lesson_plan_id=lesson_plan_id, status=result.get("status"))
        return result

    except Exception as exc:
        logger.error("lesson_plan_generation_failed", lesson_plan_id=lesson_plan_id, error=str(exc), exc_info=True)
        raise self.retry(exc=exc, countdown=30)


async def _generate(
    lesson_plan_id: str,
    class_id: str,
    focus_subtopic_ids: list[str],
    gap_summary: dict,
    duration_minutes: int,
    db: AsyncSession,
) -> dict:
    from app.ai.providers import router as llm_router
    from app.models.curriculum import Grade, Subject
    from app.models.lesson_plan import LessonPlanFailureCode
    from app.models.onboarding import StudentLearningProfile
    from app.models.school import Class, ClassEnrollment

    result = await db.execute(select(LessonPlan).where(LessonPlan.id == UUID(lesson_plan_id)))
    plan = result.scalar_one_or_none()
    if not plan:
        logger.error("lesson_plan_not_found", lesson_plan_id=lesson_plan_id)
        return {"lesson_plan_id": lesson_plan_id, "status": "error", "reason": "not_found"}

    if plan.status != LessonPlanStatus.GENERATING:
        logger.warning("lesson_plan_not_generating", lesson_plan_id=lesson_plan_id, status=plan.status)
        return {"lesson_plan_id": lesson_plan_id, "status": "skipped", "reason": "not_generating"}

    # ---- Load class context ----
    class_result = await db.execute(select(Class).where(Class.id == UUID(class_id)))
    class_ = class_result.scalar_one_or_none()
    if not class_:
        logger.error("class_not_found", class_id=class_id)
        await _mark_archived(
            plan, db, LessonPlanFailureCode.CLASS_NOT_FOUND, "Generation failed: class record not found."
        )
        return {"lesson_plan_id": lesson_plan_id, "status": "error", "reason": "class_not_found"}

    grade_name = "Unknown Grade"
    subject_name = "Unknown Subject"

    if class_.grade_id:
        gr = await db.get(Grade, class_.grade_id)
        if gr:
            grade_name = gr.name

    if class_.subject_id:
        subj = await db.get(Subject, class_.subject_id)
        if subj:
            subject_name = subj.name

    # ---- Load enrolled student count ----
    from sqlalchemy import func

    enrollment_result = await db.execute(
        select(func.count()).where(
            ClassEnrollment.class_id == UUID(class_id),
        )
    )
    student_count = enrollment_result.scalar_one() or 0

    # ---- Load learning profiles for modality distribution ----
    enrolled_result = await db.execute(
        select(ClassEnrollment.student_id).where(ClassEnrollment.class_id == UUID(class_id))
    )
    student_ids = [row[0] for row in enrolled_result.all()]

    modality_totals: dict[str, float] = defaultdict(float)
    interests_counter: dict[str, int] = defaultdict(int)
    profile_count = 0

    if student_ids:
        profiles_result = await db.execute(
            select(StudentLearningProfile).where(StudentLearningProfile.student_id.in_(student_ids))
        )
        for profile in profiles_result.scalars().all():
            profile_count += 1
            for modality, score in (profile.modality_scores or {}).items():
                modality_totals[modality] += float(score)
            for interest in profile.interests or []:
                interests_counter[interest] += 1

    modality_distribution: dict[str, float] = {}
    if profile_count:
        modality_distribution = {m: total / profile_count for m, total in modality_totals.items()}

    top_interests = [interest for interest, _ in sorted(interests_counter.items(), key=lambda x: -x[1])[:5]]

    # ---- Build subtopics list for prompt ----
    subtopics_for_prompt = [
        {
            "name": info["name"],
            "learning_objective": info.get("learning_objective", ""),
            "class_avg": info["class_avg"],
            "student_count": info["student_count"],
        }
        for subtopic_id, info in gap_summary.items()
    ]

    # ---- Render prompt ----
    template = _jinja_env.get_template("lesson_plan.jinja2")
    prompt_text = template.render(
        class_name=class_.name,
        subject_name=subject_name,
        grade_name=grade_name,
        student_count=student_count,
        duration_minutes=duration_minutes,
        subtopics=subtopics_for_prompt,
        modality_distribution=modality_distribution,
        common_interests=top_interests,
    )

    # ---- Call LLM ----
    import litellm

    try:
        response_text = await llm_router.complete(
            task="lesson_plan",
            messages=[{"role": "user", "content": prompt_text}],
        )
    except litellm.AuthenticationError as exc:
        logger.error(
            "lesson_plan_llm_auth_failed",
            lesson_plan_id=lesson_plan_id,
            class_id=class_id,
            model=str(exc.model) if hasattr(exc, "model") else "unknown",
            error=str(exc),
            exc_info=True,
        )
        await _mark_archived(
            plan,
            db,
            LessonPlanFailureCode.LLM_AUTH_ERROR,
            "Generation failed: LLM provider authentication error. Check API key configuration.",
        )
        return {"lesson_plan_id": lesson_plan_id, "status": "error", "reason": "llm_auth_error"}
    except litellm.RateLimitError as exc:
        logger.error(
            "lesson_plan_llm_rate_limited",
            lesson_plan_id=lesson_plan_id,
            class_id=class_id,
            error=str(exc),
            exc_info=True,
        )
        # Rate limits are transient — let the task retry
        raise
    except litellm.APIConnectionError as exc:
        logger.error(
            "lesson_plan_llm_connection_failed",
            lesson_plan_id=lesson_plan_id,
            class_id=class_id,
            error=str(exc),
            exc_info=True,
        )
        raise
    except Exception as exc:
        logger.error(
            "lesson_plan_llm_unexpected_error",
            lesson_plan_id=lesson_plan_id,
            class_id=class_id,
            error=str(exc),
            exc_info=True,
        )
        await _mark_archived(
            plan, db, LessonPlanFailureCode.LLM_UNEXPECTED_ERROR, "Generation failed due to an unexpected error."
        )
        return {"lesson_plan_id": lesson_plan_id, "status": "error", "reason": "llm_unexpected_error"}

    # ---- Parse JSON response ----
    try:
        generated_plan = json.loads(response_text.strip())
    except json.JSONDecodeError:
        logger.error("lesson_plan_json_parse_failed", lesson_plan_id=lesson_plan_id, raw=response_text[:500])
        await _mark_archived(
            plan, db, LessonPlanFailureCode.JSON_PARSE_FAILED, "Generation failed: AI returned an unreadable response."
        )
        return {"lesson_plan_id": lesson_plan_id, "status": "error", "reason": "json_parse_failed"}

    plan.generated_plan = generated_plan
    plan.status = LessonPlanStatus.GENERATED
    await db.commit()

    return {"lesson_plan_id": lesson_plan_id, "status": "completed"}


async def _mark_archived(
    plan: LessonPlan,
    db: AsyncSession,
    failure_code: str,
    user_message: str | None = None,
) -> None:
    plan.status = LessonPlanStatus.ARCHIVED
    plan.failure_code = failure_code
    plan.failure_reason = user_message or failure_code
    await db.commit()
    logger.error(
        "lesson_plan_generation_failed_permanently",
        plan_id=str(plan.id),
        failure_code=failure_code,
        user_message=user_message,
    )
