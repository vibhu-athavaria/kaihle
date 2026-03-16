"""Pydantic schemas for onboarding-related API requests and responses.

Covers: questionnaire submission, learning profile responses, onboarding status.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.questionnaire_config import get_option_by_key, get_question_by_id

VALID_QUESTION_IDS = {"q1", "q2", "q3", "q4", "q5", "q6_to_q10"}
SINGLE_SELECT_QUESTIONS = {"q1", "q2", "q3", "q4", "q5"}
MULTI_SELECT_QUESTIONS = {"q6_to_q10"}


class ResponseAnswer(BaseModel):
    """Schema for a single questionnaire answer submission.

    For single-select questions (q1-q5), use answer_key.
    For multi-select questions (q6_to_q10), use answer_keys.
    """

    question_id: str = Field(..., description="Question identifier (e.g., 'q1', 'q2')")
    answer_key: str | None = Field(None, description="Selected option key for single-select questions")
    answer_keys: list[str] | None = Field(None, description="Selected option keys for multi-select questions")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_response(self) -> "ResponseAnswer":
        question_id = self.question_id
        answer_key = self.answer_key
        answer_keys = self.answer_keys

        if question_id not in VALID_QUESTION_IDS:
            raise ValueError(
                f"Invalid question_id: {question_id}. Must be one of: {', '.join(sorted(VALID_QUESTION_IDS))}"
            )

        if question_id in SINGLE_SELECT_QUESTIONS:
            if answer_keys is not None:
                raise ValueError(f"question_id '{question_id}' is single-select, use 'answer_key' not 'answer_keys'")
            if answer_key is None:
                raise ValueError(f"answer_key is required for single-select question '{question_id}'")
            option = get_option_by_key(question_id, answer_key)
            if option is None:
                question = get_question_by_id(question_id)
                if question is None:
                    raise ValueError(f"Question not found: {question_id}")
                valid_keys = [str(opt["key"]) for opt in question.get("options", [])]
                raise ValueError(
                    f"Invalid answer_key '{answer_key}' for question '{question_id}'. Valid keys: {', '.join(valid_keys)}"
                )

        if question_id in MULTI_SELECT_QUESTIONS:
            if answer_key is not None:
                raise ValueError(f"question_id '{question_id}' is multi-select, use 'answer_keys' not 'answer_key'")
            if answer_keys is None or len(answer_keys) == 0:
                raise ValueError(f"answer_keys is required for multi-select question '{question_id}'")
            question = get_question_by_id(question_id)
            if question is None:
                raise ValueError(f"Question not found: {question_id}")
            valid_keys_set = {str(opt["key"]) for opt in question.get("options", [])}
            invalid_keys = [k for k in answer_keys if k not in valid_keys_set]
            if invalid_keys:
                raise ValueError(
                    f"Invalid answer_keys {invalid_keys} for question '{question_id}'. Valid keys: {', '.join(sorted(valid_keys_set))}"
                )

        return self


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


class DiagnosticStatusByClass(BaseModel):
    """Schema for per-class diagnostic status breakdown."""

    class_id: UUID = Field(..., description="Class identifier")
    class_name: str = Field(..., description="Class name")
    status: str = Field(..., description="Diagnostic status for this class enrollment")


class LearningProfileStatusResponse(BaseModel):
    """Schema for learning profile completion status."""

    completed: bool = Field(..., description="Whether learning profile questionnaire is completed")
    completed_at: datetime | None = Field(None, description="Timestamp when completed (null if not completed)")

    model_config = ConfigDict(from_attributes=True)


class OnboardingStatusResponse(BaseModel):
    """Schema for onboarding status response.

    Returns learning profile completion status, diagnostics completion status,
    and overall onboarding status. Includes per-class diagnostic breakdown.
    """

    learning_profile_complete: bool = Field(..., description="True if learning profile questionnaire is submitted")
    diagnostics_by_class: list[DiagnosticStatusByClass] = Field(
        default_factory=list, description="Per-class diagnostic status breakdown"
    )

    model_config = ConfigDict(from_attributes=True)


class OnboardingPendingResponse(BaseModel):
    """Schema for pending onboarding status response.

    Returns list of students who have not completed their learning profile
    """

    student_id: UUID
    student_name: str = Field(..., description="Student name")
    learning_profile_complete: bool = Field(..., description="True if learning profile questionnaire is submitted")

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
