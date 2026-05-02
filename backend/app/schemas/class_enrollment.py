"""Pydantic schemas for class management and enrollment."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class ClassCreate(BaseModel):
    """Schema for creating a new class."""

    name: str = Field(..., max_length=255)
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


class ClassWithSummary(BaseModel):
    """Extended class response with summary data for teacher dashboard."""

    id: uuid.UUID
    school_id: uuid.UUID
    grade_id: uuid.UUID
    subject_id: uuid.UUID
    curriculum_id: uuid.UUID
    teacher_id: uuid.UUID | None = None
    teacher_name: str | None = None
    has_teacher: bool = False
    name: str
    academic_year: str
    is_active: bool
    grade_name: str = ""
    subject_name: str = ""
    avg_mastery: float | None = None
    student_count: int = 0
    students_below_threshold: int = 0

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
    worst_mastery: float | None
    diagnostic_completed: bool
    grade_level: int | None = None

    model_config = ConfigDict(from_attributes=True)


class TeacherStudentItem(BaseModel):
    """Lightweight student summary for teacher's student list."""

    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    class_ids: list[uuid.UUID]
    class_names: list[str]


class TeacherStudentsResponse(BaseModel):
    """Response for teacher's aggregated student list."""

    students: list[TeacherStudentItem]
