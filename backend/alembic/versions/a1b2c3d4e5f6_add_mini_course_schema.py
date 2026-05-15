"""add_mini_course_schema

Revision ID: a1b2c3d4e5f6
Revises: d0755259c311
Create Date: 2026-05-15

Hand-written migration — autogenerate was not used because it picked up
unrelated model drift across the entire codebase. This migration does exactly
three things and nothing else:
  1. CREATE TABLE subtopic_course_progress
  2. CREATE TABLE subtopic_content_feedback
  3. ALTER TABLE subtopic_content: add thumbs_up_count, thumbs_down_count,
     rejection_teacher_note
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "d0755259c311"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subtopic_course_progress",
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("subtopic_id", sa.UUID(), nullable=False),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column(
            "last_visited_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "explanation_accessed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "video_accessed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("check_questions_score", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subtopic_id"], ["subtopics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("student_id", "subtopic_id"),
    )
    op.create_index(
        "idx_subtopic_course_progress_school_student",
        "subtopic_course_progress",
        ["school_id", "student_id"],
    )

    op.create_table(
        "subtopic_content_feedback",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("subtopic_content_id", sa.UUID(), nullable=False),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column("feedback_type", sa.String(length=20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "feedback_type IN ('thumbs_up', 'thumbs_down')",
            name="chk_subtopic_content_feedback_type",
        ),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["subtopic_content_id"],
            ["subtopic_content.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "student_id",
            "subtopic_content_id",
            name="uq_subtopic_content_feedback_student_content",
        ),
    )
    op.create_index(
        "idx_subtopic_content_feedback_content",
        "subtopic_content_feedback",
        ["subtopic_content_id"],
    )
    op.create_index(
        "idx_subtopic_content_feedback_school",
        "subtopic_content_feedback",
        ["school_id"],
    )

    op.add_column(
        "subtopic_content",
        sa.Column(
            "thumbs_up_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "subtopic_content",
        sa.Column(
            "thumbs_down_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "subtopic_content",
        sa.Column("rejection_teacher_note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subtopic_content", "rejection_teacher_note")
    op.drop_column("subtopic_content", "thumbs_down_count")
    op.drop_column("subtopic_content", "thumbs_up_count")

    op.drop_index(
        "idx_subtopic_content_feedback_school",
        table_name="subtopic_content_feedback",
    )
    op.drop_index(
        "idx_subtopic_content_feedback_content",
        table_name="subtopic_content_feedback",
    )
    op.drop_table("subtopic_content_feedback")

    op.drop_index(
        "idx_subtopic_course_progress_school_student",
        table_name="subtopic_course_progress",
    )
    op.drop_table("subtopic_course_progress")
