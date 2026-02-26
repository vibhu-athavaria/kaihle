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


class TeacherResponse(BaseModel):
    """Response model for teacher data."""
    teacher_id: str
    name: str
    email: str
    is_active: bool
    created_at: Optional[str] = None


class StudentResponse(BaseModel):
    """Response model for student data."""
    student_id: str
    name: str
    email: str
    grade: str
    grade_id: Optional[str] = None
    diagnostic_status: str
    plans_linked: int
    plans_total: int
    avg_progress_pct: float


class SubtopicProgress(BaseModel):
    """Model for individual subtopic progress."""
    class_subtopic_id: str
    subtopic_name: str
    status: str
    time_spent_minutes: int
    completed_at: Optional[str] = None


class StudentProgress(BaseModel):
    """Response model for student progress data."""
    student_id: str
    subtopics: List[SubtopicProgress]


class GradeResponse(BaseModel):
    """Response model for grade data."""
    grade_id: str
    name: str
    level: int


__all__ = [
    'SchoolAdminRequest',
    'SchoolAdminResponse',
    'TeacherCreateRequest',
    'TeacherListResponse',
    'DashboardStats',
    'TeacherResponse',
    'StudentResponse',
    'StudentProgress',
    'SubtopicProgress',
    'GradeResponse'
]
