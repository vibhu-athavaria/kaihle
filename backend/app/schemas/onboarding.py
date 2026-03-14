"""Pydantic schemas for onboarding-related API requests and responses.

Covers: questionnaire submission, learning profile responses, onboarding status.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResponseAnswer(BaseModel):
    """Schema for a single questionnaire answer submission.

    For single-select questions (q1-q5), use answer_key.
    For multi-select questions (q6-q10), use answer_keys.
    """

    question_id: str = Field(..., description="Question identifier (e.g., 'q1', 'q2')")
    answer_key: str | None = Field(None, description="Selected option key for single-select questions")
    answer_keys: list[str] | None = Field(None, description="Selected option keys for multi-select questions")

    model_config = ConfigDict(extra="forbid")


class QuestionnaireSubmitRequest(BaseModel):
    """Request schema for submitting questionnaire responses."""

    responses: list[ResponseAnswer] = Field(..., min_length=6, description="List of answers to all 6 question groups")

    model_config = ConfigDict(extra="forbid")


class QuestionnaireOption(BaseModel):
    """Schema for a single questionnaire option."""

    key: str = Field(..., description="Unique option identifier")
    text: str = Field(..., description="Display text for the option")
    emoji: str | None = Field(None, description="Optional emoji for the option")
    maps_to: dict[str, Any] | None = Field(None, description="Mapping information for scoring")


class QuestionnaireQuestion(BaseModel):
    """Schema for a single questionnaire question."""

    id: str = Field(..., description="Unique question identifier")
    text: str = Field(..., description="Question text")
    type: str = Field(..., description="Question type: single_select or multi_select")
    maps_to: str | None = Field(None, description="What field this question maps to")
    options: list[QuestionnaireOption] = Field(..., description="Available options")


class QuestionnaireDefinition(BaseModel):
    """Schema for the full questionnaire definition."""

    version: str = Field(..., description="Questionnaire version identifier")
    questions: list[QuestionnaireQuestion] = Field(..., description="List of questions")


class OnboardingStatus(BaseModel):
    """Schema for onboarding status response.

    Overall status:
    - COMPLETED: both profile and diagnostics complete
    - IN_PROGRESS: either profile or diagnostics started
    - PENDING: neither started
    """

    learning_profile_complete: bool = Field(..., description="True if learning profile questionnaire is submitted")
    diagnostics_complete: bool = Field(..., description="True if all tier-1 diagnostics are completed")
    overall: str = Field(..., pattern="^(PENDING|IN_PROGRESS|COMPLETED)$")


class DiagnosticStatusByClass(BaseModel):
    """Schema for per-class diagnostic status breakdown."""

    class_id: UUID = Field(..., description="Class identifier")
    class_name: str = Field(..., description="Class name")
    status: str = Field(..., description="Diagnostic status for this class enrollment")


class OnboardingStatusResponse(BaseModel):
    """Extended schema for onboarding status with per-class breakdown."""

    learning_profile_complete: bool = Field(..., description="True if learning profile questionnaire is submitted")
    diagnostics_status: str = Field(
        ..., pattern="^(PENDING|IN_PROGRESS|COMPLETED)$", description="Aggregated diagnostic status"
    )
    overall: str = Field(..., pattern="^(PENDING|IN_PROGRESS|COMPLETED)$")
    diagnostics_by_class: list[DiagnosticStatusByClass] = Field(
        default_factory=list, description="Per-class diagnostic status breakdown"
    )

    model_config = ConfigDict(from_attributes=True)


class StudentLearningProfileResponse(BaseModel):
    """Schema for student learning profile response.

    Contains the complete learning profile with modality scores,
    work style preferences, and interests.
    """

    id: UUID
    student_id: UUID
    school_id: UUID
    modality_scores: dict[str, float] = Field(
        ..., description="Scores for each modality (visual, auditory, reading_writing, kinesthetic)"
    )
    work_style: dict[str, bool] = Field(
        ..., description="Work style preferences (prefers_solo, short_sessions, concept_first, task_based)"
    )
    interests: list[str] | None = Field(None, description="Selected interests from the questionnaire")
    questionnaire_version: str = Field(..., description="Version of questionnaire used")
    completed_at: datetime | None = Field(None, description="When the questionnaire was completed")
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
