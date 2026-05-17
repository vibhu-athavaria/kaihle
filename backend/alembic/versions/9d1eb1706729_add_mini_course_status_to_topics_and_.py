"""add_mini_course_status_to_topics_and_student_overrides

Revision ID: 9d1eb1706729
Revises: 8fdf51b61aa5
Create Date: 2026-05-17 12:31:43.807695

Adds:
  - topics.mini_course_status VARCHAR(20) NOT NULL DEFAULT 'none'
  - topics.mini_course_teacher_id UUID FK → users.id (nullable)
  - mini_course_student_overrides table: teacher override of interest variant per student per topic
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9d1eb1706729"
down_revision: str | Sequence[str] | None = "8fdf51b61aa5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "topics",
        sa.Column("mini_course_status", sa.String(length=20), server_default="none", nullable=False),
    )
    op.add_column(
        "topics",
        sa.Column("mini_course_teacher_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_topics_mini_course_teacher_id",
        "topics",
        "users",
        ["mini_course_teacher_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "mini_course_student_overrides",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column("topic_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("interest_category_id", sa.UUID(), nullable=False),
        sa.Column("set_by_teacher_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["interest_category_id"], ["interest_categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["set_by_teacher_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "school_id",
            "topic_id",
            "student_id",
            name="uq_mini_course_override_school_topic_student",
        ),
    )
    op.create_index(
        "idx_mini_course_overrides_school_topic",
        "mini_course_student_overrides",
        ["school_id", "topic_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_mini_course_overrides_school_topic", table_name="mini_course_student_overrides")
    op.drop_table("mini_course_student_overrides")
    op.drop_constraint("fk_topics_mini_course_teacher_id", "topics", type_="foreignkey")
    op.drop_column("topics", "mini_course_teacher_id")
    op.drop_column("topics", "mini_course_status")
