"""Celery tasks for subtopic content pipeline.

generate_personalised_explanations: triggered when a generic explanation is approved.
Fans out to 4 interest-category variants (sports_movement, tech_gaming, nature_animals, arts_culture).
"""

from __future__ import annotations

import asyncio
import uuid

import resend  # type: ignore[import-untyped]
import structlog
from sqlalchemy import select

from app.ai.providers import router as llm_router
from app.core.config import settings
from app.core.database import CeleryAsyncSessionLocal
from app.models.interest_category import InterestCategory
from app.models.subtopic_content import SubtopicContent
from app.models.user import User, UserRole
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)  # type: ignore[misc]
def generate_personalised_explanations(
    self: object,
    subtopic_id: str,
    explanation_text: str,
) -> dict[str, object]:
    """Generate interest-personalised explanations when a generic one is approved.

    For each of 4 interest categories, generates a personalised version using the
    base explanation text as context. Saves each as a pending SubtopicContent row.
    Notifies all active KAIHLE_ADMIN users by email on completion.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            _run_generate_personalised_explanations(
                task=self,
                subtopic_id=subtopic_id,
                explanation_text=explanation_text,
            )
        )
    finally:
        loop.close()


async def _run_generate_personalised_explanations(
    task: object,
    subtopic_id: str,
    explanation_text: str,
) -> dict[str, object]:
    subtopic_uuid = uuid.UUID(subtopic_id)
    written = 0
    errors = 0

    async with CeleryAsyncSessionLocal() as db:
        # Resolve all interest categories
        cat_result = await db.execute(select(InterestCategory))
        categories = cat_result.scalars().all()

        for cat in categories:
            try:
                prompt = (
                    f"Rewrite the following educational explanation for a student who loves {cat.name}. "
                    f"Keep the same learning objective but use relatable examples and analogies "
                    f"from the context of {cat.name}. Keep it concise (150-250 words).\n\n"
                    f"Original explanation:\n{explanation_text}"
                )
                personalised = await llm_router.complete(
                    task="mini_course_explanation",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=600,
                )

                # Upsert: update existing pending/rejected row, or create new one
                existing_result = await db.execute(
                    select(SubtopicContent).where(
                        SubtopicContent.subtopic_id == subtopic_uuid,
                        SubtopicContent.content_type == "explanation",
                        SubtopicContent.interest_category_id == cat.id,
                        SubtopicContent.scope == "curriculum",
                    )
                )
                existing = existing_result.scalar_one_or_none()

                if existing is not None:
                    existing.explanation_text = personalised
                    existing.review_status = "pending"
                else:
                    db.add(
                        SubtopicContent(
                            subtopic_id=subtopic_uuid,
                            content_type="explanation",
                            scope="curriculum",
                            interest_category_id=cat.id,
                            explanation_text=personalised,
                            review_status="pending",
                        )
                    )
                written += 1
            except Exception as exc:
                logger.error(
                    "personalised_explanation_generation_failed",
                    subtopic_id=subtopic_id,
                    interest_category=cat.name,
                    error=str(exc),
                )
                errors += 1

        await db.commit()

        resend.api_key = settings.resend_api_key

        # Email all active KAIHLE_ADMIN users
        try:
            admin_result = await db.execute(
                select(User).where(
                    User.role == UserRole.KAIHLE_ADMIN,
                    User.is_active.is_(True),
                )
            )
            admins = admin_result.scalars().all()
            await _notify_admins_personalised_ready(admins, subtopic_id, written)
        except Exception as exc:
            logger.error("admin_notification_failed", subtopic_id=subtopic_id, error=str(exc))

    logger.info(
        "personalised_explanations_generated",
        subtopic_id=subtopic_id,
        written=written,
        errors=errors,
    )
    return {"subtopic_id": subtopic_id, "written": written, "errors": errors}


async def _notify_admins_personalised_ready(
    admins: list[User],
    subtopic_id: str,
    count: int,
) -> None:
    """Send email notification to all active KaihleAdmin users."""
    for admin in admins:
        if not admin.email:
            logger.warning("admin_email_missing", admin_id=str(admin.id))
            continue
        try:
            resend.Emails.send(
                {
                    "from": settings.from_email,
                    "to": [admin.email],
                    "subject": "Personalised explanations ready for review",
                    "html": (
                        f"<p>Hi {admin.first_name},</p>"
                        f"<p>{count} personalised explanation(s) have been generated for subtopic "
                        f"<code>{subtopic_id}</code> and are awaiting your review.</p>"
                        f"<p>Please log in to the Kaihle Admin portal to review.</p>"
                    ),
                }
            )
        except Exception as exc:
            logger.warning("admin_email_send_failed", admin_id=str(admin.id), error=str(exc))
