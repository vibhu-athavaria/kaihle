"""Curriculum-related SQLAlchemy models.

Covers: curricula, subjects, grades, topics, curriculum_subjects,
curriculum_topics, subtopics, subtopic_prerequisites, curriculum_chunks,
learning_objectives, subtopic_objectives, question_bank
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.subtopic_content import SubtopicContent

from app.models.base import Base, TimestampMixin, UUIDMixin


class Curriculum(Base, UUIDMixin, TimestampMixin):
    """Global curriculum boards. School-agnostic."""

    __tablename__ = "curricula"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    curriculum_topics: Mapped[list["CurriculumTopic"]] = relationship("CurriculumTopic", back_populates="curriculum")
    grades: Mapped[list["Grade"]] = relationship(
        "Grade",
        secondary="curriculum_grades",
        back_populates="curricula",
        order_by="CurriculumGrade.sort_order",
    )


class Subject(Base, UUIDMixin, TimestampMixin):
    """Global subject catalogue. School-agnostic."""

    __tablename__ = "subjects"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    # Groups subjects that share a knowledge domain across curriculum boundaries.
    # E.g. BIO/CHEM/PHY/SCI all share "SCI"; used for cross-curriculum diagnostic topic lookup.
    subject_family_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(50))
    color: Mapped[str | None] = mapped_column(String(7))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    curriculum_topics: Mapped[list["CurriculumTopic"]] = relationship("CurriculumTopic", back_populates="subject")


class Grade(Base, UUIDMixin, TimestampMixin):
    """Global grade levels. School-agnostic."""

    __tablename__ = "grades"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (CheckConstraint("level BETWEEN 1 AND 13", name="grades_level_range"),)

    curriculum_topics: Mapped[list["CurriculumTopic"]] = relationship("CurriculumTopic", back_populates="grade")
    curricula: Mapped[list["Curriculum"]] = relationship(
        "Curriculum",
        secondary="curriculum_grades",
        back_populates="grades",
    )


class Topic(Base, UUIDMixin, TimestampMixin):
    """Topics are school-agnostic AND grade-agnostic."""

    __tablename__ = "topics"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_code: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Mini-course generation status (global per topic, school-agnostic).
    # none → not yet generated; generating → in progress; ready → content exists; failed → last attempt failed.
    mini_course_status: Mapped[str] = mapped_column(String(20), nullable=False, default="none", server_default="none")
    # UUID of the teacher who last triggered generation — used to send success email.
    mini_course_teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class CurriculumSubject(Base, TimestampMixin):
    """Which subjects belong to a curriculum."""

    __tablename__ = "curriculum_subjects"

    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curricula.id", ondelete="CASCADE"),
        primary_key=True,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_core: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int | None]


class CurriculumGrade(Base):
    """Which grades belong to a curriculum. Mirrors CurriculumSubject pattern."""

    __tablename__ = "curriculum_grades"

    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curricula.id", ondelete="CASCADE"),
        primary_key=True,
    )
    grade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("grades.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sort_order: Mapped[int | None]


class CurriculumTopic(Base, UUIDMixin, TimestampMixin):
    """The pivot table binding curriculum + subject + grade + topic."""

    __tablename__ = "curriculum_topics"

    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curricula.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    grade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("grades.id", ondelete="CASCADE"),
        nullable=False,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    standard_code: Mapped[str | None] = mapped_column(String(100))
    sequence_order: Mapped[int | None]
    learning_objectives: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    recommended_weeks: Mapped[int | None]
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    curriculum: Mapped["Curriculum"] = relationship("Curriculum", back_populates="curriculum_topics")
    subject: Mapped["Subject"] = relationship("Subject", back_populates="curriculum_topics")
    grade: Mapped["Grade"] = relationship("Grade", back_populates="curriculum_topics")
    subtopics: Mapped[list["Subtopic"]] = relationship("Subtopic", back_populates="curriculum_topic")

    __table_args__ = (
        UniqueConstraint("curriculum_id", "subject_id", "grade_id", "topic_id", name="curriculum_topics_unique"),
        CheckConstraint(
            "sequence_order IS NULL OR sequence_order > 0",
            name="chk_ct_sequence",
        ),
    )


class Subtopic(Base, UUIDMixin, TimestampMixin):
    """Atomic unit of knowledge."""

    __tablename__ = "subtopics"

    curriculum_topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_code: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    learning_objective: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    bloom_taxonomy_level: Mapped[str | None] = mapped_column(String(50))
    difficulty_level: Mapped[int | None]
    estimated_minutes: Mapped[int | None]
    sequence_order: Mapped[int | None]
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))
    # IGCSE Core/Extended tiering. Tier is a curriculum-PLACEMENT property, so it lives
    # here and nowhere else — not on learning_objectives, not on subtopic_objectives.
    # Lower Secondary (grades 6-8) has no tiering and is always 'BOTH'.
    # Core students see tier IN ('CORE','BOTH'); Extended students see all three.
    tier: Mapped[str] = mapped_column(String(10), nullable=False, default="BOTH", server_default="BOTH")

    __table_args__ = (
        CheckConstraint(
            "difficulty_level IS NULL OR (difficulty_level BETWEEN 1 AND 5)",
            name="chk_subtopic_difficulty",
        ),
        CheckConstraint(
            "tier IN ('CORE', 'EXTENDED', 'BOTH')",
            name="chk_subtopic_tier",
        ),
    )

    curriculum_topic: Mapped["CurriculumTopic"] = relationship("CurriculumTopic", back_populates="subtopics")
    questions: Mapped[list["QuestionBank"]] = relationship("QuestionBank", back_populates="subtopic")
    learning_objectives: Mapped[list["LearningObjective"]] = relationship(
        "LearningObjective",
        secondary="subtopic_objectives",
        back_populates="subtopics",
    )
    subtopic_contents: Mapped[list["SubtopicContent"]] = relationship(  # noqa: F821
        "SubtopicContent", back_populates="subtopic"
    )


class SubtopicPrerequisite(Base):
    """Prerequisite graph at subtopic level."""

    __tablename__ = "subtopic_prerequisites"

    subtopic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subtopics.id", ondelete="CASCADE"),
        primary_key=True,
    )
    prerequisite_subtopic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subtopics.id", ondelete="CASCADE"),
        primary_key=True,
    )
    importance: Mapped[str] = mapped_column(String(20), nullable=False, default="REQUIRED")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "subtopic_id <> prerequisite_subtopic_id",
            name="chk_no_self_prereq",
        ),
        CheckConstraint(
            "importance IN ('REQUIRED', 'RECOMMENDED', 'HELPFUL')",
            name="chk_importance",
        ),
    )


class CurriculumChunk(Base, UUIDMixin, TimestampMixin):
    """Text chunks extracted from Cambridge PDF files, linked to subtopics."""

    __tablename__ = "curriculum_chunks"

    subtopic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subtopics.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    token_count: Mapped[int | None]
    source_file: Mapped[str | None] = mapped_column(String(255))
    page_number: Mapped[int | None]
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))

    __table_args__ = (CheckConstraint("chunk_index >= 0", name="chk_chunk_index"),)


class LearningObjective(Base, UUIDMixin, TimestampMixin):
    """A curriculum-agnostic statement of what a learner should be able to do.

    This is the stable binding target for questions. Subtopics are curriculum
    PLACEMENT (they change when a curriculum is remapped); learning objectives are
    the underlying concept and survive remapping. Deliberately carries neither a
    difficulty range (that is a per-question property) nor a grade range (that is a
    placement property, expressed via curriculum_topics -> subtopics).
    """

    __tablename__ = "learning_objectives"

    # Human-readable stable identifier, e.g. 'MATH-NEGATIVE-NUMBERS'.
    canonical_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Full objective text. This is the basis for text/semantic de-duplication.
    learning_objective: Mapped[str] = mapped_column(Text, nullable=False)
    # RESTRICT: topics are shared across grades and curricula, so deleting a topic that
    # still owns objectives must be a hard error rather than a silent cascade.
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    bloom_taxonomy_level: Mapped[str | None] = mapped_column(String(50))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    topic: Mapped["Topic"] = relationship("Topic")
    subtopics: Mapped[list["Subtopic"]] = relationship(
        "Subtopic",
        secondary="subtopic_objectives",
        back_populates="learning_objectives",
    )
    questions: Mapped[list["QuestionBank"]] = relationship("QuestionBank", back_populates="learning_objective")


class SubtopicObjective(Base):
    """Many-to-many bridge between curriculum placement and concept.

    One subtopic can teach several objectives, and one objective can be taught by
    several subtopics (across grades, and across curriculum versions). The initial
    Cambridge v2 mapping is close to 1:1, but the bridge is what allows a future
    curriculum to reuse existing objectives instead of duplicating them.
    """

    __tablename__ = "subtopic_objectives"

    subtopic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subtopics.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # RESTRICT: an objective still referenced by any subtopic must not be deleted.
    learning_objective_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_objectives.id", ondelete="RESTRICT"),
        primary_key=True,
    )


class QuestionBank(Base, UUIDMixin, TimestampMixin):
    """Single canonical question store."""

    __tablename__ = "question_bank"

    # NULLABLE as of the v2 curriculum remap. Retained for legacy/audit only — it is
    # no longer used for question selection anywhere. Selection goes through
    # learning_objective_id. A question is transiently NULL here between the scoped
    # curriculum wipe and its re-mapping to a learning objective.
    subtopic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subtopics.id", ondelete="RESTRICT"),
        nullable=True,
    )
    # The primary binding for question selection. Nullable only during the remap
    # transition; Phase 7 validation asserts every active question has one.
    learning_objective_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_objectives.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(
        Enum("MCQ", "TRUE_FALSE", "SHORT_ANSWER", name="question_type"),
        nullable=False,
    )
    options: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # MCQ format: [{"key": "A", "text": "..."}, {"key": "B", "text": "..."}, ...]
    # NULL for TRUE_FALSE and SHORT_ANSWER
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    # MCQ: "A" | TRUE_FALSE: "true"/"false" | SHORT_ANSWER: model answer text
    explanation: Mapped[str | None] = mapped_column(Text)
    hints: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # [{"order": 1, "text": "..."}, ...]
    difficulty_level: Mapped[float | None]
    bloom_taxonomy_level: Mapped[str | None] = mapped_column(String(50))
    estimated_time_seconds: Mapped[int | None]
    learning_objectives: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    canonical_form: Mapped[str] = mapped_column(Text, nullable=False)
    problem_signature: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="bank")
    # 'bank' = from founders 7K import | 'llm' = AI-generated | 'teacher' = teacher-submitted (school-scoped until promoted) | 'llm-correction' = LLM-validated replacement
    meta_tags: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    replaces_question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("question_bank.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Teacher-submitted question fields (NULL for bank/llm questions)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="RESTRICT"),
        nullable=True,
    )
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    review_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # NULL for bank/llm; 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED' for teacher-submitted

    subtopic: Mapped["Subtopic | None"] = relationship("Subtopic", back_populates="questions")
    learning_objective: Mapped["LearningObjective | None"] = relationship(
        "LearningObjective", back_populates="questions"
    )

    __table_args__ = (
        CheckConstraint(
            "difficulty_level IS NULL OR (difficulty_level BETWEEN 1.0 AND 5.0)",
            name="chk_qb_difficulty",
        ),
        CheckConstraint(
            "source IN ('bank', 'llm', 'llm-correction', 'teacher')",
            name="chk_qb_source",
        ),
        CheckConstraint(
            "review_status IS NULL OR review_status IN ('PENDING_REVIEW', 'APPROVED', 'REJECTED')",
            name="chk_qb_review_status",
        ),
    )
