"""Gap state calculation Celery task.

M1-4-T3: Computes per-subtopic recency-weighted mastery after each attempt is COMPLETED
and upserts gap_states rows via GapService.
"""

import asyncio
import uuid as _uuid

import celery
import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


def _parse_uuid(value: str, param_name: str) -> _uuid.UUID:
    """Parse a string as UUID and raise ValueError if invalid."""
    try:
        return _uuid.UUID(value)
    except ValueError:
        raise ValueError(f"Invalid UUID for {param_name}: {value}")


class CalculateGapStatesTask(celery.Task):
    """Celery Task subclass that emits a CRITICAL log when all retries are exhausted.

    Per CONSTITUTION Rule 18: tasks must emit a CRITICAL log on final retry exhaustion.
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo) -> None:  # type: ignore[override]
        """Called by Celery when all retries are exhausted.

        Emits a CRITICAL structured log event so the operations team is alerted.
        Per CONSTITUTION Rule 18.
        """
        logger.critical(
            "calculate_gap_states_permanently_failed",
            task_id=task_id,
            attempt_id=args[0] if args else kwargs.get("attempt_id"),
            error=str(exc),
            exc_info=True,
        )


@celery_app.task(
    bind=True,
    base=CalculateGapStatesTask,
    max_retries=3,
    default_retry_delay=10,
    name="app.tasks.gap_tasks.calculate_gap_states",
)
def calculate_gap_states(self, attempt_id: str) -> dict[str, object]:
    """Calculate and persist per-subtopic gap states after an attempt is COMPLETED.

    Delegates all business logic to GapService.calculate_gap_states_for_attempt().
    Creates a new event loop per CONSTITUTION Rule 4 (Celery tasks must use
    new_event_loop() — never asyncio.run inside a task).

    Args:
        attempt_id: The StudentAttempt UUID as string.

    Returns:
        Dict with attempt_id and subtopics_updated count.
    """
    logger.info("calculate_gap_states_started", attempt_id=attempt_id)

    try:
        attempt_uuid = _parse_uuid(attempt_id, "attempt_id")
    except ValueError as exc:
        logger.error("invalid_attempt_id_uuid", attempt_id=attempt_id, error=str(exc))
        raise

    async def _run_service(attempt_id_str: str) -> dict[str, object]:
        from app.core.database import AsyncSessionLocal
        from app.services.gap_service import GapService

        async with AsyncSessionLocal() as db:
            async with db.begin():
                service = GapService(db)
                return await service.calculate_gap_states_for_attempt(attempt_uuid)

    try:
        loop = asyncio.new_event_loop()
        try:
            run_result = loop.run_until_complete(_run_service(attempt_id))
        finally:
            loop.close()

        logger.info(
            "calculate_gap_states_completed",
            attempt_id=attempt_id,
            subtopics_updated=run_result["subtopics_updated"],
        )
        return run_result

    except Exception as exc:
        logger.error(
            "calculate_gap_states_failed",
            attempt_id=attempt_id,
            error=str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# update_gap_state_from_quiz — M3-2-T1
# Triggered after a study plan quiz is submitted.
# Updates the student's gap state for the subtopic based on quiz score.
# ---------------------------------------------------------------------------


class UpdateGapFromQuizTask(celery.Task):
    """Task subclass with CRITICAL log on final retry exhaustion (CONSTITUTION Rule 18)."""

    def on_failure(self, exc, task_id, args, kwargs, einfo) -> None:  # type: ignore[override]
        logger.critical(
            "update_gap_from_quiz_permanently_failed",
            task_id=task_id,
            plan_id=args[0] if args else kwargs.get("plan_id"),
            error=str(exc),
            exc_info=True,
        )


@celery_app.task(
    bind=True,
    base=UpdateGapFromQuizTask,
    max_retries=2,
    default_retry_delay=15,
    name="app.tasks.gap_tasks.update_gap_state_from_quiz",
)
def update_gap_state_from_quiz(
    self,
    plan_id: str,
    subtopic_id: str,
    student_id: str | None = None,
) -> dict[str, object]:
    """Recalculate gap state for a student after submitting a study plan quiz.

    Unlike ``calculate_gap_states`` (which is attempt-driven), this task is
    triggered by study plan quiz submission. It loads the quiz result directly
    and upserts the gap_states row for the subtopic.

    Args:
        plan_id: UUID string of the StudyPlan.
        subtopic_id: UUID string of the Subtopic.
        student_id: Optional UUID string — if not provided, loaded from the plan.

    Returns:
        Dict with plan_id, subtopic_id, and new_mastery.
    """
    logger.info(
        "update_gap_from_quiz_started",
        plan_id=plan_id,
        subtopic_id=subtopic_id,
    )

    try:
        plan_uuid = _parse_uuid(plan_id, "plan_id")
        subtopic_uuid = _parse_uuid(subtopic_id, "subtopic_id")
        student_uuid = _parse_uuid(student_id, "student_id") if student_id else None
    except ValueError as exc:
        logger.error("invalid_uuid_args", error=str(exc))
        raise

    async def _run_service() -> dict[str, object]:
        from datetime import UTC, datetime

        from sqlalchemy import select

        from app.core.database import AsyncSessionLocal
        from app.models import GapState, StudyPlan, StudyPlanQuiz
        from app.services.gap_service import GapService

        async with AsyncSessionLocal() as db:
            async with db.begin():
                # Load plan to get student_id, school_id, class_id
                plan_result = await db.execute(select(StudyPlan).where(StudyPlan.id == plan_uuid))
                plan = plan_result.scalar_one_or_none()
                if not plan:
                    return {"plan_id": plan_id, "status": "error", "reason": "plan_not_found"}

                effective_student_id = student_uuid or plan.student_id
                school_id = plan.school_id
                class_id = plan.class_id

                # Load quiz score
                quiz_result = await db.execute(select(StudyPlanQuiz).where(StudyPlanQuiz.plan_id == plan_uuid))
                quiz = quiz_result.scalar_one_or_none()
                score = quiz.score if quiz else 0.0

                # Get existing attempt count for rolling count
                gap_result = await db.execute(
                    select(GapState).where(
                        GapState.student_id == effective_student_id,
                        GapState.subtopic_id == subtopic_uuid,
                        GapState.class_id == class_id,
                    )
                )
                existing_gap = gap_result.scalar_one_or_none()
                rolling_count = (existing_gap.attempt_count or 0) + 1

                # Upsert gap state
                service = GapService(db)
                await service.upsert_gap_state(
                    student_id=effective_student_id,
                    subtopic_id=subtopic_uuid,
                    school_id=school_id,
                    class_id=class_id,
                    new_mastery=score,
                    rolling_attempt_count=rolling_count,
                    last_assessed_at=datetime.now(UTC),
                )
                return {
                    "plan_id": plan_id,
                    "subtopic_id": subtopic_id,
                    "student_id": str(effective_student_id),
                    "score": score,
                    "rolling_attempt_count": rolling_count,
                }

    try:
        loop = asyncio.new_event_loop()
        try:
            run_result = loop.run_until_complete(_run_service())
        finally:
            loop.close()

        logger.info(
            "update_gap_from_quiz_completed",
            plan_id=plan_id,
            score=run_result.get("score"),
            new_mastery=run_result.get("new_mastery"),
        )
        return run_result

    except Exception as exc:
        logger.error(
            "update_gap_from_quiz_failed",
            plan_id=plan_id,
            error=str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc)
