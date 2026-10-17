"""Persistence of production-evaluation runs and results (MLH-T18).

Storage access only: no sampling, scrubbing, judging or budgeting lives here (later slices).
Every public method writes (or reads) in its own transaction and commits.

DESIGN DECISIONS
  * Results hold metrics and ids only (D9). `CheckOutcome` has no text field, so a caller
    cannot pass text through this service even by mistake.
  * `school_id` on a result is copied from the usage event inside `record_results`, so no
    caller can attribute a result to a different school than its event (D13).
  * Idempotent writes (rules 04): `create_run` returns the existing run for the same
    `(task, window, seed)`; `record_results` ignores a verdict already stored for the same
    `(run, event, check)`.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.eval_results import (
    EVAL_CHECK_KINDS,
    EVAL_RUBRIC_STATUSES,
    EVAL_RUN_TRIGGERS,
    EvalResult,
    EvalRun,
)
from app.models.llm_usage import LlmUsageEvent

logger = structlog.get_logger()

# Statuses a run may finish in. "pending"/"running" are reached via create_run/mark_started.
TERMINAL_STATUSES = frozenset({"completed", "failed", "budget_exhausted", "empty"})


class EvalResultsValidationError(ValueError):
    """The submitted run or result breaks a rule. Raised before the database is touched."""


@dataclass(frozen=True)
class CheckOutcome:
    """One check's verdict on one sampled event. `passed=None` means indeterminate."""

    check_name: str
    kind: str
    passed: bool | None
    rubric_hash: str | None = None
    rubric_status: str | None = None


@dataclass(frozen=True)
class RunCounts:
    sampled: int = 0
    evaluated: int = 0
    skipped_not_independent: int = 0
    skipped_scrub_failed: int = 0
    skipped_unsupported: int = 0


def _validate_outcome(outcome: CheckOutcome) -> None:
    if not outcome.check_name.strip():
        raise EvalResultsValidationError("check name must not be blank")
    if outcome.kind not in EVAL_CHECK_KINDS:
        raise EvalResultsValidationError(f"unknown check kind {outcome.kind!r}")
    has_rubric = outcome.rubric_hash is not None and outcome.rubric_status is not None
    no_rubric = outcome.rubric_hash is None and outcome.rubric_status is None
    if outcome.kind == "judge" and not has_rubric:
        raise EvalResultsValidationError("judge results must carry a rubric hash and status")
    if outcome.kind == "deterministic" and not no_rubric:
        raise EvalResultsValidationError("deterministic results must not carry a rubric hash or status")
    if outcome.rubric_status is not None and outcome.rubric_status not in EVAL_RUBRIC_STATUSES:
        raise EvalResultsValidationError(f"rubric status {outcome.rubric_status!r} is not storable")


