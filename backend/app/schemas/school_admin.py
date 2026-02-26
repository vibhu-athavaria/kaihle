from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class SchoolAdminRequest(BaseModel):
    name: str
    email: str
    role: str  # 'teacher' or 'admin'
    school_id: str


class SchoolAdminResponse(BaseModel):
    teacher_id: str
    name: str
    email: str
    role: str
    school_id: str
    created_at: str  # ISO 8601 format


class TeacherCreateRequest(BaseModel):
    name: str
    email: str
    school_id: str


class TeacherListResponse(BaseModel):
    teachers: List[SchoolAdminResponse]


class DashboardStats(BaseModel):
    student_count: int
    pending_registrations: int
    teacher_count: int
    avg_assessment_pct: float


__all__ = [
    'SchoolAdminRequest',
    'SchoolAdminResponse',
    'TeacherCreateRequest',
    'TeacherListResponse',
    'DashboardStats'
]
