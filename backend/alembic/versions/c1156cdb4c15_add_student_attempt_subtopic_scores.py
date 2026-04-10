"""add_student_attempt_subtopic_scores

Revision ID: c1156cdb4c15
Revises: 006_assessment_tier2_columns
Create Date: 2026-04-10 08:17:45.235439

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1156cdb4c15"
down_revision: str | Sequence[str] | None = "006_assessment_tier2_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create student_attempt_subtopic_scores table."""
    op.create_table(
        "student_attempt_subtopic_scores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("subtopic_id", sa.UUID(), nullable=False),
        sa.Column("attempt_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("score BETWEEN 0.0 AND 1.0", name="chk_sats_score"),
        sa.ForeignKeyConstraint(["attempt_id"], ["student_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subtopic_id"], ["subtopics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "student_id",
            "subtopic_id",
            "attempt_id",
            name="uq_sats_student_subtopic_attempt",
        ),
    )
    op.create_index(
        "idx_subtopic_scores_student_sub",
        "student_attempt_subtopic_scores",
        ["student_id", "subtopic_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop student_attempt_subtopic_scores table."""
    op.drop_index("idx_subtopic_scores_student_sub", table_name="student_attempt_subtopic_scores")
    op.drop_table("student_attempt_subtopic_scores")
