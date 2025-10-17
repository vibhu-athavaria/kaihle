# app/models/assessment.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student_profiles.id"), nullable=False)
    subject = Column(String, nullable=False)  # Math, Science, English, History
    grade_level = Column(String, nullable=False)
    assessment_type = Column(String, nullable=False)  # "diagnostic", "progress", "final"
    difficulty_level = Column(String, default="medium")  # "easy", "medium", "hard"
    status = Column(String, default="started")  # "started", "in_progress", "completed", "abandoned"
    total_questions = Column(Integer, default=0)
    questions_answered = Column(Integer, default=0)
    overall_score = Column(Float, nullable=True)  # 0-100
    time_taken = Column(Integer, nullable=True)  # in minutes
    knowledge_gaps = Column(JSON, nullable=True)  # Array of topic areas with low scores
    strengths = Column(JSON, nullable=True)  # Array of topic areas with high scores
    recommendations = Column(JSON, nullable=True)  # AI-generated study recommendations
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    student = relationship("StudentProfile", back_populates="assessments")
    questions = relationship("AssessmentQuestion", back_populates="assessment", cascade="all, delete-orphan")
    study_plan = relationship("StudyPlan", uselist=False, back_populates="assessment")


class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=False)
    question_bank_id = Column(Integer, ForeignKey("question_bank.id"), nullable=False)
    question_number = Column(Integer, nullable=False)
    student_answer = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    score = Column(Float, nullable=True)  # 0-1, can be partial for complex questions
    time_taken = Column(Integer, nullable=True)  # in seconds
    ai_feedback = Column(Text, nullable=True)
    hints_used = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    answered_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    assessment = relationship("Assessment", back_populates="questions")
    question_bank = relationship("QuestionBank", back_populates="assessment_questions")  # NEW


class QuestionBank(Base):
    __tablename__ = "question_bank"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, nullable=False)
    subtopic = Column(String, nullable=True)
    grade_level = Column(String, nullable=False)
    prerequisites = Column(JSON, nullable=True)  # Array of prerequisite
    description = Column(Text, nullable=True)
    learning_objectives = Column(JSON, nullable=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String, nullable=False)  # "multiple_choice", "short_answer", "true_false", etc.
    options = Column(JSON, nullable=True)  # For multiple choice questions
    correct_answer = Column(Text, nullable=False)
    difficulty_level = Column(Float, default=0.5)  # 0.0-1.0 scale
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    assessment_questions = relationship("AssessmentQuestion", back_populates="question_bank")  # NEW


class StudentKnowledgeProfile(Base):
    __tablename__ = "student_knowledge_profiles"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student_profiles.id"), nullable=False)
    # knowledge_area_id = Column(Integer, ForeignKey("knowledge_areas.id"), nullable=False)
    mastery_level = Column(Float, default=0.0)  # 0.0-1.0, where 1.0 is complete mastery
    confidence_score = Column(Float, default=0.5)  # AI confidence in the mastery assessment
    last_assessed = Column(DateTime(timezone=True), nullable=True)
    assessment_count = Column(Integer, default=0)
    needs_review = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    # student = relationship("StudentProfile", back_populates="knowledge_profile")
    # knowledge_area = relationship("QuestionBank")
