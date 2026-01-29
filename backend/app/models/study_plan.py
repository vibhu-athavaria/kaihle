# app/models/study_plan.py
import uuid
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from app.core.database import Base
from app.crud.mixin import SerializerMixin


class StudyPlan(Base, SerializerMixin):
    """
    Personalized learning roadmap for a student
    Generated from assessment results and knowledge gaps
    """
    __tablename__ = "study_plans"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String(255), nullable=False, default="Personalized Study Plan")
    description = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)

    # Plan configuration
    total_weeks = Column(Integer, nullable=True)
    hours_per_week = Column(Integer, nullable=True)

    # AI generation metadata
    generation_metadata = Column(JSONB, nullable=True)
    """
    Example:
    {
        "knowledge_gaps": [...],
        "priority_topics": [...],
        "learning_style_adaptations": {...},
        "model_version": "gpt-4"
    }
    """

    status = Column(String(20), default="active")  # "active", "completed", "paused", "archived"
    progress_percentage = Column(Integer, default=0)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('idx_sp_student_status', 'student_id', 'status'),
    )

    # Relationships
    student = relationship("StudentProfile", back_populates="study_plans")
    assessment = relationship("Assessment", back_populates="study_plan")
    study_plan_courses = relationship("StudyPlanCourse", back_populates="study_plan",
                                     cascade="all, delete-orphan", order_by="StudyPlanCourse.sequence_order")


class StudyPlanCourse(Base, SerializerMixin):
    """
    Individual lessons/activities within a study plan
    Can link to existing Lessons or be custom AI-generated content
    """
    __tablename__ = "study_plan_courses"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    study_plan_id = Column(UUID(as_uuid=True), ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True)

    # If course_id is NULL, this is custom content
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Content hierarchy
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    subtopic_id = Column(UUID(as_uuid=True), ForeignKey("subtopics.id", ondelete="SET NULL"), nullable=True, index=True)

    # Planning
    week = Column(Integer, nullable=True)
    day = Column(Integer, nullable=True)
    sequence_order = Column(Integer, nullable=False)  # Overall order in plan

    suggested_duration_mins = Column(Integer, nullable=True)
    activity_type = Column(String(50), nullable=True)  # "lesson", "practice", "review", "assessment"

    # Custom content if course_id is NULL
    custom_content = Column(JSONB, nullable=True)

    # Progress tracking
    status = Column(String(20), default="not_started")  # "not_started", "in_progress", "completed", "skipped"
    completed_at = Column(DateTime(timezone=True), nullable=True)
    time_spent_minutes = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('idx_spl_plan_sequence', 'study_plan_id', 'sequence_order'),
        Index('idx_spl_plan_week', 'study_plan_id', 'week'),
    )

    # Relationships
    study_plan = relationship("StudyPlan", back_populates="study_plan_courses")
    topic = relationship("Topic")
    subtopic = relationship("Subtopic")