"""add lo_review_items for curriculum mapping review

Revision ID: 1470d92f4cbc
Revises: 3670a6fac36d
Create Date: 2026-08-03 13:59:57.797948

Queue of curriculum-mapping decisions awaiting human judgement, produced by the remap
pipeline wherever automated matching is inconclusive.

No school_id: these are curriculum-level rulings that apply to every school, which is
also why question_review_items cannot be reused (it is NOT NULL on school_id and
submitted_by). Constitution Rule 2 exempts curriculum tables.

NOTE: autogenerate against a production-restored database also proposed creating
question_review_items and re-emitting table comments. Both were removed. The missing
question_review_items table is genuine PRODUCTION SCHEMA DRIFT — migration
dc843fdf3ba3 is an ancestor of the recorded version 8a1b2c3d4e5f, yet the table does
not exist — and repairing that is a separate change, not something to smuggle into a
feature migration where it would fail on every environment that does have the table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1470d92f4cbc"
down_revision: str | Sequence[str] | None = "3670a6fac36d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "lo_review_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("item_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("source_code", sa.String(length=100), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=True),
        sa.Column("source_learning_objective", sa.Text(), nullable=False),
        sa.Column("subject_code", sa.String(length=20), nullable=True),
        sa.Column("grade_level", sa.Integer(), nullable=True),
        sa.Column("question_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("question_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("llm_suggested_code", sa.String(length=50), nullable=True),
        sa.Column("llm_reason", sa.Text(), nullable=True),
        sa.Column("chosen_objective_id", sa.UUID(), nullable=True),
        sa.Column("resolved_by", sa.UUID(), nullable=True),
        sa.Column("resolved_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["chosen_objective_id"],
            ["learning_objectives.id"],
            name="fk_lo_review_items_chosen_objective_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"],
            ["users.id"],
            name="fk_lo_review_items_resolved_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        # One open decision per source: re-running the remap must update the existing
        # item rather than stack duplicates in front of the reviewer.
        sa.UniqueConstraint("item_type", "source_code", name="uq_lo_review_item_source"),
    )
    op.create_index(op.f("ix_lo_review_items_item_type"), "lo_review_items", ["item_type"], unique=False)
    op.create_index(op.f("ix_lo_review_items_status"), "lo_review_items", ["status"], unique=False)

    # CHECK constraints are never emitted by autogenerate — added to match the model.
    op.create_check_constraint(
        "chk_lo_review_item_type",
        "lo_review_items",
        "item_type IN ('QUESTION_REMAP', 'OBJECTIVE_DEDUP')",
    )
    op.create_check_constraint(
        "chk_lo_review_status",
        "lo_review_items",
        "status IN ('PENDING', 'APPROVED', 'REJECTED')",
    )
    # An approved item must record what it approved; a pending one must not claim to.
    op.create_check_constraint(
        "chk_lo_review_resolution_consistent",
        "lo_review_items",
        "(status = 'APPROVED' AND chosen_objective_id IS NOT NULL) OR "
        "(status <> 'APPROVED' AND (status <> 'PENDING' OR chosen_objective_id IS NULL))",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_lo_review_items_status"), table_name="lo_review_items")
    op.drop_index(op.f("ix_lo_review_items_item_type"), table_name="lo_review_items")
    op.drop_table("lo_review_items")
