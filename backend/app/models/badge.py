# app/models/badge.py
import uuid
from app.core.database import Base
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID


class Badge(Base):
    __tablename__ = "badges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    icon = Column(String, nullable=True)
    color_key = Column(String(50), nullable=True)

    points_required = Column(Integer, nullable=True)
    # Relationships
    # student_badges = relationship("StudentBadge", back_populates="badge")

class StudentBadge(Base):
    __tablename__ = "student_badges"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"), nullable=False)  # FIXED
    badge_id = Column(UUID(as_uuid=True), ForeignKey("badges.id"), nullable=False)
    earned_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    student = relationship("StudentProfile")
    badge = relationship("Badge")
