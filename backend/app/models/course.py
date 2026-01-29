# app/models/course.py
import uuid, enum
from sqlalchemy import (
    Column, Integer, String, ForeignKey, Boolean,
    TIMESTAMP, text, Index, CheckConstraint, ENUM
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.crud.mixin import SerializerMixin

class CourseSectionType(str, enum.Enum): # "intro", "explanation", "example", "practice", "summary"
    INTRO = "intro"
    EXPLANATION = "explanation"
    EXAMPLE = "example"
    PRACTICE = "practice"
    SUMMARY = "summary"

class CourseContentType(str, enum.Enum):
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"
    QUIZ = "quiz"
    INTERACTIVE = "interactive"
    ASSIGNMENT = "assignment"


class MicroCourse(Base, SerializerMixin):
    """
    Bite-sized, focused learning modules (10-20 minutes)
    Can be AI-generated based on knowledge gaps
    """
    __tablename__ = "micro_courses"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)

    # Proper foreign key relationships
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    grade_id = Column(UUID(as_uuid=True), ForeignKey("grades.id", ondelete="SET NULL"), nullable=True, index=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    subtopic_id = Column(UUID(as_uuid=True), ForeignKey("subtopics.id", ondelete="SET NULL"), nullable=True, index=True)

    # Course metadata
    learning_objectives = Column(JSONB, nullable=True)
    duration_minutes = Column(Integer, server_default="15")
    difficulty_level = Column(Integer, nullable=True)  # 1-5

    # Prerequisites - consistent with QuestionBank
    prerequisite_topic_ids = Column(ARRAY(Integer), nullable=True)  # Array of topic IDs that must be mastered first

    # AI generation metadata
    generated_by_ai = Column(Boolean, default=False)
    generation_context = Column(JSONB, nullable=True)  # Store prompts, parameters used
    """
    Example:
    {
        "student_id": 123,
        "knowledge_gaps": [5, 12],
        "generation_date": "2024-01-15",
        "model_version": "gpt-4"
    }
    """

    is_active = Column(Boolean, default=True)
    is_published = Column(Boolean, default=False)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=text("now()"))

    __table_args__ = (
        CheckConstraint('difficulty_level BETWEEN 1 AND 5', name='chk_mc_difficulty'),
        Index('idx_mc_subject_topic', 'subject_id', 'topic_id'),
        Index('idx_mc_grade_subject', 'grade_id', 'subject_id'),
    )

    # Relationships
    subject = relationship("Subject", back_populates="micro_courses")
    grade = relationship("Grade", back_populates="micro_courses")
    topic = relationship("Topic", back_populates="micro_courses")
    subtopic = relationship("Subtopic", back_populates="micro_courses")

    sections = relationship("MicroCourseSection", back_populates="micro_course",
                          cascade="all, delete-orphan", order_by="MicroCourseSection.position")
    questions = relationship("MicroCourseQuestionLink", back_populates="micro_course",
                           cascade="all, delete-orphan", order_by="MicroCourseQuestionLink.position")

    student_progress = relationship("StudentCourseProgress", back_populates="micro_course",
                                   cascade="all, delete-orphan")
    tutor_sessions = relationship("TutorSession", back_populates="micro_course")
    student_answers = relationship("StudentAnswer", back_populates="micro_course")


class MicroCourseSection(Base, SerializerMixin):
    """
    Individual sections within a micro-course
    (e.g., Introduction, Explanation, Examples, Practice)
    """
    __tablename__ = "micro_course_sections"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    micro_course_id = Column(UUID(as_uuid=True), ForeignKey("micro_courses.id", ondelete="CASCADE"),
                            nullable=False, index=True)

    section_type = Column(ENUM(CourseSectionType), nullable=False)
    title = Column(String(255), nullable=True)

    content_type = Column(ENUM(CourseContentType), nullable=False)
    # Content stored as structured JSON
    content = Column(JSONB, nullable=False)
    """
    Example for different section types:

    "explanation": {
        "text": "...",
        "images": ["url1", "url2"],
        "video_url": "...",
        "interactive_elements": [...]
    }

    "example": {
        "problem": "...",
        "solution_steps": ["step1", "step2"],
        "explanation": "..."
    }

    "practice": {
        "question_ids": [1, 2, 3]  # Links to QuestionBank
    }
    """

    position = Column(Integer, nullable=False)
    estimated_time_minutes = Column(Integer, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=text("now()"))

    __table_args__ = (
        Index('idx_mcs_course_position', 'micro_course_id', 'position'),
    )

    # Relationships
    micro_course = relationship("MicroCourse", back_populates="sections")


class MicroCourseQuestionLink(Base, SerializerMixin):
    """
    Links questions from QuestionBank to MicroCourses
    Allows reusing questions across multiple courses
    """
    __tablename__ = "micro_course_question_links"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    micro_course_id = Column(UUID(as_uuid=True), ForeignKey("micro_courses.id", ondelete="CASCADE"), nullable=False, index=True)
    question_bank_id = Column(UUID(as_uuid=True), ForeignKey("question_bank.id", ondelete="CASCADE"), nullable=False, index=True)

    position = Column(Integer, nullable=False)  # Order within the course
    section_id = Column(UUID(as_uuid=True), ForeignKey("micro_course_sections.id", ondelete="SET NULL"), nullable=True)

    is_required = Column(Boolean, default=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index('idx_mcql_course_position', 'micro_course_id', 'position'),
    )

    # Relationships
    micro_course = relationship("MicroCourse", back_populates="questions")
    question_bank = relationship("QuestionBank", back_populates="micro_course_questions")


class StudentCourseProgress(Base, SerializerMixin):
    """
    Tracks student progress through micro-courses
    """
    __tablename__ = "student_course_progress"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    micro_course_id = Column(UUID(as_uuid=True), ForeignKey("micro_courses.id", ondelete="CASCADE"), nullable=False, index=True)

    status = Column(String(20), default="not_started")  # "not_started", "in_progress", "completed"
    progress_percentage = Column(Integer, default=0)  # 0-100

    sections_completed = Column(JSONB, default=list)  # Array of section IDs
    questions_answered = Column(JSONB, default=dict)  # {question_id: answer_data}

    time_spent_minutes = Column(Integer, default=0)
    score = Column(Integer, nullable=True)  # If course has assessment

    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_accessed_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=text("now()"))

    __table_args__ = (
        Index('idx_scp_student_course', 'student_id', 'micro_course_id'),
        Index('idx_scp_student_status', 'student_id', 'status'),
    )

    # Relationships
    student = relationship("StudentProfile", back_populates="course_progress")
    micro_course = relationship("MicroCourse", back_populates="student_progress")