"""Onboarding Celery tasks.

M0-6-T2: Tier 1 Auto-Diagnostic Trigger.

Two entry points:
- create_class_diagnostic_task: fired when a class is created.
  Creates a system-generated DIAGNOSTIC assessment with a pool of 60 questions.
- trigger_onboarding_diagnostics: fired when a student is enrolled in a class.
  Creates a StudentAttempt for the class's diagnostic and updates onboarding status.
"""

import asyncio
import uuid as _uuid

import structlog
from sqlalchemy import update

from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


def _parse_uuid(value: str, param_name: str) -> _uuid.UUID:
    """Parse a string as UUID and raise ValueError if invalid.

    Args:
        value: The string to parse as UUID.
        param_name: Name of the parameter (for error message).

    Returns:
        The parsed UUID.

    Raises:
        ValueError: If the string is not a valid UUID.
    """
    try:
        return _uuid.UUID(value)
    except ValueError:
        raise ValueError(f"Invalid UUID for {param_name}: {value}")


def _on_class_diagnostic_failure(
    task_self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: object
) -> None:
    """Called by Celery when all retries are exhausted.

    Emits a CRITICAL structured log event so the operations team is alerted.
    Per CONSTITUTION Rule 18.
    """
    logger.critical(
        "celery_task_permanently_failed",
        task_name=task_self.name,
        task_id=task_id,
        class_id=args[0] if args else kwargs.get("class_id"),
        error=str(exc),
        exc_info=True,
    )


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="app.tasks.onboarding_tasks.create_class_diagnostic_task",
    on_failure=_on_class_diagnostic_failure,
)
def create_class_diagnostic_task(self, class_id: str) -> dict[str, object]:
    """Create a Tier 1 DIAGNOSTIC assessment for a newly created class.

    Fired when a class is created. Selects a pool of up to 60 questions
    spanning all curriculum topics for the class's subject+grade.
    Idempotent — safe to call multiple times.

    Args:
        class_id: The class UUID as string.

    Returns:
        Dict with assessment_id and class_id.
    """
    from app.core.database import CeleryAsyncSessionLocal
    from app.services.assessment_service import AssessmentService, QuestionBankEmptyError

    logger.info("create_class_diagnostic_task_started", class_id=class_id)

    # Validate UUID before attempting async operation
    try:
        class_uuid = _parse_uuid(class_id, "class_id")
    except ValueError as exc:
        logger.error("invalid_class_id_uuid", class_id=class_id, error=str(exc))
        raise

    async def _run() -> dict[str, object]:
        async with CeleryAsyncSessionLocal() as db:
            async with db.begin():
                service = AssessmentService(db)
                assessment = await service.create_class_diagnostic(
                    class_id=class_uuid,
                )

            return {
                "assessment_id": str(assessment.id),
                "class_id": class_id,
            }

    try:
        loop = asyncio.new_event_loop()
        try:
            run_result = loop.run_until_complete(_run())
        finally:
            loop.close()

        logger.info(
            "create_class_diagnostic_task_completed",
            class_id=class_id,
            assessment_id=run_result["assessment_id"],
        )
        return run_result

    except QuestionBankEmptyError as exc:
        logger.warning(
            "create_class_diagnostic_skipped_empty_question_bank",
            class_id=class_id,
            reason=str(exc),
        )
        # Return without creating assessment — task succeeded, just had nothing to do.
        # The assessment will be created when the teacher manually triggers it after
        # import_questions.py has been run.
        return {"assessment_id": None, "class_id": class_id, "skipped": True}

    except Exception as exc:
        logger.error(
            "create_class_diagnostic_task_failed",
            class_id=class_id,
            error=str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc)


def _on_onboarding_failure(task_self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: object) -> None:
    """Called by Celery when all retries are exhausted.

    Emits a CRITICAL structured log event so the operations team is alerted.
    Per CONSTITUTION Rule 18.
    """
    logger.critical(
        "celery_task_permanently_failed",
        task_name=task_self.name,
        task_id=task_id,
        student_id=args[0] if args else kwargs.get("student_id"),
        class_id=args[1] if len(args) > 1 else kwargs.get("class_id"),
        error=str(exc),
        exc_info=True,
    )


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="app.tasks.onboarding_tasks.trigger_onboarding_diagnostics",
    on_failure=_on_onboarding_failure,
)
def trigger_onboarding_diagnostics(self, student_id: str, class_id: str) -> dict[str, object]:
    """Create a StudentAttempt for the class diagnostic on student enrollment.

    Fired on student enrollment. The class must already have a system-generated
    diagnostic assessment (created by create_class_diagnostic_task).
    Idempotent — safe to call multiple times for the same student+class.

    After creating the attempt, sets class_enrollments.onboarding_diagnostic_status
    to IN_PROGRESS for the specific class (only if currently PENDING — does not regress).

    Args:
        student_id: The student UUID as string.
        class_id: The class UUID as string.

    Returns:
        Dict with attempt_id and student_id.
    """
    from app.core.database import CeleryAsyncSessionLocal
    from app.models.school import ClassEnrollment
    from app.models.user import OnboardingStatus
    from app.services.assessment_service import AssessmentService

    logger.info(
        "trigger_onboarding_diagnostics_started",
        student_id=student_id,
        class_id=class_id,
    )

    # Validate UUIDs before attempting async operation
    try:
        student_uuid = _parse_uuid(student_id, "student_id")
        class_uuid = _parse_uuid(class_id, "class_id")
    except ValueError as exc:
        logger.error("invalid_uuid", student_id=student_id, class_id=class_id, error=str(exc))
        raise

    async def _run() -> dict[str, object]:
        async with CeleryAsyncSessionLocal() as db:
            async with db.begin():
                service = AssessmentService(db)

                attempt = await service.create_diagnostic_attempt(
                    student_id=student_uuid,
                    class_id=class_uuid,
                )

                # Update onboarding_diagnostic_status to IN_PROGRESS for the specific class enrollment
                # only if currently PENDING — never regress
                await db.execute(
                    update(ClassEnrollment)
                    .where(
                        ClassEnrollment.class_id == class_uuid,
                        ClassEnrollment.student_id == student_uuid,
                        ClassEnrollment.onboarding_diagnostic_status == OnboardingStatus.PENDING,
                    )
                    .values(onboarding_diagnostic_status=OnboardingStatus.IN_PROGRESS)
                )
                logger.info(
                    "onboarding_diagnostic_status_updated",
                    student_id=student_id,
                    class_id=class_id,
                    previous_status=OnboardingStatus.PENDING,
                    new_status=OnboardingStatus.IN_PROGRESS,
                )

            return {"attempt_id": str(attempt.id), "student_id": student_id}

    try:
        loop = asyncio.new_event_loop()
        try:
            run_result = loop.run_until_complete(_run())
        finally:
            loop.close()

        logger.info(
            "trigger_onboarding_diagnostics_completed",
            student_id=student_id,
            class_id=class_id,
            attempt_id=run_result["attempt_id"],
        )
        return run_result

    except Exception as exc:
        logger.error(
            "trigger_onboarding_diagnostics_failed",
            student_id=student_id,
            class_id=class_id,
            error=str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc)
