"""Production-evaluation runs and their per-check results (MLH-T18).

`eval_runs` records one evaluation of one task over one sampled window; `eval_results`
records one check outcome for one sampled `llm_usage_events` row.

RESULTS NEVER HOLD TEXT (decision D9). A result is a metric plus the id of the usage event it
was computed from; the prompt/response text stays in `llm_usage_events`, where the Kaihle Admin
LLM Logs viewer already controls access to it. Judge `evidence` is deliberately not stored
because it can quote a student. A test pins the column set so this cannot drift unnoticed.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

EVAL_RUN_STATUSES = ("pending", "running", "completed", "failed", "budget_exhausted", "empty")
EVAL_RUN_TRIGGERS = ("manual", "scheduled")
EVAL_CHECK_KINDS = ("deterministic", "judge")
# Only rubrics trusted (or explicitly opted-in as indicative, D6) ever run on production
# data, so only these statuses can appear on a stored judge result.
EVAL_RUBRIC_STATUSES = ("CALIBRATED", "HUMAN_VALIDATED", "INDICATIVE")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class EvalRun(Base, UUIDMixin):
    """One production evaluation of one task over one sampled window.

    NO `school_id` (CONSTITUTION Rule 2 deviation, MLH-T18 decision D13, approved by Vibhu
    2026-10-11). A run samples across schools and is started only by KAIHLE_ADMIN or the
    weekly beat; there is no school to scope it to. Per-school attribution lives on
    `eval_results.school_id`. Do not add a `school_id` here.

    Idempotency (D12): `(task, window_start, window_end, seed)` is unique, so a retried or
    double-submitted run cannot create a second copy.
    """

    __tablename__ = "eval_runs"

    # A key of router.TASK_MODEL_MAP (same convention as llm_usage_events.task, not an enum).
    task: Mapped[str] = mapped_column(String(50), nullable=False)
    window_start: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    # Seeds the stable ordering that makes the sample reproducible (D11).
    seed: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    include_indicative: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")

    # The judge model resolved at run start (an env-driven value, recorded for
    # reproducibility). NULL until the run starts: a pending run has not resolved one yet.
    judge_model: Mapped[str | None] = mapped_column(String(200))

    sampled_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    evaluated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    skipped_not_independent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    skipped_scrub_failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    skipped_unsupported_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # Judge spend attributed to this run; Numeric (not float) for the same reason as
    # llm_usage_events.estimated_cost_usd. Unpriced calls are counted at the configured
    # worst case by the budget guard (D2), so this is an upper estimate, never zero-by-gap.
    spend_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("0"), server_default="0")

    # Exception class name when status = 'failed'; NULL otherwise.
    error_type: Mapped[str | None] = mapped_column(String(100))

    # NULL = started by the weekly beat, or the requesting admin's account was later
    # deleted (SET NULL keeps the run: the metrics outlive the account).
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    # NULL until the run starts / finishes respectively.
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    # lazy="raise": loading every result of a run is unbounded; callers must query explicitly.
    results: Mapped[list["EvalResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )

    __table_args__ = (
        UniqueConstraint("task", "window_start", "window_end", "seed", name="uq_eval_runs_task_window_seed"),
        Index("idx_eval_runs_created", "created_at"),
        Index("idx_eval_runs_task_created", "task", "created_at"),
        CheckConstraint(_in_list("status", EVAL_RUN_STATUSES), name="chk_eval_runs_status"),
        CheckConstraint(_in_list("trigger", EVAL_RUN_TRIGGERS), name="chk_eval_runs_trigger"),
        CheckConstraint("length(btrim(seed)) > 0", name="chk_eval_runs_seed_not_blank"),
        CheckConstraint("window_end > window_start", name="chk_eval_runs_window_ordered"),
        CheckConstraint(
            "sampled_count >= 0 AND evaluated_count >= 0 AND skipped_not_independent_count >= 0 "
            "AND skipped_scrub_failed_count >= 0 AND skipped_unsupported_count >= 0",
            name="chk_eval_runs_counts_non_negative",
        ),
        CheckConstraint("spend_usd >= 0", name="chk_eval_runs_spend_non_negative"),
    )


class EvalResult(Base, UUIDMixin):
    """One check outcome for one sampled usage event. Metrics and ids only — no text.

    `school_id` is COPIED from the sampled `llm_usage_events` row when the result is
    written (MLH-T18 D13, Vibhu 2026-10-11): the school's id for school-attributed tasks,
    NULL for batch/curriculum tasks. NULL means exactly what it means on
    `llm_usage_events` — platform-level work, not "unknown school".
      * Origin: `llm_usage_events.school_id` at the moment the result is recorded.
      * Sync: none. It is a point-in-time copy; a later change to the event's school is not
        propagated (events are append-only in practice, so the failure mode is benign).
      * Deleting a school sets it NULL (the metric outlives the school), as on the event.
    """

    __tablename__ = "eval_results"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False
    )
    # NULL = the usage event was purged (e.g. by a future retention job). SET NULL, not
    # CASCADE: the pass/fail metric must outlive the text it was computed from.
    usage_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("llm_usage_events.id", ondelete="SET NULL"), nullable=True
    )
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"), nullable=True
    )

    check_name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)

    # NULL if and only if `indeterminate` (e.g. an unparseable judge verdict). An
    # indeterminate result is never a pass and never a fail; it is counted separately.
    passed: Mapped[bool | None] = mapped_column(nullable=True)
    indeterminate: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")

    # Judge results only (NULL for deterministic checks): the rubric content hash and the
    # calibration status it had at run time, so a result stays interpretable after the
    # rubric is edited or recalibrated.
    rubric_hash: Mapped[str | None] = mapped_column(String(64))
    rubric_status: Mapped[str | None] = mapped_column(String(20))

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    run: Mapped[EvalRun] = relationship(back_populates="results", lazy="raise")

    __table_args__ = (
        # One verdict per check per sampled event per run; also makes result writes retry-safe.
        # NULL usage_event_id (purged event) rows are distinct under this key, by design.
        UniqueConstraint("run_id", "usage_event_id", "check_name", name="uq_eval_results_run_event_check"),
        Index("idx_eval_results_run", "run_id"),
        Index("idx_eval_results_usage_event", "usage_event_id"),
        # Supports the weekly summary (by check over time) and a future per-school view.
        Index("idx_eval_results_created", "created_at"),
        Index("idx_eval_results_school_created", "school_id", "created_at"),
        CheckConstraint("length(btrim(check_name)) > 0", name="chk_eval_results_check_name_not_blank"),
        CheckConstraint(_in_list("kind", EVAL_CHECK_KINDS), name="chk_eval_results_kind"),
        CheckConstraint(
            "(indeterminate AND passed IS NULL) OR (NOT indeterminate AND passed IS NOT NULL)",
            name="chk_eval_results_passed_consistent",
        ),
        CheckConstraint(
            "(kind = 'judge' AND rubric_hash IS NOT NULL AND rubric_status IS NOT NULL) "
            "OR (kind = 'deterministic' AND rubric_hash IS NULL AND rubric_status IS NULL)",
            name="chk_eval_results_rubric_consistent",
        ),
        CheckConstraint(
            f"rubric_status IS NULL OR {_in_list('rubric_status', EVAL_RUBRIC_STATUSES)}",
            name="chk_eval_results_rubric_status",
        ),
    )
