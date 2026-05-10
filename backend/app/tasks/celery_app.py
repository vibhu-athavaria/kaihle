import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready
from sqlalchemy import update

from app.core.config import settings

logger = structlog.get_logger(__name__)

celery_app = Celery(
    "kaihle",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.gap_tasks",
        "app.tasks.onboarding_tasks",
        "app.tasks.lesson_plan_tasks",
        "app.tasks.parent_tasks",
        "app.tasks.content_maintenance_tasks",
        "app.tasks.study_plan_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)


@worker_ready.connect
def reconcile_stuck_lesson_plans(sender: object, **kwargs: object) -> None:
    """On worker boot, archive any GENERATING plans older than 15 minutes.

    Covers plans left stuck when a previous worker process was killed mid-task
    (e.g. Render instance restart, SIGKILL). Python exception handlers don't run
    in that case, so this is the only reliable cleanup path.
    """
    from app.core.database import CeleryAsyncSessionLocal
    from app.models.lesson_plan import LessonPlan, LessonPlanFailureCode, LessonPlanStatus

    cutoff = datetime.now(UTC) - timedelta(minutes=15)

    async def _reconcile() -> None:
        async with CeleryAsyncSessionLocal() as db:
            result = await db.execute(
                update(LessonPlan)
                .where(
                    LessonPlan.status == LessonPlanStatus.GENERATING,
                    LessonPlan.updated_at < cutoff,
                )
                .values(
                    status=LessonPlanStatus.ARCHIVED,
                    failure_code=LessonPlanFailureCode.LLM_UNEXPECTED_ERROR,
                    failure_reason="Worker process was killed mid-generation (instance restart).",
                )
                .returning(LessonPlan.id)
            )
            archived_ids = [str(row[0]) for row in result.all()]
            await db.commit()

        if archived_ids:
            logger.warning(
                "stuck_lesson_plans_reconciled_on_startup",
                count=len(archived_ids),
                plan_ids=archived_ids,
            )
        else:
            logger.info("lesson_plan_startup_reconciliation_clean")

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_reconcile())
    except Exception as exc:
        logger.error("lesson_plan_startup_reconciliation_failed", error=str(exc), exc_info=True)
    finally:
        loop.close()


celery_app.conf.beat_schedule = {
    # existing entries would go here if defined in celery_app directly
    # Nightly stale video link checker — runs at 02:00 every day
    "check-stale-video-links": {
        "task": "tasks.check_stale_video_links",
        "schedule": crontab(hour=2, minute=0),  # every day at 02:00 UTC
    },
}
