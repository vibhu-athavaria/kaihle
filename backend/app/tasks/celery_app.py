from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "kaihle",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.gap_tasks", "app.tasks.onboarding_tasks",
             "app.tasks.lesson_plan_tasks", "app.tasks.parent_tasks"],
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
