"""Assessment-related SQLAlchemy models.

Covers: assessments, assessment_selected_questions, student_attempts, student_responses
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class AssessmentType:
    """Assessment type constants."""

    DIAGNOSTIC = "DIAGNOSTIC"
    TOPIC_SPECIFIC = "TOPIC_SPECIFIC"
    PROGRESS_CHECK = "PROGRESS_CHECK"
    FINAL = "FINAL"


class AssessmentStatus:
    """Assessment status constants."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class AttemptStatus:
    """Attempt status constants."""

    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class QuestionType:
    """Question type constants."""

    MCQ = "MCQ"
    TRUE_FALSE = "TRUE_FALSE"
    SHORT_ANSWER = "SHORT_ANSWER"


class ScoredBy:
    """Scored by constants."""

    RULE = "RULE"
    LLM = "LLM"
    PENDING = "PENDING"


class Assessment(Base, UUIDMixin, TimestampMixin):
    """Assessment definition."""

    __tablename__ = "assessments"

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        # NULL for system-generated Tier 1 diagnostics (is_system_generated=TRUE).
        # Non-NULL for teacher-created assessments (is_system_generated=FALSE).
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    assessment_type: Mapped[str] = mapped_column(
        Enum(
            AssessmentType.DIAGNOSTIC,
            AssessmentType.TOPIC_SPECIFIC,
            AssessmentType.PROGRESS_CHECK,
            AssessmentType.FINAL,
            name="assessment_type",
            native_enum=False,
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum(
            AssessmentStatus.DRAFT,
            AssessmentStatus.ACTIVE,
            AssessmentStatus.CLOSED,
            name="assessment_status",
            native_enum=False,
        ),
        nullable=False,
        default=AssessmentStatus.DRAFT,
    )
    is_system_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # TRUE = Tier 1 (auto-created on student enrollment by Celery task)
    # FALSE = Tier 2 (manually created by teacher)
    # Determines whether submit triggers onboarding completion check
    curriculum_topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_topics.id", ondelete="SET NULL"),
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # {
    #   "num_questions": 10,
    #   "difficulty_range": [1, 4],
    #   "question_types": ["MCQ", "SHORT_ANSWER"],
    #   "time_limit_minutes": null
    # }
    instructions: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssessmentSelectedQuestion(Base):
    """Bridge between assessment definition and question_bank."""

    __tablename__ = "assessment_selected_questions"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("question_bank.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    order_index: Mapped[int] = mapped_column(nullable=False)

    __table_args__ = (CheckConstraint("order_index >= 0", name="chk_asq_order"),)


class StudentAttempt(Base, UUIDMixin, TimestampMixin):
    """Per-student attempt."""

    __tablename__ = "student_attempts"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum(
            AttemptStatus.NOT_STARTED,
            AttemptStatus.IN_PROGRESS,
            AttemptStatus.COMPLETED,
            AttemptStatus.ABANDONED,
            name="attempt_status",
            native_enum=False,
        ),
        nullable=False,
        default=AttemptStatus.NOT_STARTED,
    )
    total_questions: Mapped[int | None]
    questions_answered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_score: Mapped[float | None]
    time_taken_seconds: Mapped[int | None]
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "overall_score IS NULL OR (overall_score BETWEEN 0.0 AND 1.0)",
            name="chk_sa_score",
        ),
    )


class StudentResponse(Base, UUIDMixin):
    """Per-question response within an attempt."""

    __tablename__ = "student_responses"

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_attempts.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("question_bank.id", ondelete="RESTRICT"),
        nullable=False,
    )
    answer_given: Mapped[str | None] = mapped_column(Text)
    is_correct: Mapped[bool | None]
    score: Mapped[float | None]
    scored_by: Mapped[str] = mapped_column(
        Enum(
            ScoredBy.RULE,
            ScoredBy.LLM,
            ScoredBy.PENDING,
            name="scored_by",
            native_enum=False,
        ),
        nullable=False,
        default=ScoredBy.PENDING,
    )
    ai_feedback: Mapped[str | None] = mapped_column(Text)
    hints_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    time_taken_ms: Mapped[int | None]
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "score IS NULL OR (score BETWEEN 0.0 AND 1.0)",
            name="chk_sr_score",
        ),
    )
