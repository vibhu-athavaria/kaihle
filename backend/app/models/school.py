# backend/app/models/school.py
import uuid
import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index, UniqueConstraint, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from app.crud.mixin import SerializerMixin


class SchoolStatus(str, enum.Enum):
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class PlanTier(str, enum.Enum):
    TRIAL = "trial"    # 30 students max
    STARTER = "starter"  # 100 students
    GROWTH = "growth"   # 500 students
    SCALE = "scale"    # unlimited


class School(Base, SerializerMixin):
    __tablename__ = "schools"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False, unique=True)
    school_code = Column(String(8), unique=True, nullable=True)  # NULL until approved
    curriculum_id = Column(UUID(as_uuid=True), ForeignKey('curricula.id'), nullable=False)
    country = Column(String(100), nullable=True)
    timezone = Column(String(64), nullable=False, default='Asia/Makassar')
    status = Column(SAEnum(SchoolStatus), nullable=False, default=SchoolStatus.PENDING_APPROVAL)
    plan_tier = Column(SAEnum(PlanTier), nullable=False, default=PlanTier.TRIAL)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    __table_args__ = (Index('idx_schools_status', 'status'),
                      Index('idx_schools_admin_id', 'admin_id'))

    # Relationships
    admin = relationship("User", backref="administered_school")
    teachers = relationship("Teacher", back_populates="school")
    students = relationship("StudentProfile", back_populates="school")
    school_grades = relationship("SchoolGrade", back_populates="school")
    student_registrations = relationship("StudentSchoolRegistration", back_populates="school")