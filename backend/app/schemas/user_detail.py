"""Pydantic schemas for user detail views (school-admin)."""

import uuid

from pydantic import BaseModel


class GapStateDetail(BaseModel):
    subtopic_name: str
    mastery_score: float | None


class ClassEnrollmentDetail(BaseModel):
    class_id: uuid.UUID
    class_name: str
    teacher_name: str
    gap_states: list[GapStateDetail]


class StudentDetailResponse(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    grade_level: int
    curriculum_name: str
    enrolled_at: str
    last_login_at: str | None
    class_enrollments: list[ClassEnrollmentDetail]


class AssignedClassSummary(BaseModel):
    class_id: uuid.UUID
    class_name: str
    subject_name: str
    grade_level: int
    student_count: int
    avg_mastery: float | None


class TeacherDetailResponse(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    is_active: bool
    assigned_classes: list[AssignedClassSummary]


class LinkedStudentSummary(BaseModel):
    student_id: uuid.UUID
    first_name: str
    last_name: str
    worst_mastery: float | None
    class_count: int


class ParentDetailResponse(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    is_active: bool
    linked_students: list[LinkedStudentSummary]
