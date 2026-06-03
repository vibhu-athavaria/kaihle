"""add_question_review_items_and_teacher_source_to_question_bank

Revision ID: dc843fdf3ba3
Revises: f892502b0975
Create Date: 2026-06-01 10:47:54.971741

Changes:
- question_bank: add school_id, submitted_by, review_status columns
- question_bank: widen chk_qb_source to include 'teacher'
- question_bank: add chk_qb_review_status CHECK constraint
- New table: question_review_items (unified review queue for teacher questions + edit suggestions)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "dc843fdf3ba3"
down_revision: str | Sequence[str] | None = "f892502b0975"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── question_bank: widen source CHECK to include 'teacher' ──────────────
    # Alembic cannot diff CHECK constraint text — must be done manually.
    op.drop_constraint("chk_qb_source", "question_bank", type_="check")
    op.create_check_constraint(
        "chk_qb_source",
        "question_bank",
        "source IN ('bank', 'llm', 'teacher')",
    )

    # ── question_bank: add teacher-submission columns ────────────────────────
    op.add_column("question_bank", sa.Column("school_id", sa.UUID(), nullable=True))
    op.add_column("question_bank", sa.Column("submitted_by", sa.UUID(), nullable=True))
    op.add_column("question_bank", sa.Column("review_status", sa.String(length=20), nullable=True))
    op.create_foreign_key(
        "fk_qb_school",
        "question_bank",
        "schools",
        ["school_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_qb_submitted_by",
        "question_bank",
        "users",
        ["submitted_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "chk_qb_review_status",
        "question_bank",
        "review_status IS NULL OR review_status IN ('PENDING_REVIEW', 'APPROVED', 'REJECTED')",
    )
    op.create_index(
        "idx_qb_school",
        "question_bank",
        ["school_id"],
        postgresql_where=sa.text("school_id IS NOT NULL"),
    )

    # ── question_review_items: unified review queue ──────────────────────────
    op.create_table(
        "question_review_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("item_type", sa.String(length=20), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("submitted_by", sa.UUID(), nullable=False),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column("assessment_id", sa.UUID(), nullable=True),
        sa.Column("suggested_question_text", sa.Text(), nullable=True),
        sa.Column(
            "suggested_options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("suggested_correct_answer", sa.Text(), nullable=True),
        sa.Column("suggested_explanation", sa.Text(), nullable=True),
        sa.Column("suggested_difficulty_level", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.UUID(), nullable=True),
        sa.Column("resolved_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "item_type IN ('TEACHER_QUESTION', 'EDIT_SUGGESTION')",
            name="chk_qri_item_type",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="chk_qri_status",
        ),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["question_id"], ["question_bank.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_qri_item_type", "question_review_items", ["item_type"])
    op.create_index("idx_qri_school", "question_review_items", ["school_id"])
    op.create_index(
        "idx_qri_status",
        "question_review_items",
        ["status"],
        postgresql_where=sa.text("status = 'PENDING'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # ── question_review_items ────────────────────────────────────────────────
    op.drop_index("idx_qri_status", table_name="question_review_items")
    op.drop_index("idx_qri_school", table_name="question_review_items")
    op.drop_index("idx_qri_item_type", table_name="question_review_items")
    op.drop_table("question_review_items")

    # ── question_bank: remove teacher-submission columns ─────────────────────
    op.drop_index("idx_qb_school", table_name="question_bank")
    op.drop_constraint("chk_qb_review_status", "question_bank", type_="check")
    op.drop_constraint("fk_qb_submitted_by", "question_bank", type_="foreignkey")
    op.drop_constraint("fk_qb_school", "question_bank", type_="foreignkey")
    op.drop_column("question_bank", "review_status")
    op.drop_column("question_bank", "submitted_by")
    op.drop_column("question_bank", "school_id")

    # ── question_bank: restore original source CHECK ─────────────────────────
    op.drop_constraint("chk_qb_source", "question_bank", type_="check")
    op.create_check_constraint(
        "chk_qb_source",
        "question_bank",
        "source IN ('bank', 'llm')",
    )
