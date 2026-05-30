"""add_mini_course_chat_messages_and_quiz_responses

Revision ID: f892502b0975
Revises: 4907e221d11b
Create Date: 2026-05-28 16:06:34.274273

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f892502b0975"
down_revision: str | Sequence[str] | None = "4907e221d11b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mini_course_chat_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("subtopic_id", sa.UUID(), nullable=False),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default="now()", nullable=False),
        sa.CheckConstraint("role IN ('student', 'ai')", name="chk_chat_message_role"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subtopic_id"], ["subtopics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_mini_course_chat_school_student_subtopic",
        "mini_course_chat_messages",
        ["school_id", "student_id", "subtopic_id"],
        unique=False,
    )

    op.create_table(
        "mini_course_quiz_responses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("subtopic_id", sa.UUID(), nullable=False),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column("question_type", sa.String(length=20), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("student_answer", sa.Text(), nullable=False),
        sa.Column("ai_grade", sa.String(length=20), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default="now()", nullable=False),
        sa.CheckConstraint(
            "ai_grade IS NULL OR ai_grade IN ('correct', 'partial', 'incorrect')", name="chk_quiz_response_ai_grade"
        ),
        sa.CheckConstraint("question_type IN ('mcq', 'open_ended')", name="chk_quiz_response_question_type"),
        sa.CheckConstraint("score >= 0.0 AND score <= 1.0", name="chk_quiz_response_score_range"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subtopic_id"], ["subtopics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_mini_course_quiz_responses_school_student_subtopic",
        "mini_course_quiz_responses",
        ["school_id", "student_id", "subtopic_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_mini_course_quiz_responses_school_student_subtopic", table_name="mini_course_quiz_responses")
    op.drop_table("mini_course_quiz_responses")
    op.drop_index("idx_mini_course_chat_school_student_subtopic", table_name="mini_course_chat_messages")
    op.drop_table("mini_course_chat_messages")
