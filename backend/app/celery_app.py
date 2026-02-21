"""
Celery Application - Phase 0 Placeholder

This is a minimal Celery app configuration for Phase 0.
Full task definitions and configuration will be added in Phase 1.
"""

from celery import Celery
import os

# Get Redis URL from environment
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
celery_broker_url = os.environ.get("CELERY_BROKER_URL", f"{redis_url}/1")
celery_result_backend = os.environ.get("CELERY_RESULT_BACKEND", f"{redis_url}/1")

# Create Celery app
celery_app = Celery(
    "kaihle",
    broker=celery_broker_url,
    backend=celery_result_backend,
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    worker_prefetch_multiplier=1,
)

# Auto-discover tasks from app.tasks module (to be created in Phase 1)
# celery_app.autodiscover_tasks(["app.tasks"])


# Health check task for Phase 0 verification
@celery_app.task(name="app.celery_app.health_check")
def health_check():
    """Simple health check task to verify Celery is working."""
    return {"status": "healthy", "service": "celery_worker"}
