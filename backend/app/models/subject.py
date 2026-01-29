# app/models/subject.py
import uuid
from sqlalchemy import Column, Integer, String, Text, Boolean, TIMESTAMP, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from app.crud.mixin import SerializerMixin


class Subject(Base, SerializerMixin):
    """Core subject areas (Math, Science, English, etc.)"""
    __tablename__ = "subjects"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    code = Column(String(20), nullable=True, unique=True)  # "MATH", "SCI", "ENG"
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)
    color = Column(String(7), nullable=True)  # Hex color for UI
    is_active = Column(Boolean, default=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=text("now()"))

    # Relationships
    curriculum_topics = relationship("CurriculumTopic", back_populates="subject")
    micro_courses = relationship("MicroCourse", back_populates="subject")
    assessments = relationship("Assessment", back_populates="subject")
    question_banks = relationship("QuestionBank", back_populates="subject")
    lessons = relationship("Lesson", back_populates="subject")
    subscriptions = relationship("Subscription", back_populates="subject")