# backend/app/schemas/student_dashboard.py
"""Pydantic schemas for GET /students/me/dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ActionItem(BaseModel):
    """One actionable item surfaced on the student dashboard."""

    model_config = ConfigDict(populate_by_name=True)

    type: Literal[
        "assessment_due",
        "lesson_pack_ready",
        "study_plan_continue",
        "diagnostic_pending",
    ]
    class_id: UUID
    class_name: str
    subject_name: str
    priority: int  # 1 = today / urgent, 2 = this week, 3 = nudge
    due_date: datetime | None = None
    action_url: str  # frontend-relative path, e.g. "/student/assessments"


class ClassSummary(BaseModel):
    """Dashboard summary for one enrolled class."""

    model_config = ConfigDict(populate_by_name=True)

    class_id: UUID
    class_name: str
    subject_id: UUID
    subject_name: str
    subject_color: str  # Tailwind class name, e.g. "bg-brand-primary"
    teacher_name: str
    mastery_score: float | None  # None = no gap states yet
    mastery_label: str  # "Strong" | "Developing" | "Needs Work" | "Not assessed"
    topics_total: int
    topics_assessed: int
    diagnostic_status: Literal["PENDING", "IN_PROGRESS", "COMPLETED"]
    trend: Literal["up", "down", "flat", "none"]


class DashboardResponse(BaseModel):
    """Full response for GET /students/me/dashboard."""

    model_config = ConfigDict(populate_by_name=True)

    student_name: str
    grade: str
    curriculum: str
    action_items: list[ActionItem]  # sorted: priority asc, due_date asc nulls last
    classes: list[ClassSummary]
