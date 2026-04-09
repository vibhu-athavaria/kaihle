"""Add Tier 2 assessment columns: school_id, published_at, question_count, deadline (rename due_at)

Revision ID: 006_assessment_tier2_columns
Revises: 005_add_cs_timestamps
Create Date: 2026-04-09
"""

import sqlalchemy as sa
from alembic import op

revision = "006_assessment_tier2_columns"
down_revision = "005_add_cs_timestamps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add school_id as nullable first so existing rows are accepted
    op.add_column(
        "assessments",
        sa.Column("school_id", sa.UUID(as_uuid=True), nullable=True),
    )

    # 2. Backfill school_id from the class row (assessments always belong to a class)
    op.execute(
        """
        UPDATE assessments
        SET school_id = c.school_id
        FROM classes c
        WHERE assessments.class_id = c.id
        """
    )

    # 3. Enforce NOT NULL and add FK + index now that all rows are populated
    op.alter_column("assessments", "school_id", nullable=False)
    op.create_foreign_key(
        "fk_assessments_school_id",
        "assessments",
        "schools",
        ["school_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("idx_assessments_school_id", "assessments", ["school_id"])

    # 4. Rename due_at → deadline
    op.alter_column("assessments", "due_at", new_column_name="deadline")

    # 5. Add published_at
    op.add_column(
        "assessments",
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # 6. Add question_count (nullable — Tier 1 assessments don't use it)
    op.add_column(
        "assessments",
        sa.Column("question_count", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("assessments", "question_count")
    op.drop_column("assessments", "published_at")
    op.alter_column("assessments", "deadline", new_column_name="due_at")
    op.drop_index("idx_assessments_school_id", table_name="assessments")
    op.drop_constraint("fk_assessments_school_id", "assessments", type_="foreignkey")
    op.drop_column("assessments", "school_id")
