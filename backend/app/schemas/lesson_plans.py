"""Lesson plan schemas — AI-generated weekly plans for teachers."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class LessonPlanResponse(BaseModel):
    id: UUID
    class_id: UUID
    week_start: date
    status: str  # "GENERATED" | "EDITED" | "USED" | "ARCHIVED"
    generated_plan: dict[str, Any] | None  # full JSON structure from LLM
    teacher_edits: dict[str, Any] | None  # sparse delta — only fields teacher changed
    created_at: datetime


class LessonPlanEditRequest(BaseModel):
    """All fields optional — PATCH applies only the fields provided."""

    starter_10min: str | None = None
    group_a_activity: str | None = None
    group_b_activity: str | None = None
    group_c_activity: str | None = None
    plenary_10min: str | None = None
    homework: str | None = None
    teacher_notes: str | None = None


class LessonPlanStatusRequest(BaseModel):
    status: str  # "USED" | "ARCHIVED"
