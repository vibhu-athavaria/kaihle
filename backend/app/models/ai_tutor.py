import uuid
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class TutorSession(Base):
    __tablename__ = "tutor_sessions"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"), nullable=False)
    session_type = Column(String, nullable=False)  # "recommendation", "question", "evaluation"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    # student = relationship("StudentProfile", back_populates="tutor_sessions")
    interactions = relationship("TutorInteraction", back_populates="session", cascade="all, delete-orphan")


class TutorInteraction(Base):
    __tablename__ = "tutor_interactions"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("tutor_sessions.id"), nullable=False)
    user_message = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    context_data = Column(JSON, nullable=True)  # Store additional context like lesson info, progress data
    feedback_score = Column(Integer, nullable=True)  # 1-5 rating from user
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("TutorSession", back_populates="interactions")
