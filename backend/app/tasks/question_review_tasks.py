"""Question review notification Celery tasks.

Sends email notifications to KaihleAdmin users when teachers submit new questions
or edit suggestions for review.
"""

import asyncio

import celery
import structlog
from sqlalchemy import select

from app.tasks.celery_app import celery_app

logger = structlog.get_logger()

# Known retriable errors for email sending
RETRIABLE_EXCEPTIONS = (ConnectionError, TimeoutError, OSError)


class NotifyKaihleAdminsTask(celery.Task):
    """Celery Task that emits CRITICAL log on final retry exhaustion (Rule 18)."""

    def on_failure(self, exc: Exception, task_id: str, args: list, kwargs: dict, einfo: object) -> None:
        logger.critical(
            "notify_kaihle_admins_final_failure",
            task_id=task_id,
            exc_info=True,
        )


@celery_app.task(
    bind=True,
    base=NotifyKaihleAdminsTask,
    max_retries=2,
    default_retry_delay=30,
    name="app.tasks.question_review_tasks.notify_kaihle_admins_of_review_item",
)
def notify_kaihle_admins_of_review_item(
    self: celery.Task,
    review_item_id: str,
    item_type: str,
    submitted_by_id: str,
) -> None:
    """Send an email to all KaihleAdmin users about a new question review item.

    Args:
        review_item_id: UUID of the question_review_items row.
        item_type: 'TEACHER_QUESTION' or 'EDIT_SUGGESTION'.
        submitted_by_id: UUID of the teacher who submitted the item.
    """
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_send_review_notification_async(review_item_id, item_type, submitted_by_id))
    except RETRIABLE_EXCEPTIONS as exc:
        logger.error(
            "notify_kaihle_admins_retriable_error",
            review_item_id=review_item_id,
            item_type=item_type,
            exc_info=True,
        )
        raise self.retry(exc=exc) from exc
    except Exception:  # noqa: BLE001
        logger.critical(
            "notify_kaihle_admins_non_retriable_error",
            review_item_id=review_item_id,
            item_type=item_type,
            exc_info=True,
        )
        # Do NOT retry for non-retriable errors
    finally:
        loop.close()


async def _send_review_notification_async(
    review_item_id: str,
    item_type: str,
    submitted_by_id: str,
) -> None:
    """Load admin emails and send the notification concurrently."""
    from app.core.database import AsyncSessionLocal  # noqa: PLC0415
    from app.models.user import User, UserRole  # noqa: PLC0415
    from app.services.email_service import EmailService  # noqa: PLC0415

    async with AsyncSessionLocal() as db:
        # Load all active KaihleAdmin users
        admins_result = await db.execute(
            select(User.email, User.first_name).where(
                User.role == UserRole.KAIHLE_ADMIN,
                User.is_active.is_(True),
            )
        )
        admins = admins_result.all()

        if not admins:
            logger.warning(
                "no_kaihle_admins_found_for_review_notification",
                review_item_id=review_item_id,
            )
            return

        email_svc = EmailService()
        subject_map = {
            "TEACHER_QUESTION": "New question submitted for review",
            "EDIT_SUGGESTION": "New edit suggestion submitted for review",
        }
        subject = subject_map.get(item_type, "New question review item")
        admin_url = "https://admin.kaihle.com/kaihle-admin/content/question-review"

        # Send all emails concurrently; failures are logged per-admin but don't block others
        results = await asyncio.gather(
            *(
                email_svc.send(
                    to=admin.email,
                    subject=subject,
                    template="question_review_notification.html",
                    ctx={
                        "admin_name": admin.first_name or "Admin",
                        "item_type": item_type,
                        "review_item_id": review_item_id,
                        "submitted_by_id": submitted_by_id,
                        "admin_url": admin_url,
                    },
                )
                for admin in admins
            ),
            return_exceptions=True,
        )

        # Log per-admin failures
        for admin, result in zip(admins, results, strict=False):
            if isinstance(result, Exception):
                logger.error(
                    "review_notification_email_failed",
                    to=admin.email,
                    review_item_id=review_item_id,
                    exc_info=result,
                )
