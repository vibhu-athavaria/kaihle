"""Mini-course progress, feedback, and teacher override SQLAlchemy models.

Covers: subtopic_course_progress, subtopic_content_feedback, mini_course_student_overrides
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
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
        TIMESTAMP(timezone=True),
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


class MiniCourseStudentOverride(Base, UUIDMixin, TimestampMixin):
    """Teacher-set interest-category override for a student on a topic's mini-course.

    When set, the mini-course delivery uses this interest category instead of
    auto-picking from the student's learning profile.

    UNIQUE on (school_id, topic_id, student_id) — one override per student per topic.
    """

    __tablename__ = "mini_course_student_overrides"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    interest_category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interest_categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Teacher who set this override — for audit trail.
    set_by_teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "school_id",
            "topic_id",
            "student_id",
            name="uq_mini_course_override_school_topic_student",
        ),
        Index("idx_mini_course_overrides_school_topic", "school_id", "topic_id"),
    )
