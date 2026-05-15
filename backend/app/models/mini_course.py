"""Mini-course progress and feedback SQLAlchemy models.

Covers: subtopic_course_progress, subtopic_content_feedback
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class SubtopicCourseProgress(Base):
    """Tracks a student's progress through a mini-course for a given subtopic.

    Composite primary key: (student_id, subtopic_id) — one row per student per subtopic.
    last_visited_at is updated every time the student opens the mini-course page.
    check_questions_score is NULL until the student completes the check questions.
    """

    __tablename__ = "subtopic_course_progress"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    )
    subtopic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subtopics.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    last_visited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )
    explanation_accessed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    video_accessed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    check_questions_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    __table_args__ = (Index("idx_subtopic_course_progress_school_student", "school_id", "student_id"),)


class SubtopicContentFeedback(Base, UUIDMixin, TimestampMixin):
    """Stores student thumbs up/down feedback on AI-generated subtopic content.

    UNIQUE on (student_id, subtopic_content_id) — one feedback per student per content row.
    feedback_type must be 'thumbs_up' or 'thumbs_down'.
    """

    __tablename__ = "subtopic_content_feedback"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    subtopic_content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subtopic_content.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feedback_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "subtopic_content_id",
            name="uq_subtopic_content_feedback_student_content",
        ),
        CheckConstraint(
            "feedback_type IN ('thumbs_up', 'thumbs_down')",
            name="chk_subtopic_content_feedback_type",
        ),
    )
