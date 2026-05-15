"""Mini-course content generation Celery task.

M5-1-T4: Generate interest-personalised explanations for every subtopic
under a topic. Produces one SubtopicContent row per
(subtopic, interest_category) pair — four rows per subtopic.

Architecture:
- Route handler (POST /api/v1/topics/{topic_id}/generate-course) enqueues
  this task and returns {"task_id": ..., "status": "queued"}.
- All DB logic lives in MiniCourseGenerationService (services layer).
- LLM calls go through router.py only (Rule 4).
- Uses new_event_loop() — never asyncio.run() (Rule 4, Celery safety).
"""

from __future__ import annotations

import asyncio
from typing import Any

import celery
import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


class GenerateMiniCourseTask(celery.Task):
    """Celery Task subclass that emits a CRITICAL log when all retries are exhausted.

    Per CONSTITUTION Rule 18: tasks must emit a CRITICAL log on final retry exhaustion.
    """

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        """Emit CRITICAL structured log on final retry exhaustion (Rule 18)."""
        topic_id = args[0] if args else kwargs.get("topic_id")
        logger.critical(
            "generate_topic_mini_course_permanently_failed",
            task_id=task_id,
            topic_id=topic_id,
            error=str(exc),
            exc_info=True,
        )


@celery_app.task(
    bind=True,
    base=GenerateMiniCourseTask,
    max_retries=3,
    default_retry_delay=30,
    name="app.tasks.mini_course_tasks.generate_topic_mini_course",
)
def generate_topic_mini_course(self: celery.Task, topic_id: str, school_id: str) -> dict[str, Any]:
    """Generate interest-personalised mini-course explanations for a topic.

    For each subtopic under the topic, generates 4 explanations (one per
    interest category) and upserts them into subtopic_content.

    Skips (subtopic_id, interest_category_id) pairs that already have a
    non-rejected row — idempotent by design.

    Args:
        topic_id: UUID of the Topic (curriculum-layer, school-agnostic).
        school_id: UUID of the requesting school — used for access logging only.

    Returns:
        Dict with counts of subtopics processed and explanations written.

    Rules applied:
        - Rule 17: logs WARNING and exits early if topic has no subtopics.
        - Rule 18: CRITICAL log on final retry exhaustion (via GenerateMiniCourseTask.on_failure).
        - Rule 4: LLM via router.py only; new_event_loop() not asyncio.run().
    """
    logger.info(
        "generate_topic_mini_course_started",
        topic_id=topic_id,
        school_id=school_id,
    )

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_run_generation(task=self, topic_id=topic_id, school_id=school_id))
    except Exception as exc:
        logger.error(
            "generate_topic_mini_course_failed",
            topic_id=topic_id,
            school_id=school_id,
            error=str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc)
    finally:
        loop.close()

    logger.info(
        "generate_topic_mini_course_completed",
        topic_id=topic_id,
        school_id=school_id,
        **result,
    )
    return result


async def _run_generation(task: celery.Task, topic_id: str, school_id: str) -> dict[str, Any]:
    """Core async logic — runs inside a fresh event loop.

    Separated from the Celery task function so it can be exercised in
    async unit tests without spawning a loop.
    """
    from app.core.database import CeleryAsyncSessionLocal
    from app.services.mini_course_generation_service import MiniCourseGenerationService

    async with CeleryAsyncSessionLocal() as db:
        service = MiniCourseGenerationService(db)
        return await service.generate_for_topic(topic_id=topic_id, school_id=school_id)
