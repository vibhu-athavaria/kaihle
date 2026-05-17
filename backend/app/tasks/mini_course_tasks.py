"""Mini-course content generation Celery task.

Generate interest-personalised explanations for every subtopic under a topic.
Produces one SubtopicContent row per (subtopic, interest_category) pair — four rows per subtopic.

Two-path logic:
  - Content already exists (status == ready): queue a 30-second delayed email to teacher.
    No regeneration. Feels instant from teacher's perspective.
  - No content (status == none | failed): set status = generating, run full generation,
    update status = ready on success or failed on failure.

Architecture:
  - Route handler (POST /api/v1/topics/{topic_id}/generate-course) enqueues this task.
  - All DB logic lives in MiniCourseGenerationService (services layer).
  - LLM calls go through router.py only (Rule 4).
  - Uses new_event_loop() — never asyncio.run() (Rule 4, Celery safety).
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import celery
import resend  # type: ignore[import]
import structlog
from sqlalchemy import select

from app.core.config import settings
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Email helpers (mirror lesson_plan_tasks pattern)
# ---------------------------------------------------------------------------


def send_mini_course_ready_email(teacher_email: str, topic_name: str) -> None:
    """Send success email to teacher. Non-fatal — log on failure."""
    try:
        resend.api_key = settings.resend_api_key
        course_url = f"{settings.teacher_app_url}/content-review"
        resend.Emails.send(
            {
                "from": settings.from_email,
                "to": [teacher_email],
                "subject": f"Your mini-course for '{topic_name}' is ready",
                "html": (
                    f"<p>Your mini-course for <strong>{topic_name}</strong> has been generated.</p>"
                    f"<p>Students will automatically receive the version that best matches their learning interests.</p>"
                    f'<p><a href="{course_url}">View in Content Review →</a></p>'
                ),
            }
        )
        logger.info("mini_course_ready_email_sent", teacher_email=teacher_email, topic_name=topic_name)
    except Exception as exc:
        logger.warning("mini_course_ready_email_failed", topic_name=topic_name, error=str(exc))


def send_mini_course_failed_email(topic_id: str, topic_name: str, error_detail: str) -> None:
    """Send failure alert to Kaihle admin with full detail. Non-fatal — log on failure."""
    try:
        resend.api_key = settings.resend_api_key
        resend.Emails.send(
            {
                "from": settings.from_email,
                "to": [settings.kaihle_admin_email],
                "subject": f"[ALERT] Mini-course generation failed — {topic_name}",
                "html": (
                    f"<p><strong>Topic:</strong> {topic_name}<br>"
                    f"<strong>Topic ID:</strong> {topic_id}<br>"
                    f"<strong>Error:</strong><br><pre>{error_detail}</pre></p>"
                ),
            }
        )
        logger.info("mini_course_failed_email_sent", topic_id=topic_id)
    except Exception as exc:
        logger.warning("mini_course_failed_email_send_error", topic_id=topic_id, error=str(exc))


# ---------------------------------------------------------------------------
# Delayed email task — used for the "content already exists" fast path
# ---------------------------------------------------------------------------


@celery_app.task(
    name="app.tasks.mini_course_tasks.send_mini_course_ready_email_delayed",
    queue="celery",
)
def send_mini_course_ready_email_delayed(teacher_email: str, topic_name: str) -> None:
    """Sends the 'mini-course ready' email after a 30-second delay.

    Called when content already exists — gives teacher the feel of on-demand generation
    without re-running the LLM pipeline.
    """
    send_mini_course_ready_email(teacher_email=teacher_email, topic_name=topic_name)


# ---------------------------------------------------------------------------
# Core async logic
# ---------------------------------------------------------------------------


async def _run_generation(task: celery.Task, topic_id: str, school_id: str, teacher_id: str) -> dict[str, Any]:
    """Core async logic — runs inside a fresh event loop."""
    from app.core.database import CeleryAsyncSessionLocal
    from app.models.curriculum import Topic
    from app.models.user import User
    from app.services.mini_course_generation_service import MiniCourseGenerationService

    async with CeleryAsyncSessionLocal() as db:
        # Load topic name for email
        topic_row = await db.execute(select(Topic).where(Topic.id == UUID(topic_id)))
        topic = topic_row.scalar_one_or_none()
        topic_name = topic.name if topic else "Unknown Topic"

        # Check if content already exists (fast path)
        from app.models.curriculum import CurriculumTopic, Subtopic
        from app.models.subtopic_content import SubtopicContent

        subtopic_ids_result = await db.execute(
            select(Subtopic.id)
            .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
            .where(CurriculumTopic.topic_id == UUID(topic_id), Subtopic.is_active.is_(True))
        )
        subtopic_ids = [row[0] for row in subtopic_ids_result.all()]

        content_exists = False
        if subtopic_ids:
            count_result = await db.execute(
                select(SubtopicContent.id)
                .where(
                    SubtopicContent.subtopic_id.in_(subtopic_ids),
                    SubtopicContent.content_type == "explanation",
                    SubtopicContent.review_status != "rejected",
                    SubtopicContent.is_archived.is_(False),
                )
                .limit(1)
            )
            content_exists = count_result.first() is not None

        if content_exists:
            # Fast path: content already exists — schedule delayed email, no LLM call
            logger.info(
                "mini_course_content_already_exists_fast_path",
                topic_id=topic_id,
                topic_name=topic_name,
            )
            if topic and topic.mini_course_status != "ready":
                topic.mini_course_status = "ready"
                await db.commit()

            # Fetch teacher email and schedule delayed notification
            if teacher_id:
                teacher_row = await db.execute(select(User).where(User.id == UUID(teacher_id)))
                teacher = teacher_row.scalar_one_or_none()
                if teacher and teacher.email:
                    send_mini_course_ready_email_delayed.apply_async(
                        kwargs={"teacher_email": teacher.email, "topic_name": topic_name},
                        countdown=30,
                    )
            return {"fast_path": True, "subtopics_found": len(subtopic_ids)}

        # Slow path: actually generate
        if topic:
            topic.mini_course_status = "generating"
            if teacher_id:
                topic.mini_course_teacher_id = UUID(teacher_id)
            await db.commit()

        try:
            service = MiniCourseGenerationService(db)
            result = await service.generate_for_topic(topic_id=topic_id, school_id=school_id)
        except Exception:
            # Mark failed, email admin, re-raise so Celery retries
            if topic:
                topic.mini_course_status = "failed"
                await db.commit()
            raise

        if topic:
            topic.mini_course_status = "ready"
            await db.commit()

        # Email teacher on success
        if teacher_id:
            teacher_row = await db.execute(select(User).where(User.id == UUID(teacher_id)))
            teacher = teacher_row.scalar_one_or_none()
            if teacher and teacher.email:
                send_mini_course_ready_email(teacher_email=teacher.email, topic_name=topic_name)

        return result


# ---------------------------------------------------------------------------
# Celery task class (Rule 18 — CRITICAL log on final retry exhaustion)
# ---------------------------------------------------------------------------


class GenerateMiniCourseTask(celery.Task):  # type: ignore[type-arg]
    """Emits CRITICAL log on final retry exhaustion (CONSTITUTION Rule 18)."""

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        topic_id = args[0] if args else kwargs.get("topic_id", "unknown")
        topic_name = kwargs.get("topic_name_hint", topic_id)
        logger.critical(
            "generate_topic_mini_course_permanently_failed",
            task_id=task_id,
            topic_id=topic_id,
            error=str(exc),
            exc_info=True,
        )
        send_mini_course_failed_email(
            topic_id=str(topic_id),
            topic_name=str(topic_name),
            error_detail=str(exc),
        )


# ---------------------------------------------------------------------------
# Celery entry point
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    base=GenerateMiniCourseTask,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
    name="app.tasks.mini_course_tasks.generate_topic_mini_course",
    queue="celery",
)
def generate_topic_mini_course(
    self: celery.Task,
    topic_id: str,
    school_id: str,
    teacher_id: str = "",
) -> dict[str, Any]:
    """Generate interest-personalised mini-course explanations for a topic.

    Two paths:
      1. Content exists → fast path: mark ready, schedule 30s delayed email.
      2. No content → full LLM generation, email on success, admin alert on failure.

    Args:
        topic_id: UUID of the Topic.
        school_id: UUID of the requesting school.
        teacher_id: UUID of the teacher who triggered generation (for email notification).

    Rules applied:
        - Rule 17: WARNING + exit if topic has no subtopics.
        - Rule 18: CRITICAL log on final retry exhaustion (via GenerateMiniCourseTask.on_failure).
        - Rule 4: LLM via router.py only; new_event_loop() not asyncio.run().
    """
    logger.info(
        "generate_topic_mini_course_started",
        topic_id=topic_id,
        school_id=school_id,
        teacher_id=teacher_id,
    )

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            _run_generation(task=self, topic_id=topic_id, school_id=school_id, teacher_id=teacher_id)
        )
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
        **{k: v for k, v in result.items() if k != "fast_path"},
    )
    return result
