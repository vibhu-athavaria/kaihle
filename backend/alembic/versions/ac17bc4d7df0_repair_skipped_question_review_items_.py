"""repair skipped question_review_items migration in production

Revision ID: ac17bc4d7df0
Revises: 1470d92f4cbc
Create Date: 2026-08-03 14:48:48.216581

Production is missing everything migration dc843fdf3ba3 was supposed to create, even
though its recorded version (8a1b2c3d4e5f) is four revisions PAST that migration.
Confirmed against a production restore:

    question_bank.school_id             MISSING
    question_bank.submitted_by          MISSING
    question_bank.review_status         MISSING
    question_review_items               MISSING
    chk_qb_source                       lacks 'teacher'
    question_bank.replaces_question_id  PRESENT  <- from 5d1bdf1ec743, the NEXT migration

One migration's effects absent while the following migration's are present is the
signature of a revision being STAMPED rather than executed. It is not a missed deploy:
prod ran past it. dc843fdf3ba3 is itself fully guarded with _has_table/_has_column
checks, so had it run at all it would have created these objects.

Impact: the ORM declares columns the database does not have, so select(QuestionBank)
raises UndefinedColumnError. Every endpoint loading a question row through the ORM is
failing in production — not only the teacher-submission feature. It went unnoticed
because production has no active users.

This migration re-applies dc843fdf3ba3's operations. Every step is existence-guarded,
so it is a no-op wherever that migration ran correctly (dev, CI, test) and repairs only
the environments where it did not.

The operations are spelled out here rather than imported from dc843fdf3ba3: migrations
must be immutable and self-contained, and a later edit to that file must not silently
change what this repair does.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision: str = "ac17bc4d7df0"
down_revision: str | Sequence[str] | None = "1470d92f4cbc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(conn: Connection, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspect(conn).get_columns(table))


def _has_constraint(conn: Connection, table: str, constraint: str) -> bool:
    return any(chk["name"] == constraint for chk in inspect(conn).get_check_constraints(table))


def _has_fk(conn: Connection, table: str, fk_name: str) -> bool:
    return any(fk.get("name") == fk_name for fk in inspect(conn).get_foreign_keys(table))


def _has_index(conn: Connection, table: str, index: str) -> bool:
    return any(idx["name"] == index for idx in inspect(conn).get_indexes(table))


def _has_table(conn: Connection, table: str) -> bool:
    return inspect(conn).has_table(table)


def upgrade() -> None:
    """Re-apply dc843fdf3ba3. No-op where that migration ran correctly."""
    conn = op.get_bind()

    # chk_qb_source must allow 'teacher'. Alembic cannot diff CHECK text, so this is
    # rewritten unconditionally — dropping and recreating an identical constraint is
    # harmless, and comparing the text by hand is not worth the fragility.
    if _has_constraint(conn, "question_bank", "chk_qb_source"):
        op.drop_constraint("chk_qb_source", "question_bank", type_="check")
    op.create_check_constraint(
        "chk_qb_source",
        "question_bank",
        "source IN ('bank', 'llm', 'llm-correction', 'teacher')",
    )

    # Teacher-submission columns. NULL for bank/llm questions, which is why they can be
    # added to a populated table without a backfill.
    if not _has_column(conn, "question_bank", "school_id"):
        op.add_column("question_bank", sa.Column("school_id", sa.UUID(), nullable=True))
    if not _has_column(conn, "question_bank", "submitted_by"):
        op.add_column("question_bank", sa.Column("submitted_by", sa.UUID(), nullable=True))
    if not _has_column(conn, "question_bank", "review_status"):
        op.add_column("question_bank", sa.Column("review_status", sa.String(length=20), nullable=True))

    if not _has_fk(conn, "question_bank", "fk_qb_school"):
        op.create_foreign_key("fk_qb_school", "question_bank", "schools", ["school_id"], ["id"], ondelete="RESTRICT")
    if not _has_fk(conn, "question_bank", "fk_qb_submitted_by"):
        op.create_foreign_key(
            "fk_qb_submitted_by", "question_bank", "users", ["submitted_by"], ["id"], ondelete="SET NULL"
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
            sa.Column("suggested_options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
            sa.CheckConstraint("item_type IN ('TEACHER_QUESTION', 'EDIT_SUGGESTION')", name="chk_qri_item_type"),
            sa.CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED')", name="chk_qri_status"),
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
        # Partial unique INDEX, not a UniqueConstraint: PostgreSQL does not support a
        # WHERE clause on the latter.
        op.create_index(
            "uq_qri_pending_question_type",
            "question_review_items",
            ["question_id", "item_type"],
            unique=True,
            postgresql_where=sa.text("status = 'PENDING'"),
        )


def downgrade() -> None:
    """Intentionally a no-op.

    This migration only repairs state that dc843fdf3ba3 already owns. Dropping these
    objects here would undo that migration's work on every healthy environment while
    leaving its revision recorded as applied — recreating exactly the inconsistency
    being fixed. To roll the feature back, downgrade past dc843fdf3ba3 itself.
    """
