"""Study Plan Content Generation Celery Tasks — M3-2-T1.

generate_study_plan_content: async task that:
1. Loads the StudyPlan and StudentLearningProfile
2. Curates resources (via content_curator.py)
3. Generates a quiz (via quiz_generator.py)
4. Stores results in StudyPlanResource + StudyPlanQuiz
5. Updates StudyPlan status to ACTIVE (or ABANDONED on failure)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import celery
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.quiz_generator import generate_quiz
from app.core.database import CeleryAsyncSessionLocal
from app.models import Class, StudyPlan, StudyPlanQuiz, StudyPlanResource
from app.models.study_plan import ResourceType, StudyPlanStatus
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

SHARED_TASK_NAME = "app.tasks.study_plan_tasks.generate_study_plan_content"


# ---------------------------------------------------------------------------
# Task subclass — emits CRITICAL log on final retry exhaustion (Rule 18)
# ---------------------------------------------------------------------------


class GenerateStudyPlanContentTask(celery.Task):
    """Celery Task subclass that emits a CRITICAL log when all retries are exhausted.

    Per CONSTITUTION Rule 18: tasks must emit a CRITICAL log on final retry exhaustion.
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo) -> None:  # type: ignore[override]
        """Called by Celery when all retries are exhausted."""
        logger.critical(
            "generate_study_plan_content_permanently_failed",
            task_id=task_id,
            plan_id=args[0] if args else kwargs.get("plan_id"),
            error=str(exc),
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    base=GenerateStudyPlanContentTask,
    name=SHARED_TASK_NAME,
    max_retries=2,
    default_retry_delay=30,
    time_limit=120,
    queue="celery",
)
def generate_study_plan_content(self: GenerateStudyPlanContentTask, plan_id: str) -> dict:
    """Generate study plan content asynchronously.

    Args:
        plan_id: UUID string of the StudyPlan.

    Returns:
        Dict with plan_id, status, resource_count, quiz_id on success.

    Creates a new event loop per CONSTITUTION Rule 4 (Celery tasks must use
    new_event_loop() — never asyncio.run() inside a task).
    """
    logger.info("study_plan_content_generation_started", plan_id=plan_id)

    async def _run() -> dict:
        async with CeleryAsyncSessionLocal() as session:
            return await _generate_content(plan_id, session)

    try:
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(_run())
        finally:
            loop.close()

        logger.info(
            "study_plan_content_generation_completed",
            plan_id=plan_id,
            resource_count=result.get("resource_count", 0),
            quiz_id=result.get("quiz_id"),
        )
        return result

    except Exception as exc:
        logger.error(
            "study_plan_content_generation_failed",
            plan_id=plan_id,
            error=str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=30)


# ---------------------------------------------------------------------------
# Core logic (async, needs its own session)
# ---------------------------------------------------------------------------


