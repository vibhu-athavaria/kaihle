# app/models/school_registration.py
import uuid
import enum
from sqlalchemy import Column, DateTime, ForeignKey, Index, UniqueConstraint, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from app.crud.mixin import SerializerMixin


class RegistrationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class StudentSchoolRegistration(Base, SerializerMixin):
    __tablename__ = 'student_school_registrations'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), ForeignKey('schools.id'), nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey('student_profiles.id'), nullable=False)
    status = Column(SAEnum(RegistrationStatus), nullable=False, default=RegistrationStatus.PENDING)
    grade_id = Column(UUID(as_uuid=True), ForeignKey('grades.id'), nullable=True)
    # ↑ Set on approval. References EXISTING grades.id — same FK as student_profiles.grade_id
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint('school_id', 'student_id'),
                      Index('idx_ssr_school_status', 'school_id', 'status'))

    # Relationships
    school = relationship("School", back_populates="student_registrations")
    student = relationship("StudentProfile", back_populates="school_registrations")
    grade = relationship("Grade")
    reviewer = relationship("User", foreign_keys=[reviewed_by])