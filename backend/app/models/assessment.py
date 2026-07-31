"""Assessment-related SQLAlchemy models.

Covers: assessments, assessment_topic_config, assessment_selected_questions,
        student_attempts, student_responses, student_attempt_subtopic_scores,
        question_review_items
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID
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


class QuestionReviewItem(Base, UUIDMixin, TimestampMixin):
    """Unified review queue for teacher-submitted questions and edit suggestions.

    item_type='TEACHER_QUESTION': teacher added a new question to their assessment.
        question_id → newly inserted question_bank row (source='teacher', school-scoped).
        suggested_* fields are NULL; question is already live in the assessment pool.
        On KaihleAdmin approve: school_id cleared → question promoted to global bank.
        On KaihleAdmin reject:  question_bank.is_active set FALSE.

    item_type='EDIT_SUGGESTION': teacher suggested a change to an existing question.
        question_id → existing question_bank row.
        suggested_* fields contain the proposed changes.
        On KaihleAdmin approve: suggested (or admin-edited) fields applied to question_bank.
        On KaihleAdmin reject:  question_bank unchanged.
    """

    __tablename__ = "question_review_items"

    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("question_bank.id", ondelete="CASCADE"),
        nullable=False,
    )
    submitted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="SET NULL"),
        nullable=True,
    )
    suggested_question_text: Mapped[str | None] = mapped_column(Text)
    suggested_options: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    suggested_correct_answer: Mapped[str | None] = mapped_column(Text)
    suggested_explanation: Mapped[str | None] = mapped_column(Text)
    suggested_difficulty_level: Mapped[float | None]
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    admin_note: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "item_type IN ('TEACHER_QUESTION', 'EDIT_SUGGESTION')",
            name="chk_qri_item_type",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="chk_qri_status",
        ),
        Index("idx_qri_status", "status", postgresql_where=text("status = 'PENDING'")),
        Index("idx_qri_school", "school_id"),
        Index("idx_qri_item_type", "item_type"),
    )
