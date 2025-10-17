# app/models/lesson.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    difficulty_level = Column(String, nullable=True)  # beginner, intermediate, advanced
    subject = Column(String, nullable=True)
    # knowledge_area_id = Column(Integer, ForeignKey("knowledge_areas.id"), nullable=True)
    points_value = Column(Integer, default=10)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    study_plan_lessons = relationship("StudyPlanLesson", back_populates="lesson")


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=True)  # optional link to origin assessment
    student_id = Column(Integer, ForeignKey("student_profiles.id"), nullable=False)
    title = Column(String, nullable=False, default="Personalized Study Plan")
    summary = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)  # raw AI payload / parameters used
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    assessment = relationship("Assessment", back_populates="study_plan")
    # student = relationship("StudentProfile", back_populates="study_plans")
    study_plan_lessons = relationship("StudyPlanLesson", back_populates="study_plan", cascade="all, delete-orphan")


class StudyPlanLesson(Base):
    __tablename__ = "study_plan_lessons"

    id = Column(Integer, primary_key=True, index=True)
    study_plan_id = Column(Integer, ForeignKey("study_plans.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=True)  # <-- link to Lesson
    title = Column(String, nullable=False)
    # knowledge_area_id = Column(Integer, ForeignKey("knowledge_areas.id"), nullable=True)
    suggested_duration_mins = Column(Integer, nullable=True)
    week = Column(Integer, nullable=True)  # week index in the plan
    details = Column(Text, nullable=True)  # human readable task/instructions
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    study_plan = relationship("StudyPlan", back_populates="study_plan_lessons")
    lesson = relationship("Lesson", back_populates="study_plan_lessons")  # <-- new

