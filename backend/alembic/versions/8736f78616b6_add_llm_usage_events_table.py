"""add llm_usage_events table

Revision ID: 8736f78616b6
Revises: 94eca178e453
Create Date: 2026-09-07 16:23:16.262332

MLH-T2. Per-call LLM usage and cost telemetry.

`router.py` has always logged token counts, but `core/logging.py` renders to stdout via
PrintLoggerFactory with no store behind it, so the history was not queryable. This table is
where "what did the diagnostic cost?" gets answered.

TWO NOTES FOR REVIEWERS
-----------------------
1. `school_id` IS NULLABLE — a deliberate CONSTITUTION Rule 2 deviation, approved by Vibhu
   on 2026-09-07. A large share of LLM spend has no school: curriculum-wide question
   generation, quality validation, remap adjudication, and mini-course content generated at
   scope='curriculum'. NULL means "platform-level work", not "unknown school". Precedent:
   `lo_review_items` carries no school_id at all. Do not "fix" this to NOT NULL.

2. THIS MIGRATION WAS TRIMMED AFTER AUTOGENERATION. `alembic revision --autogenerate`
   additionally proposed dropping table comments from 33 unrelated tables (`assessments`,
   `users`, `schools`, ...). That is pre-existing drift between the ORM models, which do not
   declare `comment=`, and the database, which has comments from the original SQL schema. It
   predates this task, and applying it would delete schema documentation for reasons
   unrelated to LLM telemetry. Those operations were removed by hand; only the new table
   remains. The drift is real and should be addressed on its own terms.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8736f78616b6"
down_revision: str | Sequence[str] | None = "94eca178e453"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create llm_usage_events."""
    op.create_table(
        "llm_usage_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("task", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("component", sa.String(length=80), nullable=True),
        sa.Column("run_id", sa.String(length=64), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        # Numeric, not float: summed over millions of rows, and binary floating point drifts.
        sa.Column("estimated_cost_usd", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("streamed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("succeeded", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("error_type", sa.String(length=100), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("school_id", sa.UUID(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("latency_ms >= 0", name="chk_llm_usage_latency_non_negative"),
        sa.CheckConstraint(
            "estimated_cost_usd IS NULL OR estimated_cost_usd >= 0",
            name="chk_llm_usage_cost_non_negative",
        ),
        # A failed call names its error; a successful one does not claim one.
        sa.CheckConstraint(
            "(succeeded = true AND error_type IS NULL) OR (succeeded = false AND error_type IS NOT NULL)",
            name="chk_llm_usage_error_consistent",
        ),
        # SET NULL, not CASCADE: deleting a school must not erase the record that its work
        # was performed and paid for.
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table_comment(
        "llm_usage_events",
        "Per-call LLM usage and cost telemetry. school_id is nullable by design — "
        "platform-level work (curriculum generation, remap adjudication) has no school.",
        schema=None,
    )
    # Every report groups by one of these and filters by date, so each index leads with the
    # grouping column and ends with the range scan.
    op.create_index("idx_llm_usage_task_created", "llm_usage_events", ["task", "created_at"], unique=False)
    op.create_index("idx_llm_usage_component_created", "llm_usage_events", ["component", "created_at"], unique=False)
    op.create_index("idx_llm_usage_model_created", "llm_usage_events", ["model", "created_at"], unique=False)
    op.create_index("idx_llm_usage_created", "llm_usage_events", ["created_at"], unique=False)
    op.create_index("idx_llm_usage_run", "llm_usage_events", ["run_id"], unique=False)


def downgrade() -> None:
    """Drop llm_usage_events.

    Telemetry only — nothing reads this table as a source of truth for application
    behaviour, so dropping it loses history but breaks nothing.
    """
    op.drop_index("idx_llm_usage_run", table_name="llm_usage_events")
    op.drop_index("idx_llm_usage_created", table_name="llm_usage_events")
    op.drop_index("idx_llm_usage_model_created", table_name="llm_usage_events")
    op.drop_index("idx_llm_usage_component_created", table_name="llm_usage_events")
    op.drop_index("idx_llm_usage_task_created", table_name="llm_usage_events")
    op.drop_table("llm_usage_events")
