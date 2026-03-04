"""Curriculum-related SQLAlchemy models.

Covers: curricula, subjects, grades, topics, curriculum_subjects,
curriculum_topics, subtopics, subtopic_prerequisites, curriculum_chunks
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Curriculum(Base, UUIDMixin, TimestampMixin):
    """Global curriculum boards. School-agnostic."""

    __tablename__ = "curricula"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )


class Subject(Base, UUIDMixin, TimestampMixin):
    """Global subject catalogue. School-agnostic."""

    __tablename__ = "subjects"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(50))
    color: Mapped[str | None] = mapped_column(String(7))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )


class Grade(Base, UUIDMixin, TimestampMixin):
    """Global grade levels. School-agnostic."""

    __tablename__ = "grades"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    level: Mapped[int] = mapped_column(
        Integer, nullable=False, unique=True
    )
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    __table_args__ = (
        CheckConstraint("level BETWEEN 1 AND 13", name="grades_level_range"),
    )


class Topic(Base, UUIDMixin, TimestampMixin):
    """Topics are school-agnostic AND grade-agnostic."""

    __tablename__ = "topics"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_code: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
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
    is_core: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
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
    is_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    __table_args__ = (
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
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))

    __table_args__ = (
        CheckConstraint(
            "difficulty_level IS NULL OR (difficulty_level BETWEEN 1 AND 5)",
            name="chk_subtopic_difficulty",
        ),
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
    importance: Mapped[str] = mapped_column(
        String(20), nullable=False, default="REQUIRED"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()", nullable=False
    )

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

    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="chk_chunk_index"),
    )
