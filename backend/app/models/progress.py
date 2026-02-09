import uuid
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class Progress(Base):
    __tablename__ = "progress"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"), nullable=False)  # FIXED
    week_start = Column(DateTime(timezone=True), nullable=False)
    points_earned = Column(Integer, default=0)
    streak_days = Column(Integer, default=0)
    lessons_completed = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    # student = relationship("StudentProfile", back_populates="progress_records")  # FIXED
