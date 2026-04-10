"""Gap state calculation Celery task.

M1-4-T3: Computes per-subtopic recency-weighted mastery after each attempt is COMPLETED
and upserts gap_states rows via GapService.
"""

import asyncio
import uuid as _uuid

import celery
import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


def _parse_uuid(value: str, param_name: str) -> _uuid.UUID:
    """Parse a string as UUID and raise ValueError if invalid."""
    try:
        return _uuid.UUID(value)
    except ValueError:
        raise ValueError(f"Invalid UUID for {param_name}: {value}")


class CalculateGapStatesTask(celery.Task):
    """Celery Task subclass that emits a CRITICAL log when all retries are exhausted.

    Per CONSTITUTION Rule 18: tasks must emit a CRITICAL log on final retry exhaustion.
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo) -> None:  # type: ignore[override]
        """Called by Celery when all retries are exhausted.

        Emits a CRITICAL structured log event so the operations team is alerted.
        Per CONSTITUTION Rule 18.
        """
        logger.critical(
            "calculate_gap_states_permanently_failed",
            task_id=task_id,
            attempt_id=args[0] if args else kwargs.get("attempt_id"),
            error=str(exc),
            exc_info=True,
        )


@celery_app.task(
    bind=True,
    base=CalculateGapStatesTask,
    max_retries=3,
    default_retry_delay=10,
    name="app.tasks.gap_tasks.calculate_gap_states",
)
def calculate_gap_states(self, attempt_id: str) -> dict[str, object]:
    """Calculate and persist per-subtopic gap states after an attempt is COMPLETED.

    Delegates all business logic to GapService.calculate_gap_states_for_attempt().
    Creates a new event loop per CONSTITUTION Rule 4 (Celery tasks must use
    new_event_loop() — never asyncio.run inside a task).

    Args:
        attempt_id: The StudentAttempt UUID as string.

    Returns:
        Dict with attempt_id and subtopics_updated count.
    """
    logger.info("calculate_gap_states_started", attempt_id=attempt_id)

    try:
        attempt_uuid = _parse_uuid(attempt_id, "attempt_id")
    except ValueError as exc:
        logger.error("invalid_attempt_id_uuid", attempt_id=attempt_id, error=str(exc))
        raise

    async def _run_service(attempt_id_str: str) -> dict[str, object]:
        from app.core.database import AsyncSessionLocal
        from app.services.gap_service import GapService

        async with AsyncSessionLocal() as db:
            async with db.begin():
                service = GapService(db)
                return await service.calculate_gap_states_for_attempt(attempt_uuid)

    try:
        loop = asyncio.new_event_loop()
        try:
            run_result = loop.run_until_complete(_run_service(attempt_id))
        finally:
            loop.close()

        logger.info(
            "calculate_gap_states_completed",
            attempt_id=attempt_id,
            subtopics_updated=run_result["subtopics_updated"],
        )
        return run_result

    except Exception as exc:
        logger.error(
            "calculate_gap_states_failed",
            attempt_id=attempt_id,
            error=str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc)
