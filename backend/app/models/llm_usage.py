"""Per-call LLM usage and cost telemetry.

`router.py` has always logged token counts and latency, but `app/core/logging.py` renders
to stdout through `PrintLoggerFactory` and there is no log store behind it. On Render that
is a rolling buffer, not a queryable history — so "what did the diagnostic cost?" had no
answer. This table is that answer.

Written by `app/ai/usage_sink.py` on every LLM call. Telemetry never blocks inference: a
failed insert here is logged and swallowed, never raised.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class LlmUsageEvent(Base, UUIDMixin):
    """One LLM provider call — what it cost, how long it took, and who caused it.

    NO `school_id` REQUIREMENT (CONSTITUTION Rule 2 deviation, approved by Vibhu
    2026-09-07). The column exists but is nullable, because a large share of LLM spend has
    no school to attribute it to: curriculum-wide question generation, quality validation,
    remap adjudication, and mini-course content generated at `scope='curriculum'` are all
    platform-level work. NULL means exactly that — platform-level, not "unknown school".

    Precedent: `lo_review_items` carries no `school_id` at all, for the same reason.

    Do not "fix" this to NOT NULL. Doing so would force every offline script to invent a
    school id, which is worse than an honest NULL.
    """

    __tablename__ = "llm_usage_events"

    # A key of router.TASK_MODEL_MAP. Not an enum: adding a task type is a routine change
    # and an enum migration for each would be friction with no safety gain here.
    task: Mapped[str] = mapped_column(String(50), nullable=False)

    # The resolved model string as sent to the provider. Stored, never hardcoded — model
    # names are env-driven and this column is the only place they are written down.
    model: Mapped[str] = mapped_column(String(200), nullable=False)

    # Which code path issued the call: "api:<route>", "celery:<task>", "script:<name>".
    # `task` alone is not enough — only question_quality has a single caller. Without this,
    # interactive student traffic and offline batch runs are indistinguishable, and
    # smoke-test spend counts as production.
    #
    # Nullable: a call from an unwrapped path records NULL rather than failing. The cost
    # report surfaces the NULL share so a missed path is visible rather than hidden.
    component: Mapped[str | None] = mapped_column(String(80))

    # Groups one batch-script invocation, so a whole remap run costs one number rather than
    # a date-range guess.
    run_id: Mapped[str | None] = mapped_column(String(64))

    # NULL when the provider did not report usage. Streaming responses are the common case:
    # not every provider honours stream_options.include_usage.
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)

    # Full prompt/response text, for the LLM Logs admin viewer's per-call detail. NULL
    # for every row written before this column existed, and for a streamed call whose
    # provider dropped the connection before the response was fully assembled — captured
    # best-effort, same tolerance as prompt_tokens/completion_tokens above. Stored raw, no
    # masking or truncation (explicit product decision 2026-09-09): this table already
    # carries real student/teacher content whenever it flows through a prompt, and the
    # page is KAIHLE_ADMIN-only, same trust boundary as every other admin-only view here.
    prompt_text: Mapped[str | None] = mapped_column(Text)
    response_text: Mapped[str | None] = mapped_column(Text)

    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    # NULL when the model is not priceable. Never guessed and never borrowed from another
    # model — a wrong cost figure is worse than a missing one, because it looks like data.
    # Numeric, not float: costs are summed across millions of rows and binary floating point
    # drifts. 6dp because per-call costs are frequently in the 1e-5 range.
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))

    streamed: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    succeeded: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")

    # Exception class name when succeeded is false. Failed calls cost money and time too,
    # and a report that counts only successes understates spend.
    error_type: Mapped[str | None] = mapped_column(String(100))

    error_detail: Mapped[str | None] = mapped_column(Text)

    # From structlog contextvars — ties a call back to the request or job that caused it.
    correlation_id: Mapped[str | None] = mapped_column(String(64))

    # Bound from the JWT by RequestLoggingMiddleware, so a call made while serving a student
    # is attributable to their school. Batch scripts and curriculum-scope work bind nothing,
    # which is what makes NULL mean "platform-level" rather than "we forgot". See the class
    # docstring. SET NULL rather than CASCADE: deleting a school must not erase the record
    # that its work was performed and paid for.
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        # Every report groups by one of these and filters by date, so each index leads with
        # the grouping column and ends with the range scan.
        Index("idx_llm_usage_task_created", "task", "created_at"),
        Index("idx_llm_usage_component_created", "component", "created_at"),
        Index("idx_llm_usage_model_created", "model", "created_at"),
        Index("idx_llm_usage_created", "created_at"),
        Index("idx_llm_usage_run", "run_id"),
        CheckConstraint("latency_ms >= 0", name="chk_llm_usage_latency_non_negative"),
        CheckConstraint(
            "estimated_cost_usd IS NULL OR estimated_cost_usd >= 0",
            name="chk_llm_usage_cost_non_negative",
        ),
        # A failed call has an error_type; a successful one does not claim an error.
        CheckConstraint(
            "(succeeded = true AND error_type IS NULL) OR (succeeded = false AND error_type IS NOT NULL)",
            name="chk_llm_usage_error_consistent",
        ),
    )
