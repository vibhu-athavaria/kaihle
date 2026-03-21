"""Analytics schemas — school-level and platform-level usage data."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ClassBreakdown(BaseModel):
    class_id: UUID
    class_name: str
    subject_name: str
    grade_name: str
    teacher_name: str
    student_count: int
    avg_mastery: float | None  # None if no assessments taken
    assessments_completed: int


class SchoolAnalytics(BaseModel):
    school_id: UUID
    school_name: str
    generated_at: datetime
    total_students: int
    active_students_last_7_days: int
    onboarding_completion_rate: float  # 0.0–1.0
    students_pending_onboarding: int
    assessments_completed: int
    study_plans_assigned: int
    study_plans_completed: int
    lesson_plans_generated: int
    lesson_plans_used: int
    classes: list[ClassBreakdown]


class PlatformStats(BaseModel):
    """KaihleAdmin view — platform-wide counts across all schools."""

    total_schools: int
    total_active_students: int
    total_teachers: int
    assessments_completed_last_7_days: int
    generated_at: datetime