async def _generate_content(plan_id: str, db: AsyncSession) -> dict:
    """Execute content generation for a study plan.

    Steps:
    1. Load StudyPlan + StudentLearningProfile + Subtopic
    2. Curate resources → StudyPlanResource rows
    3. Generate quiz → StudyPlanQuiz row
    4. Update plan status to ACTIVE
    """
    from app.ai.content_curator import curate_resources
    from app.models import StudentLearningProfile, Subtopic

    # ---- 1. Load plan ----
    result = await db.execute(select(StudyPlan).where(StudyPlan.id == UUID(plan_id)))
    plan = result.scalar_one_or_none()
    if not plan:
        logger.error("study_plan_not_found", plan_id=plan_id)
        return {"plan_id": plan_id, "status": "error", "reason": "plan_not_found"}

    if plan.status != StudyPlanStatus.GENERATING:
        logger.warning(
            "study_plan_not_generating",
            plan_id=plan_id,
            status=str(plan.status),
        )
        return {"plan_id": plan_id, "status": "skipped", "reason": "not_generating"}

    # ---- 2. Load subtopic ----
    subtopic_result = await db.execute(select(Subtopic).where(Subtopic.id == plan.subtopic_id))
    subtopic = subtopic_result.scalar_one_or_none()
    if not subtopic:
        logger.error("subtopic_not_found", plan_id=plan_id, subtopic_id=str(plan.subtopic_id))
        await _mark_abandoned(plan, db, "subtopic_not_found")
        return {"plan_id": plan_id, "status": "error", "reason": "subtopic_not_found"}

    # ---- 3. Load student learning profile ----
    profile_result = await db.execute(
        select(StudentLearningProfile).where(StudentLearningProfile.student_id == plan.student_id)
    )
    profile = profile_result.scalar_one_or_none()
    student_mastery = 0.3  # default (gap-based, start conservative)
    if profile and profile.mastery_levels:
        student_mastery = profile.mastery_levels.get(str(plan.subtopic_id), 0.3)

    # ---- 4. Look up grade level and school_id from the class ----
    grade_level = 8  # sensible default
    school_id = UUID(int=0)  # fallback; overwritten from class row below
    class_result = await db.execute(select(Class).where(Class.id == plan.class_id))
    class_row = class_result.scalar_one_or_none()
    if class_row:
        if class_row.school_id:
            school_id = class_row.school_id
        if class_row.grade_id:
            from app.models.school import Grade

            grade_result = await db.execute(select(Grade).where(Grade.id == class_row.grade_id))
            grade_row = grade_result.scalar_one_or_none()
            if grade_row and grade_row.name:
                try:
                    grade_level = int(grade_row.name.replace("Grade ", "").strip())
                except (ValueError, AttributeError):
                    grade_level = 8

    resource_ids = []
    quiz_id = None

    # ---- 5. Curate resources ----
    try:
        resources = await curate_resources(
            subtopic_id=plan.subtopic_id,
            student_id=plan.student_id,
            school_id=school_id,
            db=db,
            redis_client=None,  # Celery task — no Redis in worker by default
        )
        for i, res in enumerate(resources):
            pr = StudyPlanResource(
                plan_id=plan.id,
                title=res.title,
                resource_type=_map_resource_type(res.resource_type.value),
                url=res.url,
                source=res.source or "KAIHLE",
                duration_seconds=res.duration_seconds,
                order_index=i,
            )
            db.add(pr)
            await db.flush()
            resource_ids.append(str(pr.id))

        logger.info(
            "resources_curated",
            plan_id=plan_id,
            count=len(resources),
        )
    except Exception as exc:
        logger.warning(
            "resource_curation_failed",
            plan_id=plan_id,
            error=str(exc),
        )
        # Non-fatal: plan can still have a quiz-only experience

    # ---- 6. Generate quiz ----
    try:
        generated_quiz = await generate_quiz(
            subtopic=subtopic,
            student_mastery=student_mastery,
            student_id=plan.student_id,
            db=db,
            grade_level=grade_level,
        )
        quiz_record = StudyPlanQuiz(
            plan_id=plan.id,
            questions={"questions": [q.to_dict() for q in generated_quiz.questions]},
        )
        db.add(quiz_record)
        await db.flush()
        quiz_id = str(quiz_record.id)

        logger.info(
            "quiz_generated",
            plan_id=plan_id,
            question_count=len(generated_quiz.questions),
            quiz_id=quiz_id,
        )
    except Exception as exc:
        logger.warning(
            "quiz_generation_failed",
            plan_id=plan_id,
            error=str(exc),
        )
        # Non-fatal: resources can still be useful without quiz

    # ---- 7. Update plan status ----
    plan.status = StudyPlanStatus.ACTIVE
    plan.generated_at = datetime.now(UTC)
    await db.commit()

    return {
        "plan_id": plan_id,
        "status": "completed",
        "resource_count": len(resource_ids),
        "quiz_id": quiz_id,
    }


async def _mark_abandoned(plan: StudyPlan, db: AsyncSession, reason: str) -> None:
    """Mark a plan as ABANDONED and commit."""
    plan.status = StudyPlanStatus.ABANDONED
    await db.commit()
    logger.warning("study_plan_marked_abandoned", plan_id=str(plan.id), reason=reason)


def _map_resource_type(rt: str) -> ResourceType:
    """Map content curator resource type to StudyPlanResource type."""
    mapping: dict[str, ResourceType] = {
        "video": ResourceType.VIDEO,
        "article": ResourceType.ARTICLE,
        "interactive": ResourceType.INTERACTIVE,
    }
    return mapping.get(rt.lower(), ResourceType.ARTICLE)
