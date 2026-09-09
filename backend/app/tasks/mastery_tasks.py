"""Periodic recalibration of hierarchical mastery priors.

MLH-T3-2. `mastery_priors` is a snapshot: fitting it once and never again means a subject
that starts with zero response data stays pinned to the GLOBAL prior forever, even after a
school generates enough usage in it to deserve its own subject-specific prior. This task
re-runs the same fitting logic on a schedule, following the exact pattern
content_maintenance_tasks.py already uses for check_stale_video_links (Task subclass for
Rule 18 CRITICAL logging, shared_task with a fixed name, new_event_loop rather than
asyncio.run() per .claude/rules/04-transactions-and-idempotency.md).

Never called from request paths — background maintenance only, registered in
celery_app.conf.beat_schedule.
"""

import asyncio
from typing import Any

import structlog
from celery import Task, shared_task
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from scripts.calibrate_mastery_prior import gather_all_subtopic_pools, render, resolve_prior, write_priors

logger = structlog.get_logger()


class RecalibrateMasteryPriorsTask(Task):
    """Emits a CRITICAL log when all retries are exhausted. Per CONSTITUTION Rule 18."""

    def on_failure(
        self, exc: Exception, task_id: str, args: tuple[Any, ...], kwargs: dict[str, Any], einfo: Any
    ) -> None:
        logger.critical(
            "recalibrate_mastery_priors_permanently_failed",
            task_id=task_id,
            error=str(exc),
            exc_info=True,
        )


async def _run() -> dict[str, int]:
    """Fit and write. Own engine — Celery tasks each run in a fresh event loop and must
    not share the pooled FastAPI session factory (see core/database.py)."""
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with async_session() as db:
            pools_by_subtopic = await gather_all_subtopic_pools(db)
            if not pools_by_subtopic:
                # Guard against an empty curriculum, the same way Rule 17 guards against
                # an empty question bank — log and exit cleanly rather than writing nothing
                # and looking like a silent success.
                logger.warning("recalibrate_mastery_priors_no_active_subtopics")
                return {"subtopics_resolved": 0}

            # Shared across the loop — see resolve_prior's level_cache docstring; without
            # it this refits the GLOBAL pool once per subtopic instead of once total.
            level_cache: dict[int, tuple[float, float, int] | None] = {}
            resolutions = {
                subtopic_id: resolve_prior(
                    pools,
                    fallback_alpha=settings.mastery_prior_alpha,
                    fallback_beta=settings.mastery_prior_beta,
                    level_cache=level_cache,
                )
                for subtopic_id, pools in pools_by_subtopic.items()
            }
            logger.info("recalibrate_mastery_priors_resolved", report=render(resolutions))
            await write_priors(db, resolutions)
            await db.commit()
            return {"subtopics_resolved": len(resolutions)}
    finally:
        await engine.dispose()


@shared_task(
    bind=True,
    base=RecalibrateMasteryPriorsTask,
    max_retries=3,
    default_retry_delay=300,
    ignore_result=True,
    name="tasks.recalibrate_mastery_priors",
)
def recalibrate_mastery_priors(self: Task, *args: Any, **kwargs: Any) -> None:
    """Celery beat task — re-fits mastery_priors from current response data.

    Runs weekly (celery_app.py beat_schedule), not nightly: at pilot scale, a single day
    rarely adds enough responses to move a level across MIN_ROWS_FOR_FIT. Calls the same
    fitting logic scripts/calibrate_mastery_prior.py --apply uses — one code path for the
    manual and the scheduled entry point, never duplicated.
    """
    logger.info("recalibrate_mastery_priors_started")
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_run())
        logger.info("recalibrate_mastery_priors_completed", **result)
    except Exception as exc:
        logger.warning("recalibrate_mastery_priors_attempt_failed", error=str(exc), exc_info=True)
        raise self.retry(exc=exc) from exc
    finally:
        loop.close()
