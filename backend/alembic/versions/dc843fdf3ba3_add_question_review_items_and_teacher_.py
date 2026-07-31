"""add_question_review_items_and_teacher_source_to_question_bank

Revision ID: dc843fdf3ba3
Revises: f892502b0975
Create Date: 2026-06-01 10:47:54.971741

Changes:
- question_bank: add school_id, submitted_by, review_status columns (idempotent)
- question_bank: widen chk_qb_source to include 'teacher' and 'llm-correction'
- question_bank: add chk_qb_review_status CHECK constraint (idempotent)
- New table: question_review_items (unified review queue for teacher questions + edit suggestions)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision: str = "dc843fdf3ba3"
down_revision: str | Sequence[str] | None = "f892502b0975"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(conn: Connection, table: str, column: str) -> bool:
    """Check if a column exists in the given table."""
    insp = inspect(conn)
    return any(c["name"] == column for c in insp.get_columns(table))


def _has_constraint(conn: Connection, table: str, constraint: str) -> bool:
    """Check if a named constraint exists on the given table."""
    insp = inspect(conn)
    for chk in insp.get_check_constraints(table):
        if chk["name"] == constraint:
            return True
    return False


def _has_fk(conn: Connection, table: str, fk_name: str) -> bool:
    """Check if a named foreign key exists on the given table."""
    insp = inspect(conn)
    for fk in insp.get_foreign_keys(table):
        if fk.get("name") == fk_name:
            return True
    return False


def _has_index(conn: Connection, table: str, index: str) -> bool:
    """Check if a named index exists."""
    insp = inspect(conn)
    for idx in insp.get_indexes(table):
        if idx["name"] == index:
            return True
    return False


def _has_table(conn: Connection, table: str) -> bool:
    """Check if a table exists."""
    insp = inspect(conn)
    return insp.has_table(table)


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    # ── question_bank: widen source CHECK to include 'teacher' and 'llm-correction' ─
    # Alembic cannot diff CHECK constraint text — must be done manually.
    if _has_constraint(conn, "question_bank", "chk_qb_source"):
        op.drop_constraint("chk_qb_source", "question_bank", type_="check")
    op.create_check_constraint(
        "chk_qb_source",
        "question_bank",
        "source IN ('bank', 'llm', 'llm-correction', 'teacher')",
    )

    # ── question_bank: add teacher-submission columns (idempotent) ────────────
    if not _has_column(conn, "question_bank", "school_id"):
        op.add_column("question_bank", sa.Column("school_id", sa.UUID(), nullable=True))
    if not _has_column(conn, "question_bank", "submitted_by"):
        op.add_column("question_bank", sa.Column("submitted_by", sa.UUID(), nullable=True))
    if not _has_column(conn, "question_bank", "review_status"):
        op.add_column("question_bank", sa.Column("review_status", sa.String(length=20), nullable=True))

    if not _has_fk(conn, "question_bank", "fk_qb_school"):
        op.create_foreign_key(
            "fk_qb_school",
            "question_bank",
            "schools",
            ["school_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    if not _has_fk(conn, "question_bank", "fk_qb_submitted_by"):
        op.create_foreign_key(
            "fk_qb_submitted_by",
            "question_bank",
            "users",
            ["submitted_by"],
            ["id"],
            ondelete="SET NULL",
        )

    if not _has_constraint(conn, "question_bank", "chk_qb_review_status"):
        op.create_check_constraint(
            "chk_qb_review_status",
            "question_bank",
            "review_status IS NULL OR review_status IN ('PENDING_REVIEW', 'APPROVED', 'REJECTED')",
        )

    if not _has_index(conn, "question_bank", "idx_qb_school"):
        op.create_index(
            "idx_qb_school",
            "question_bank",
            ["school_id"],
            postgresql_where=sa.text("school_id IS NOT NULL"),
        )

    # ── question_review_items: unified review queue ──────────────────────────
    if not _has_table(conn, "question_review_items"):
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
        # Prevent duplicate PENDING review items for the same question+type
        # Uses a partial unique INDEX because PostgreSQL does not support
        # postgresql_where on UniqueConstraint.
        if not _has_index(conn, "question_review_items", "uq_qri_pending_question_type"):
            op.create_index(
                "uq_qri_pending_question_type",
                "question_review_items",
                ["question_id", "item_type"],
                unique=True,
                postgresql_where=sa.text("status = 'PENDING'"),
            )


def downgrade() -> None:
    """Downgrade schema."""
    # ── question_review_items ────────────────────────────────────────────────
    conn = op.get_bind()
    if _has_index(conn, "question_review_items", "uq_qri_pending_question_type"):
        op.drop_index("uq_qri_pending_question_type", table_name="question_review_items")
    op.drop_index("idx_qri_status", table_name="question_review_items")
    op.drop_index("idx_qri_school", table_name="question_review_items")
    op.drop_index("idx_qri_item_type", table_name="question_review_items")
    op.drop_table("question_review_items")

    # ── question_bank: remove teacher-submission columns ─────────────────────
    conn = op.get_bind()
    if _has_index(conn, "question_bank", "idx_qb_school"):
        op.drop_index("idx_qb_school", table_name="question_bank")
    if _has_constraint(conn, "question_bank", "chk_qb_review_status"):
        op.drop_constraint("chk_qb_review_status", "question_bank", type_="check")
    if _has_fk(conn, "question_bank", "fk_qb_submitted_by"):
        op.drop_constraint("fk_qb_submitted_by", "question_bank", type_="foreignkey")
    if _has_fk(conn, "question_bank", "fk_qb_school"):
        op.drop_constraint("fk_qb_school", "question_bank", type_="foreignkey")
    if _has_column(conn, "question_bank", "review_status"):
        op.drop_column("question_bank", "review_status")
    if _has_column(conn, "question_bank", "submitted_by"):
        op.drop_column("question_bank", "submitted_by")
    if _has_column(conn, "question_bank", "school_id"):
        op.drop_column("question_bank", "school_id")

    # ── question_bank: restore original source CHECK ─────────────────────────
    if _has_constraint(conn, "question_bank", "chk_qb_source"):
        op.drop_constraint("chk_qb_source", "question_bank", type_="check")
    op.create_check_constraint(
        "chk_qb_source",
        "question_bank",
        "source IN ('bank', 'llm')",
    )
