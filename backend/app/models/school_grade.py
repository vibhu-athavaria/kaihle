# app/models/school_grade.py
import uuid
from sqlalchemy import Column, Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from app.crud.mixin import SerializerMixin


class SchoolGrade(Base, SerializerMixin):
    __tablename__ = 'school_grades'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), ForeignKey('schools.id', ondelete='CASCADE'), nullable=False)
    grade_id = Column(UUID(as_uuid=True), ForeignKey('grades.id'), nullable=False)
    # ↑ References EXISTING grades table (Grade 5–12). Do NOT create a new grades table.
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint('school_id', 'grade_id'),
                      Index('idx_sg_school_id', 'school_id'))

    # Relationships
    school = relationship("School", back_populates="school_grades")
    grade = relationship("Grade", back_populates="school_grades")