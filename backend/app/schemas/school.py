"""Pydantic schemas for school management."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class SchoolCreate(BaseModel):
    """Schema for creating a new school."""

    name: str
    slug: str  # URL-safe identifier e.g. "bali-green-school"
    country: str | None = None
    timezone: str | None = "UTC"


class SchoolUpdate(BaseModel):
    """Schema for updating a school."""

    name: str | None = None
    country: str | None = None
    timezone: str | None = None
    is_active: bool | None = None


class SchoolResponse(BaseModel):
    """Schema for school response."""

    id: uuid.UUID
    name: str
    slug: str
    country: str | None
    timezone: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class SchoolListResponse(BaseModel):
    """Schema for paginated school list response."""

    schools: list[SchoolResponse]
    total: int
    page: int
    page_size: int


# ===========================================
# Class and Enrollment Schemas
# ===========================================


class ClassCreate(BaseModel):
    """Schema for creating a new class."""

    name: str
    grade_id: uuid.UUID
    subject_id: uuid.UUID
    curriculum_id: uuid.UUID
    teacher_id: uuid.UUID
    academic_year: str = Field(..., description="e.g. '2025-2026'")


class ClassResponse(BaseModel):
    """Schema for class response."""

    id: uuid.UUID
    school_id: uuid.UUID
    grade_id: uuid.UUID
    subject_id: uuid.UUID
    curriculum_id: uuid.UUID
    teacher_id: uuid.UUID
    name: str
    academic_year: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class EnrollRequest(BaseModel):
    """Schema for enrolling students in a class."""

    student_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class EnrollResponse(BaseModel):
    """Schema for enrollment response."""

    enrolled: int
    skipped: int
    errors: list[str]


class StudentSummary(BaseModel):
    """Schema for student summary in class enrollment."""

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str

    model_config = ConfigDict(from_attributes=True)
