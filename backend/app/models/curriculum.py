# app/models/curriculum.py
import uuid
from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, Boolean,
    CheckConstraint, UniqueConstraint, TIMESTAMP, text, Index
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.crud.mixin import SerializerMixin


class Grade(Base, SerializerMixin):
    """Grade levels (K-12, etc.)"""
    __tablename__ = "grades"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    name = Column(String(50), nullable=False)  # "Grade 5", "Kindergarten"
    level = Column(Integer, nullable=False, unique=True, index=True)  # 0 for K, 1-12
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=text("now()"))

    # Relationships
    curriculum_topics = relationship("CurriculumTopic", back_populates="grade")
    assessments = relationship("Assessment", back_populates="grade")
    student_profiles = relationship("StudentProfile", back_populates="grade")
    courses = relationship("Course", back_populates="grade")


class Curriculum(Base, SerializerMixin):
    """Curriculum standards (Common Core, IB, State-specific, etc.)"""
    __tablename__ = "curricula"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True)
    code = Column(String(50), nullable=True, unique=True)  # "CCSS", "IB", "CA-STATE"
    description = Column(Text, nullable=True)
    country = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=text("now()"))

    # Relationships
    curriculum_topics = relationship("CurriculumTopic", back_populates="curriculum", cascade="all, delete-orphan")


class Topic(Base, SerializerMixin):
    """
    High-level topics within a subject (e.g., Algebra, Geometry, Fractions)
    These are curriculum-agnostic and can be mapped to different standards
    """
    __tablename__ = "topics"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    canonical_code = Column(String(50), nullable=True, unique=True)  # e.g., "MATH.ALG.001"
    difficulty_level = Column(Integer, nullable=True)  # 1-5 scale
    learning_objectives = Column(ARRAY(Text), nullable=True)
    estimated_hours = Column(Integer, nullable=True)

    # Metadata for AI/ML
    keywords = Column(ARRAY(String), nullable=True)
    bloom_taxonomy_level = Column(String(50), nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=text("now()"))

    __table_args__ = (
        CheckConstraint('difficulty_level BETWEEN 1 AND 5', name='chk_topic_difficulty'),
    )

    # Relationships
    curriculum_topics = relationship("CurriculumTopic", back_populates="topic")
    subtopics = relationship("Subtopic", back_populates="topic", cascade="all, delete-orphan")
    prerequisites = relationship(
        "TopicPrerequisite",
        foreign_keys="[TopicPrerequisite.topic_id]",
        back_populates="topic",
        cascade="all, delete-orphan"
    )
    prerequisite_for = relationship(
        "TopicPrerequisite",
        foreign_keys="[TopicPrerequisite.prerequisite_topic_id]",
        back_populates="prerequisite_topic"
    )
    courses = relationship("Course", back_populates="topic")
    question_banks = relationship("QuestionBank", back_populates="topic")
    lessons = relationship("Lesson", back_populates="topic")
    knowledge_profiles = relationship("StudentKnowledgeProfile", back_populates="topic")


class Subtopic(Base, SerializerMixin):
    """
    Granular topics within a broader topic
    (e.g., Linear Equations, Quadratic Equations under Algebra)
    """
    __tablename__ = "subtopics"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    canonical_code = Column(String(50), nullable=True)
    sequence_order = Column(Integer, nullable=True)
    difficulty_level = Column(Integer, nullable=True)
    learning_objectives = Column(ARRAY(Text), nullable=True)
    estimated_hours = Column(Integer, nullable=True)

    keywords = Column(ARRAY(String), nullable=True)
    bloom_taxonomy_level = Column(String(50), nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=text("now()"))

    __table_args__ = (
        CheckConstraint('difficulty_level BETWEEN 1 AND 5', name='chk_subtopic_difficulty'),
        UniqueConstraint('topic_id', 'canonical_code', name='uq_topic_subtopic_code'),
        Index('idx_subtopic_topic_sequence', 'topic_id', 'sequence_order'),
    )

    # Relationships
    topic = relationship("Topic", back_populates="subtopics")
    courses = relationship("Course", back_populates="subtopic")
    question_banks = relationship("QuestionBank", back_populates="subtopic")
    lessons = relationship("Lesson", back_populates="subtopic")
    knowledge_profiles = relationship("StudentKnowledgeProfile", back_populates="subtopic")


class TopicPrerequisite(Base, SerializerMixin):
    """Defines prerequisite relationships between topics"""
    __tablename__ = "topic_prerequisites"

    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    prerequisite_topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    importance = Column(String(20), default="required")  # "required", "recommended", "optional"

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        CheckConstraint('topic_id <> prerequisite_topic_id', name='chk_no_self_prereq'),
    )

    # Relationships
    topic = relationship("Topic", foreign_keys=[topic_id], back_populates="prerequisites")
    prerequisite_topic = relationship("Topic", foreign_keys=[prerequisite_topic_id], back_populates="prerequisite_for")


class CurriculumTopic(Base, SerializerMixin):
    """
    Maps topics to specific curriculum standards and grade levels
    The same topic can appear in multiple curricula/grades
    """
    __tablename__ = "curriculum_topics"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    curriculum_id = Column(UUID(as_uuid=True), ForeignKey("curricula.id", ondelete="CASCADE"), nullable=False, index=True)
    grade_id = Column(UUID(as_uuid=True), ForeignKey("grades.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)

    sequence_order = Column(Integer, nullable=True)
    standard_code = Column(String(100), nullable=True)  # e.g., CCSS.MATH.5.NF.A.1
    difficulty_level = Column(Integer, nullable=True)
    learning_objectives = Column(ARRAY(Text), nullable=True)
    recommended_weeks = Column(Integer, nullable=True)

    is_required = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=text("now()"))

    __table_args__ = (
        UniqueConstraint('curriculum_id', 'grade_id', 'subject_id', 'topic_id',
                        name='uq_curriculum_grade_subject_topic'),
        CheckConstraint('difficulty_level BETWEEN 1 AND 5', name='chk_ct_difficulty'),
        Index('idx_ct_curriculum_grade_subject', 'curriculum_id', 'grade_id', 'subject_id'),
    )

    # Relationships
    curriculum = relationship("Curriculum", back_populates="curriculum_topics")
    grade = relationship("Grade", back_populates="curriculum_topics")
    subject = relationship("Subject", back_populates="curriculum_topics")
    topic = relationship("Topic", back_populates="curriculum_topics")
