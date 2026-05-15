"""Assessment-related SQLAlchemy models.

Covers: assessments, assessment_topic_config, assessment_selected_questions,
        student_attempts, student_responses, student_attempt_subtopic_scores
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID
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

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="RESTRICT"),
        nullable=False,
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    assessment_type: Mapped[str] = mapped_column(
        Enum(
            AssessmentType.DIAGNOSTIC,
            AssessmentType.TOPIC_SPECIFIC,
            AssessmentType.PROGRESS_CHECK,
            AssessmentType.FINAL,
            name="assessment_type",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum(
            AssessmentStatus.DRAFT,
            AssessmentStatus.ACTIVE,
            AssessmentStatus.CLOSED,
            name="assessment_status",
        ),
        nullable=False,
        default=AssessmentStatus.DRAFT,
    )
    instructions: Mapped[str | None] = mapped_column(Text)
    question_count: Mapped[int | None] = mapped_column(Integer)
    questions_per_topic: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    minimum_difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    maximum_difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    question_types: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=lambda: ["MCQ", "TRUE_FALSE"]
    )
    time_limit_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    deadline: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    __table_args__ = (
        CheckConstraint("minimum_difficulty >= 1", name="chk_assessment_min_diff"),
        CheckConstraint("maximum_difficulty <= 5", name="chk_assessment_max_diff"),
        CheckConstraint("questions_per_topic >= 1", name="chk_assessment_qpt"),
        CheckConstraint("time_limit_minutes >= 0", name="chk_assessment_time_limit"),
    )


class AssessmentTopicConfig(Base):
    """Topics selected for an assessment, with their source grade.

    Replaces the diagnostic_topic_ids ARRAY column. Each row records which
    curriculum topic is included and which grade it came from — supporting
    prior-grade topic selection (grade = class.grade - 1).
    """

    __tablename__ = "assessment_topic_config"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    curriculum_topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_topics.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    grade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("grades.id", ondelete="RESTRICT"),
        nullable=False,
    )

    __table_args__ = (Index("idx_atc_assessment", "assessment_id"),)


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
        ),
        nullable=False,
        default=AttemptStatus.NOT_STARTED,
    )
    total_questions: Mapped[int | None]
    questions_answered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_score: Mapped[float | None]
    time_taken_seconds: Mapped[int | None]
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    __table_args__ = (
        UniqueConstraint("assessment_id", "student_id", name="sa_unique"),
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
        ),
        nullable=False,
        default=ScoredBy.PENDING,
    )
    ai_feedback: Mapped[str | None] = mapped_column(Text)
    hints_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    time_taken_ms: Mapped[int | None]
    answered_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="sr_unique"),
        CheckConstraint(
            "score IS NULL OR (score BETWEEN 0.0 AND 1.0)",
            name="chk_sr_score",
        ),
    )


class StudentAttemptSubtopicScore(Base):
    """Per-attempt, per-subtopic score used to compute rolling mastery.

    Inserted by the calculate_gap_states Celery task after each attempt is COMPLETED.
    Used to compute recency-weighted mastery in subsequent task runs.
    """

    __tablename__ = "student_attempt_subtopic_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    subtopic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subtopics.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_attempts.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(nullable=False)
    # Per-subtopic fraction correct for this attempt: correct / total in subtopic
    attempted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "subtopic_id",
            "attempt_id",
            name="uq_sats_student_subtopic_attempt",
        ),
        Index("idx_subtopic_scores_student_sub", "student_id", "subtopic_id"),
        CheckConstraint("score BETWEEN 0.0 AND 1.0", name="chk_sats_score"),
    )
