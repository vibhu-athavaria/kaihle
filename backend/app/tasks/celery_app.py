from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

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

celery_app.conf.beat_schedule = {
    # existing entries would go here if defined in celery_app directly
    # Nightly stale video link checker — runs at 02:00 every day
    "check-stale-video-links": {
        "task": "tasks.check_stale_video_links",
        "schedule": crontab(hour=2, minute=0),  # every day at 02:00 UTC
    },
}
