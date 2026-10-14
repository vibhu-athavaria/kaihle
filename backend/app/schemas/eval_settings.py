"""Request/response schemas for the Kaihle Admin production-evaluation settings."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class StudentTextAcknowledgement(BaseModel):
    """Who accepted the privacy risk of evaluating a student-text task, and when (UTC)."""

    acknowledged_by: str
    acknowledged_at: str


class EvalSettingsUpdateRequest(BaseModel):
    """Full replacement of the editable settings. Range and allowlist rules are enforced by
    `PlatformSettingsService` (single source), which the route maps to 422."""

    eval_monthly_budget_usd: Decimal
    eval_enabled_tasks: list[str]
    eval_sample_size_per_task: int
    eval_window_days: int
    eval_include_indicative: bool
    # Student-text tasks being newly acknowledged by this request. Already-acknowledged
    # tasks need not be repeated.
    acknowledge_student_text_tasks: list[str] = Field(default_factory=list)


class EvalSettingsResponse(BaseModel):
    eval_monthly_budget_usd: float
    eval_enabled_tasks: list[str]
    eval_sample_size_per_task: int
    eval_window_days: int
    eval_include_indicative: bool
    student_text_acknowledgements: dict[str, StudentTextAcknowledgement]
    # Static facts the UI needs to render the allowlist without hardcoding task names.
    available_tasks: list[str]
    tasks_with_student_text: list[str]
    # NULL until first saved / if the editor's account was deleted.
    updated_by: str | None
    updated_at: datetime | None
