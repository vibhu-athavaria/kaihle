# backend/app/models/teacher.py
import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base
from app.crud.mixin import SerializerMixin


class Teacher(Base, SerializerMixin):
    __tablename__ = "teachers"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False, index=True)
    qualifications = Column(JSONB, nullable=True)  # e.g., ["Bachelor's in Math", "Teaching Certificate"]
    subjects_taught = Column(JSONB, nullable=True)  # list of subject_ids or names
    experience_years = Column(Integer, nullable=True)
    bio = Column(Text, nullable=True)
    hire_date = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="teacher_profile")
    school = relationship("School", back_populates="teachers")