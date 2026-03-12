"""Onboarding Celery tasks.

M0-6-T2: Tier 1 Auto-Diagnostic Trigger.
Fired when a student is enrolled in a class. Creates system-generated
DIAGNOSTIC assessments for the student's subject, with questions spanning
all curriculum topics for the grade+curriculum.
"""

import structlog
from sqlalchemy import select

from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="app.tasks.onboarding_tasks.trigger_onboarding_diagnostics",
)
def trigger_onboarding_diagnostics(self, student_id: str, class_id: str) -> dict[str, object]:  # type: ignore[no-untyped-def]
    """Create Tier 1 DIAGNOSTIC assessments on student enrollment.

    Fired on student enrollment. Creates one DIAGNOSTIC assessment for the
    class subject for this student. Marks is_system_generated=TRUE on each.
    Idempotent — safe to call multiple times for the same student+class.

    After all subjects are processed, sets student_profiles.onboarding_diagnostic_status
    to IN_PROGRESS (only if currently PENDING — does not regress from IN_PROGRESS or COMPLETED).

    Args:
        student_id: The student UUID as string.
        class_id: The class UUID as string.

    Returns:
        Dict with created_count and student_id.
    """
    import asyncio
    import uuid as _uuid

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.models.user import OnboardingStatus, StudentProfile
    from app.services.assessment_service import AssessmentService

    logger.info(
        "trigger_onboarding_diagnostics_started",
        student_id=student_id,
        class_id=class_id,
    )

    async def _run() -> dict[str, object]:
        engine = create_async_engine(settings.database_url, echo=False)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as db:
            async with db.begin():
                service = AssessmentService(db)
                student_uuid = _uuid.UUID(student_id)
                class_uuid = _uuid.UUID(class_id)

                created = await service.create_system_diagnostic(
                    student_id=student_uuid,
                    class_id=class_uuid,
                )

                # Update onboarding_diagnostic_status to IN_PROGRESS
                # only if currently PENDING — never regress from IN_PROGRESS or COMPLETED
                profile_result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == student_uuid))
                student_profile = profile_result.scalar_one_or_none()

                if (
                    student_profile is not None
                    and student_profile.onboarding_diagnostic_status == OnboardingStatus.PENDING
                ):
                    student_profile.onboarding_diagnostic_status = OnboardingStatus.IN_PROGRESS
                    logger.info(
                        "onboarding_diagnostic_status_updated",
                        student_id=student_id,
                        previous_status=OnboardingStatus.PENDING,
                        new_status=OnboardingStatus.IN_PROGRESS,
                    )

            return {"created_count": len(created), "student_id": student_id}

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
            created_count=run_result["created_count"],
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