class EvalResultsService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_run(
        self,
        *,
        task: str,
        window_start: datetime,
        window_end: datetime,
        seed: str,
        trigger: str,
        requested_by: uuid.UUID | None = None,
        include_indicative: bool = False,
    ) -> tuple[EvalRun, bool]:
        """Create a pending run, or return the existing one for the same (task, window, seed).

        Returns `(run, created)`. Race-safe: a concurrent duplicate loses on the unique key
        (ON CONFLICT DO NOTHING) and receives the winner's row.
        """
        if trigger not in EVAL_RUN_TRIGGERS:
            raise EvalResultsValidationError(f"unknown trigger {trigger!r}")
        if not seed.strip():
            raise EvalResultsValidationError("seed must not be blank")
        if window_end <= window_start:
            raise EvalResultsValidationError("window end must be after window start")

        inserted = await self._db.execute(
            pg_insert(EvalRun)
            .values(
                id=uuid.uuid4(),
                task=task,
                window_start=window_start,
                window_end=window_end,
                seed=seed,
                trigger=trigger,
                requested_by=requested_by,
                include_indicative=include_indicative,
            )
            .on_conflict_do_nothing(constraint="uq_eval_runs_task_window_seed")
            .returning(EvalRun.id)
        )
        created = inserted.scalar_one_or_none() is not None
        found = await self._db.execute(
            select(EvalRun).where(
                EvalRun.task == task,
                EvalRun.window_start == window_start,
                EvalRun.window_end == window_end,
                EvalRun.seed == seed,
            )
        )
        run = found.scalar_one()
        await self._db.commit()
        if created:
            logger.info("eval_run.created", run_id=str(run.id), task=task, trigger=trigger)
        return run, created

    async def get_run(self, run_id: uuid.UUID) -> EvalRun | None:
        # populate_existing: a run finished through UPDATE statements must not be served stale
        # from the session's identity map.
        result = await self._db.execute(
            select(EvalRun).where(EvalRun.id == run_id).execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def mark_started(self, run_id: uuid.UUID, *, judge_model: str) -> None:
        """pending -> running, recording the resolved judge model. LookupError if not pending."""
        result = await self._db.execute(
            update(EvalRun)
            .where(EvalRun.id == run_id, EvalRun.status == "pending")
            .values(status="running", judge_model=judge_model, started_at=datetime.now(UTC))
            .returning(EvalRun.id)
        )
        await self._commit_or_raise(result.scalar_one_or_none(), f"eval run {run_id} not found or not pending")

    async def finish_run(
        self,
        run_id: uuid.UUID,
        *,
        status: str,
        counts: RunCounts,
        spend_usd: Decimal,
        error_type: str | None = None,
    ) -> None:
        """Record a run's terminal status, counters and spend. LookupError if the run is missing."""
        if status not in TERMINAL_STATUSES:
            raise EvalResultsValidationError(f"{status!r} is not a terminal run status")
        result = await self._db.execute(
            update(EvalRun)
            .where(EvalRun.id == run_id)
            .values(
                status=status,
                sampled_count=counts.sampled,
                evaluated_count=counts.evaluated,
                skipped_not_independent_count=counts.skipped_not_independent,
                skipped_scrub_failed_count=counts.skipped_scrub_failed,
                skipped_unsupported_count=counts.skipped_unsupported,
                spend_usd=spend_usd,
                error_type=error_type,
                completed_at=datetime.now(UTC),
            )
            .returning(EvalRun.id)
        )
        await self._commit_or_raise(result.scalar_one_or_none(), f"eval run {run_id} not found")
        logger.info(
            "eval_run.finished",
            run_id=str(run_id),
            status=status,
            evaluated=counts.evaluated,
            sampled=counts.sampled,
            spend_usd=str(spend_usd),
            error_type=error_type,
        )

    async def record_results(
        self, run_id: uuid.UUID, usage_event_id: uuid.UUID, outcomes: Sequence[CheckOutcome]
    ) -> int:
        """Store the outcomes for one sampled event; returns how many rows were newly written.

        Copies the event's `school_id` onto every row (NULL for platform-level events).
        Outcomes already stored for the same (run, event, check) are ignored, so a retry is
        safe. Raises LookupError if the event does not exist.
        """
        if not outcomes:
            return 0
        for outcome in outcomes:
            _validate_outcome(outcome)

        event = await self._db.execute(select(LlmUsageEvent.school_id).where(LlmUsageEvent.id == usage_event_id))
        row = event.one_or_none()
        if row is None:
            raise LookupError(f"usage event {usage_event_id} not found")

        inserted = await self._db.execute(
            pg_insert(EvalResult)
            .values(
                [
                    {
                        "id": uuid.uuid4(),
                        "run_id": run_id,
                        "usage_event_id": usage_event_id,
                        "school_id": row[0],
                        "check_name": o.check_name,
                        "kind": o.kind,
                        "passed": o.passed,
                        "indeterminate": o.passed is None,
                        "rubric_hash": o.rubric_hash,
                        "rubric_status": o.rubric_status,
                    }
                    for o in outcomes
                ]
            )
            .on_conflict_do_nothing(constraint="uq_eval_results_run_event_check")
            .returning(EvalResult.id)
        )
        written = len(inserted.all())
        await self._db.commit()
        return written

    async def _commit_or_raise(self, found: uuid.UUID | None, message: str) -> None:
        if found is None:
            await self._db.rollback()
            raise LookupError(message)
        await self._db.commit()
