"""Kaihle Admin entry points for production-evaluation runs (MLH-T18 slice 5b-ii).

Sits between the routes / the weekly beat task and `EvalRunService`: it resolves defaults,
validates the request, and decides WHEN a run is handed to the Celery worker. It does not
sample, judge or store results (that is `EvalRunService`), and it never imports Celery: the
caller passes `enqueue`, so this module stays unit-testable and free of an import cycle with
`app.tasks`.

ENQUEUE RULES
  * Manual ("Run now"): enqueue only when the run was newly created. A repeat of the same
    (task, window, seed) returns the existing run and enqueues nothing (idempotent).
  * Scheduled (weekly beat): enqueue a newly created run, and also a same-day run that is still
    `pending` (an earlier attempt created it but failed before enqueueing). `execute_run` ignores
    runs that are not pending, so a duplicate message is harmless.

SCHEDULE GUARDS. The beat starts nothing when the monthly budget is 0, no task is enabled, or no
judge model is configured; each refusal is logged (WARNING for budget/judge, INFO for no tasks).
Tasks whose student-text acknowledgement is missing are skipped and counted.

Tenancy: runs are platform-wide and every caller is a Kaihle Admin (or the beat acting as
SYSTEM_EVAL_ACTOR), so no `school_id` filter applies (Rule 12, enforced by the route guard).
Nothing here reads or logs prompt/response text.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.models.eval_results import EvalRun
from app.services.eval_results_service import EvalResultsService, EvalResultsValidationError
from app.services.eval_run_service import EvalRunService, RunNotAllowedError, scheduled_window_and_seed
from app.services.platform_settings_service import EvalSettings, PlatformSettingsService
from app.services.quality_summary_service import MAX_WINDOW_DAYS

logger = structlog.get_logger()

MAX_RUNS_PAGE_SIZE = 100
DEFAULT_RUNS_PAGE_SIZE = 20
_MANUAL_SEED_PREFIX = "manual-"
_NOT_ALLOWED_MESSAGE = (
    "This task cannot be evaluated: it is not enabled, or its student-text acknowledgement is missing."
)

EnqueueRun = Callable[[uuid.UUID], None]


class EvalRunRequestError(ValueError):
    """The request is invalid or not allowed. The message is safe to show to the admin (422)."""


class EnqueueFailedError(RuntimeError):
    """The run was created but could not be handed to the worker (broker unreachable)."""


class _RunStore(Protocol):
    async def list_runs(self, *, page: int, page_size: int) -> tuple[list[EvalRun], int]: ...

    async def get_run(self, run_id: uuid.UUID) -> EvalRun | None: ...


class _SettingsSource(Protocol):
    async def get_eval_settings(self) -> EvalSettings: ...


class _RunRequester(Protocol):
    async def request_run(
        self,
        *,
        task: str,
        window_start: datetime,
        window_end: datetime,
        seed: str,
        trigger: str,
        requested_by: uuid.UUID | None = None,
    ) -> tuple[EvalRun, bool]: ...


@dataclass(frozen=True)
class ScheduleOutcome:
    """What one weekly beat did. `refused_reason` is set when nothing was attempted."""

    started: int = 0
    existing: int = 0
    skipped_not_allowed: int = 0
    refused_reason: str | None = None


class EvalRunAdminService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        enqueue: EnqueueRun,
        runner: _RunRequester | None = None,
        platform_settings: _SettingsSource | None = None,
        results: _RunStore | None = None,
        config: Settings = settings,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._enqueue = enqueue
        self._runner: _RunRequester = runner or EvalRunService(db)
        self._platform: _SettingsSource = platform_settings or PlatformSettingsService(db)
        self._results: _RunStore = results or EvalResultsService(db)
        self._config = config
        self._clock = clock

    async def request_manual_run(
        self,
        *,
        task: str,
        window_start: datetime | None,
        window_end: datetime | None,
        seed: str | None,
        requested_by: uuid.UUID,
    ) -> tuple[EvalRun, bool]:
        """Create (or find) a manual run and enqueue it when new: `(run, created)`.

        Omitted bounds default to the saved window length ending now; an omitted seed is generated,
        so each such call is a new run. Raises EvalRunRequestError (invalid / not allowed) and
        EnqueueFailedError (run created, worker unreachable; re-submitting the same seed will NOT
        re-enqueue, so use a new seed).
        """
        eval_settings = await self._platform.get_eval_settings()
        end = window_end or self._clock()
        start = window_start or end - timedelta(days=eval_settings.window_days)
        self._validate_window(start, end)
        try:
            run, created = await self._runner.request_run(
                task=task,
                window_start=start,
                window_end=end,
                seed=seed or f"{_MANUAL_SEED_PREFIX}{uuid.uuid4().hex[:16]}",
                trigger="manual",
                requested_by=requested_by,
            )
        except RunNotAllowedError as exc:
            logger.info("eval_run.manual_request_refused", requested_by=str(requested_by), task=task)
            raise EvalRunRequestError(_NOT_ALLOWED_MESSAGE) from exc
        except EvalResultsValidationError as exc:
            raise EvalRunRequestError(str(exc)) from exc
        if created:
            self._enqueue_or_raise(run)
        return run, created

    async def list_runs(self, *, page: int, page_size: int) -> tuple[list[EvalRun], int]:
        if page < 1 or not 1 <= page_size <= MAX_RUNS_PAGE_SIZE:
            raise EvalRunRequestError(f"page must be >= 1 and page_size between 1 and {MAX_RUNS_PAGE_SIZE}")
        return await self._results.list_runs(page=page, page_size=page_size)

    async def get_run(self, run_id: uuid.UUID) -> EvalRun | None:
        return await self._results.get_run(run_id)

    async def schedule_weekly_runs(self) -> ScheduleOutcome:
        """The weekly beat: one `scheduled` run per enabled task, enqueued. Starts nothing when the
        budget is 0, no task is enabled or no judge is configured."""
        eval_settings = await self._platform.get_eval_settings()
        if eval_settings.monthly_budget_usd <= 0:
            logger.warning("eval_schedule.skipped", reason="budget_zero")
            return ScheduleOutcome(refused_reason="budget_zero")
        if not self._config.llm_eval_judge_model:
            logger.warning("eval_schedule.skipped", reason="judge_unset")
            return ScheduleOutcome(refused_reason="judge_unset")
        if not eval_settings.enabled_tasks:
            logger.info("eval_schedule.skipped", reason="no_tasks_enabled")
            return ScheduleOutcome(refused_reason="no_tasks_enabled")

        start, end, seed = scheduled_window_and_seed(self._clock(), window_days=eval_settings.window_days)
        started = existing = skipped = 0
        for task in sorted(eval_settings.enabled_tasks):
            try:
                run, created = await self._runner.request_run(
                    task=task, window_start=start, window_end=end, seed=seed, trigger="scheduled"
                )
            except RunNotAllowedError:
                skipped += 1
                logger.warning("eval_schedule.task_skipped", task=task, reason="not_allowed")
                continue
            if created or run.status == "pending":
                self._enqueue_or_raise(run)
                started += 1
            else:
                existing += 1
        logger.info("eval_schedule.done", started=started, existing=existing, skipped_not_allowed=skipped)
        return ScheduleOutcome(started=started, existing=existing, skipped_not_allowed=skipped)

    def _enqueue_or_raise(self, run: EvalRun) -> None:
        try:
            self._enqueue(run.id)
        except Exception as exc:  # broker errors vary by transport; the cause is logged, never returned
            logger.error("eval_run.enqueue_failed", run_id=str(run.id), error_type=type(exc).__name__)
            raise EnqueueFailedError("could not enqueue the evaluation run") from exc

    @staticmethod
    def _validate_window(start: datetime, end: datetime) -> None:
        if start.tzinfo is None or end.tzinfo is None:
            raise EvalRunRequestError("window bounds must include a timezone")
        if end <= start:
            raise EvalRunRequestError("window end must be after window start")
        if (end - start).days > MAX_WINDOW_DAYS:
            raise EvalRunRequestError(f"window must not exceed {MAX_WINDOW_DAYS} days")
