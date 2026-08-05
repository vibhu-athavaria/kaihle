"""Lesson plan schemas."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SubtopicContext(BaseModel):
    subtopic_id: UUID
    name: str
    topic_name: str


class LessonPlanResponse(BaseModel):
    id: UUID
    class_id: UUID
    class_name: str
    # NULL when the class has no grade assigned — the UI falls back to class_name.
    grade_name: str | None = None
    week_start: date | None
    status: str  # "GENERATING" | "GENERATED" | "EDITED" | "USED" | "ARCHIVED"
    duration_minutes: int
    generated_plan: dict[str, Any] | None
    teacher_edits: dict[str, Any] | None
    class_context_snapshot: dict[str, Any]
    focus_subtopics: list[SubtopicContext]
    generated_at: datetime
    failure_code: str | None = None
    failure_reason: str | None = None

    model_config = {"from_attributes": True}


class GenerateLessonPlanRequest(BaseModel):
    focus_subtopic_ids: list[UUID]
    duration_minutes: int = Field(default=45, ge=30, le=120)


class LessonPlanEditRequest(BaseModel):
    """All fields optional — PATCH merges only the fields provided into teacher_edits."""

    # Top-level text fields
    prior_knowledge: str | None = None
    teacher_tips: str | None = None
    homework: str | None = None

    # List fields
    learning_objectives: list[str] | None = None
    key_concepts: list[dict[str, str]] | None = None
    real_world_applications: list[dict[str, str]] | None = None
    resources_needed: list[str] | None = None
    common_misconceptions: list[str] | None = None

    # Nested section overrides
    starter: dict[str, Any] | None = None
    main_activity: dict[str, Any] | None = None
    formative_check: dict[str, Any] | None = None
    plenary: dict[str, Any] | None = None


class LessonPlanStatusRequest(BaseModel):
    status: str  # "USED" | "ARCHIVED"
