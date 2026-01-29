# app/models/assessment.py
import enum, uuid
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey, Boolean, Float, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, UUID
from sqlalchemy.sql import func
from app.core.database import Base
from app.crud.mixin import SerializerMixin

class AssessmentType(str, enum.Enum):
    DIAGNOSTIC = "diagnostic"
    PROGRESS = "progress"
    FINAL = "final"
    TOPIC_SPECIFIC = "topic_specific"

class AssessmentStatus(str, enum.Enum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"

class DifficultyLevel(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class Assessment(Base, SerializerMixin):
    __tablename__ = "assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    grade_id = Column(UUID(as_uuid=True), ForeignKey("grades.id", ondelete="SET NULL"), nullable=True, index=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)

    assessment_type = Column(Enum(AssessmentType), nullable=False)  # "diagnostic", "progress", "final", "topic_specific"
    difficulty_level = Column(Enum(DifficultyLevel), default=DifficultyLevel.MEDIUM)  # "easy", "medium", "hard"
    status = Column(Enum(AssessmentStatus), default=AssessmentStatus.STARTED, index=True)  # "started", "in_progress", "completed", "abandoned"

    total_questions = Column(Integer, default=0)
    questions_answered = Column(Integer, default=0)
    overall_score = Column(Float, nullable=True)  # 0-100
    time_taken = Column(Integer, nullable=True)  # in minutes

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('idx_assessment_student_subject', 'student_id', 'subject_id'),
        Index('idx_assessment_status_created', 'status', 'created_at'),
    )

    # Relationships
    student = relationship("StudentProfile", back_populates="assessments")
    subject = relationship("Subject", back_populates="assessments")
    grade = relationship("Grade", back_populates="assessments")
    topic = relationship("Topic")
    questions = relationship("AssessmentQuestion", back_populates="assessment", cascade="all, delete-orphan")
    study_plan = relationship("StudyPlan", uselist=False, back_populates="assessment")
    reports = relationship("AssessmentReport", back_populates="assessment", cascade="all, delete-orphan")


class AssessmentQuestion(Base, SerializerMixin):
    __tablename__ = "assessment_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    question_bank_id = Column(UUID(as_uuid=True), ForeignKey("question_bank.id", ondelete="CASCADE"), nullable=False, index=True)

    question_number = Column(Integer, nullable=False)
    student_answer = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    score = Column(Float, nullable=True)  # 0-1, can be partial for complex questions
    time_taken = Column(Integer, nullable=True)  # in seconds

    ai_feedback = Column(Text, nullable=True)
    hints_used = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    answered_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('idx_aq_assessment_question', 'assessment_id', 'question_number'),
    )

    # Relationships
    assessment = relationship("Assessment", back_populates="questions")
    question_bank = relationship("QuestionBank", back_populates="assessment_questions")


class QuestionBank(Base, SerializerMixin):
    __tablename__ = "question_bank"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=True, index=True)
    subtopic_id = Column(UUID(as_uuid=True), ForeignKey("subtopics.id", ondelete="SET NULL"), nullable=True, index=True)
    grade_id = Column(UUID(as_uuid=True), ForeignKey("grades.id", ondelete="SET NULL"), nullable=True, index=True)

    question_text = Column(Text, nullable=False)
    question_type = Column(String(50), nullable=False)  # "multiple_choice", "short_answer", "true_false", "essay"

    # For multiple choice
    options = Column(JSONB, nullable=True)
    correct_answer = Column(Text, nullable=False)

    # Question metadata
    difficulty_level = Column(Float, default=0.5)  # 0.0-1.0 scale
    bloom_taxonomy_level = Column(String(50), nullable=True)  # Remember, Understand, Apply, Analyze, Evaluate, Create
    estimated_time_seconds = Column(Integer, nullable=True)

    # For tracking prerequisite topics required
    prerequisites = Column(ARRAY(Integer), nullable=True)  # Array of topic IDs

    learning_objectives = Column(ARRAY(Text), nullable=True)
    explanation = Column(Text, nullable=True)  # Detailed explanation of the answer
    hints = Column(JSONB, nullable=True)  # Progressive hints

    # For question deduplication and similarity
    canonical_form = Column(Text, nullable=False)  # Normalized version for dedup
    problem_signature = Column(JSONB, nullable=False)  # For similarity matching

    # Usage tracking
    times_used = Column(Integer, default=0)
    average_score = Column(Float, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('idx_qb_subject_topic_difficulty', 'subject_id', 'topic_id', 'difficulty_level'),
        Index('idx_qb_grade_subject', 'grade_id', 'subject_id'),
    )

    # Relationships
    subject = relationship("Subject", back_populates="question_banks")
    topic = relationship("Topic", back_populates="question_banks")
    subtopic = relationship("Subtopic", back_populates="question_banks")
    grade = relationship("Grade")
    assessment_questions = relationship("AssessmentQuestion", back_populates="question_bank")
    micro_course_questions = relationship("MicroCourseQuestionLink", back_populates="question_bank")
    student_answers = relationship("StudentAnswer", back_populates="question_bank")


class AssessmentReport(Base, SerializerMixin):
    __tablename__ = "assessment_reports"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, unique=True)

    diagnostic_summary = Column(JSONB, nullable=True)
    knowledge_gaps = Column(JSONB, nullable=True)
    strengths = Column(JSONB, nullable=True)
    recommendations = Column(JSONB, nullable=True)

    # Structured report data
    study_plan_json = Column(JSONB, nullable=True)
    mastery_table_json = Column(JSONB, nullable=True)
    topic_breakdown = Column(JSONB, nullable=True)
    """
    Example:
    {
        "topics": [
            {
                "topic_id": 5,
                "topic_name": "Algebra",
                "questions_attempted": 10,
                "questions_correct": 7,
                "mastery_level": 0.7,
                "subtopics": [...]
            }
        ]
    }
    """

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    assessment = relationship("Assessment", back_populates="reports")


class StudentKnowledgeProfile(Base, SerializerMixin):
    """
    Tracks student mastery across topics/subtopics over time
    Updated after each assessment
    """
    __tablename__ = "student_knowledge_profiles"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=True, index=True)
    subtopic_id = Column(UUID(as_uuid=True), ForeignKey("subtopics.id", ondelete="CASCADE"), nullable=True, index=True)

    mastery_level = Column(Float, default=0.0)  # 0.0-1.0, where 1.0 is complete mastery
    confidence_score = Column(Float, default=0.5)  # AI confidence in the mastery assessment

    # Tracking metadata
    last_assessed = Column(DateTime(timezone=True), nullable=True)
    assessment_count = Column(Integer, default=0)
    total_questions_attempted = Column(Integer, default=0)
    total_questions_correct = Column(Integer, default=0)

    needs_review = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('idx_skp_student_subject', 'student_id', 'subject_id'),
        Index('idx_skp_student_topic', 'student_id', 'topic_id'),
        Index('idx_skp_needs_review', 'student_id', 'needs_review'),
    )

    # Relationships
    student = relationship("StudentProfile", back_populates="knowledge_profiles")
    subject = relationship("Subject")
    topic = relationship("Topic", back_populates="knowledge_profiles")
    subtopic = relationship("Subtopic", back_populates="knowledge_profiles")