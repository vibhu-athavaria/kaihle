from pydantic import BaseModel, EmailStr
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from app.models.school import SchoolStatus, PlanTier
from app.models.school_registration import RegistrationStatus


# School Schemas
class SchoolBase(BaseModel):
    name: str
    country: Optional[str] = None
    timezone: str = "Asia/Makassar"


class SchoolCreate(SchoolBase):
    curriculum_id: UUID


class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None


class SchoolInDBBase(SchoolBase):
    id: UUID
    admin_id: UUID
    slug: str
    school_code: Optional[str] = None
    curriculum_id: UUID
    status: SchoolStatus
    plan_tier: PlanTier
    approved_at: Optional[datetime] = None
    approved_by: Optional[UUID] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class School(SchoolInDBBase):
    pass


class SchoolWithDetails(SchoolInDBBase):
    # Could include relationships here if needed
    pass


# School Grade Schemas
class SchoolGradeBase(BaseModel):
    school_id: UUID
    grade_id: UUID


class SchoolGradeCreate(SchoolGradeBase):
    pass


class SchoolGradeInDBBase(SchoolGradeBase):
    id: UUID
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SchoolGrade(SchoolGradeInDBBase):
    pass


# Student Registration Schemas
class StudentRegistrationBase(BaseModel):
    school_id: UUID
    student_id: UUID
    status: RegistrationStatus
    grade_id: Optional[UUID] = None
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None


class StudentRegistrationCreate(BaseModel):
    school_id: UUID
    student_id: UUID


class StudentRegistrationUpdate(BaseModel):
    status: Optional[RegistrationStatus] = None
    grade_id: Optional[UUID] = None
    reviewed_by: Optional[UUID] = None


class StudentRegistrationInDBBase(StudentRegistrationBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class StudentRegistration(StudentRegistrationInDBBase):
    pass


class StudentRegistrationWithDetails(StudentRegistrationInDBBase):
    # Could include relationships here if needed
    pass


# Dashboard Schemas
class SchoolDashboard(BaseModel):
    student_count: int = 0
    pending_registrations: int = 0
    teacher_count: int = 0
    class_count: int = 0
    avg_assessment_pct: float = 0.0