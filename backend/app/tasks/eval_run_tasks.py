"""Celery tasks for production-evaluation runs (MLH-T18 slice 5b-ii).

  * `tasks.run_eval_run(run_id)`: evaluates one pending run (`EvalRunService.execute_run`) as
    SYSTEM_EVAL_ACTOR. Idempotent: a run that is not pending is returned untouched, so a redelivered
    or duplicate message does nothing. `execute_run` records evaluation failures itself (status
    `failed`, error class name) and does not raise for them; this task retries ONLY unexpected
    infrastructure errors (database, broker) and gives up with a CRITICAL log (Rule 18).
  * `tasks.schedule_weekly_eval_runs`: the weekly beat. Creates and enqueues a `scheduled` run per
    enabled task; starts nothing when the budget is 0, no task is enabled or no judge is set.

Both use a NEW event loop (never asyncio.run, .claude/rules/04) and a NullPool session. Nothing
here logs prompt/response text: log lines carry run ids, counts and exception class names.
"""

import asyncio
import uuid
from typing import Any

import structlog
from celery import Task, shared_task

from app.core.database import CeleryAsyncSessionLocal
from app.services.eval_prod.sampler import SYSTEM_EVAL_ACTOR
from app.services.eval_run_admin_service import EvalRunAdminService, ScheduleOutcome
from app.services.eval_run_service import EvalRunService

logger = structlog.get_logger()

RUN_TASK_NAME = "tasks.run_eval_run"
SCHEDULE_TASK_NAME = "tasks.schedule_weekly_eval_runs"
_RETRY_DELAY_SECONDS = 120
_MAX_RETRIES = 3


class EvalRunTask(Task):
    """Emits a CRITICAL log when all retries are exhausted. Per CONSTITUTION Rule 18."""

    def on_failure(
        self, exc: Exception, task_id: str, args: tuple[Any, ...], kwargs: dict[str, Any], einfo: Any
    ) -> None:
        logger.critical(
            "eval_run_task_permanently_failed",
            task_name=RUN_TASK_NAME,
            task_id=task_id,
            run_id=str(args[0]) if args else kwargs.get("run_id", "unknown"),
            error_type=type(exc).__name__,  # class only: a message could echo prompt text
            exc_info=exc,
        )


class ScheduleEvalRunsTask(Task):
    """Same Rule 18 CRITICAL log for the weekly beat."""

    def on_failure(
        self, exc: Exception, task_id: str, args: tuple[Any, ...], kwargs: dict[str, Any], einfo: Any
    ) -> None:
        logger.critical(
            "eval_schedule_task_permanently_failed",
            task_name=SCHEDULE_TASK_NAME,
            task_id=task_id,
            error_type=type(exc).__name__,
            exc_info=exc,
        )


def enqueue_eval_run(run_id: uuid.UUID) -> None:
    """Hand a pending run to the worker. Side effect: publishes a message to the broker."""
    run_eval_run.delay(str(run_id))


async def _execute_run(run_id: uuid.UUID) -> None:
    async with CeleryAsyncSessionLocal() as db:
        try:
            await EvalRunService(db).execute_run(run_id, SYSTEM_EVAL_ACTOR)
        except LookupError:
            # The run was deleted before the worker picked it up; nothing to retry.
            logger.warning("eval_run_task.run_not_found", run_id=str(run_id))


async def _schedule_weekly_runs() -> ScheduleOutcome:
    async with CeleryAsyncSessionLocal() as db:
        return await EvalRunAdminService(db, enqueue=enqueue_eval_run).schedule_weekly_runs()


@shared_task(
    bind=True,
    base=EvalRunTask,
    max_retries=_MAX_RETRIES,
    default_retry_delay=_RETRY_DELAY_SECONDS,
    acks_late=True,
    ignore_result=True,
    name=RUN_TASK_NAME,
)
def run_eval_run(self: Task, run_id: str) -> None:
    """Evaluate one pending run. Safe to deliver twice (non-pending runs are a no-op)."""
    try:
        parsed = uuid.UUID(run_id)
    except ValueError:
        logger.error("eval_run_task.invalid_run_id")
        return
    logger.info("eval_run_task.started", run_id=run_id)
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_execute_run(parsed))
    except Exception as exc:
        logger.warning("eval_run_task.attempt_failed", run_id=run_id, error_type=type(exc).__name__)
        raise self.retry(exc=exc) from exc
    finally:
        loop.close()


@shared_task(
    bind=True,
    base=ScheduleEvalRunsTask,
    max_retries=2,
    default_retry_delay=_RETRY_DELAY_SECONDS,
    ignore_result=True,
    name=SCHEDULE_TASK_NAME,
)
def schedule_weekly_eval_runs(self: Task, *args: Any, **kwargs: Any) -> None:
    """Celery beat task (celery_app.py beat_schedule): start this week's scheduled evaluations."""
    loop = asyncio.new_event_loop()
    try:
        outcome = loop.run_until_complete(_schedule_weekly_runs())
        logger.info(
            "eval_schedule_task.completed",
            started=outcome.started,
            existing=outcome.existing,
            skipped_not_allowed=outcome.skipped_not_allowed,
            refused_reason=outcome.refused_reason,
        )
    except Exception as exc:
        logger.warning("eval_schedule_task.attempt_failed", error_type=type(exc).__name__)
        raise self.retry(exc=exc) from exc
    finally:
        loop.close()
