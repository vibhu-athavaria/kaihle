# app/schemas/study_plan.py

from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID

from app.schemas.course import CourseBase


# -----------------------------
# StudyPlan Schemas
# -----------------------------
class StudyPlan(BaseModel):
    title: str = "Personalized Study Plan"
    summary: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Any] = None


class StudyPlanCreate(StudyPlan):
    assessment_id: Optional[UUID] = None
    student_id: UUID
    course_ids: Optional[List[UUID]] = []  # quick link courses
    courses: List[CourseBase] = []  # full course objects


class StudyPlanUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Any] = None
    is_active: Optional[bool] = None


class StudyPlanOut(StudyPlan):
    id: UUID
    assessment_id: Optional[UUID] = None
    student_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    courses: List[CourseBase] = []

    class Config:
        from_attributes = True

# -----------------------------
# StudyPlanCourse Schemas
# -----------------------------
class StudyPlanCourseBase(BaseModel):
    title: str
    knowledge_area_id: Optional[UUID] = None
    suggested_duration_mins: Optional[int] = None
    week: Optional[int] = None
    details: Optional[str] = None


class StudyPlanCourseCreate(StudyPlanCourseBase):
    order_index: Optional[int] = None


class StudyPlanCourseUpdate(BaseModel):
    is_completed: Optional[bool] = None


class StudyPlanCourseOut(StudyPlanCourseBase):
    id: UUID
    study_plan_id: UUID
    course_id: Optional[UUID] = None
    order_index: Optional[int] = None
    is_completed: bool = False
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

