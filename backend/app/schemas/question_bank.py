"""Question Bank schemas — KaihleAdmin question browser and editor."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class QuestionBankResponse(BaseModel):
    """Response schema for a single question with curriculum context."""

    id: UUID
    question_text: str
    question_type: str
    options: list[dict[str, Any]] | None
    correct_answer: str
    explanation: str | None
    difficulty_level: float | None
    is_active: bool
    meta_tags: dict[str, Any] | None = None
    source: str | None = None
    replaces_question_id: UUID | None = None
    subtopic_id: UUID | None
    created_at: datetime
    updated_at: datetime | None

    # Curriculum context (from join)
    curriculum_id: UUID | None
    curriculum_name: str | None
    subject_id: UUID | None
    subject_name: str | None
    grade_id: UUID | None
    grade_name: str | None
    topic_id: UUID | None
    topic_name: str | None
    subtopic_name: str | None
    curriculum_topic_id: UUID | None

    model_config = {"from_attributes": True}


class QuestionBankListResponse(BaseModel):
    """Paginated response for question list."""

    questions: list[QuestionBankResponse]
    total: int
    page: int
    page_size: int


class QuestionBankUpdateRequest(BaseModel):
    """
    All fields optional — PATCH semantics.
    Omitted fields are not updated.
    Pass subtopic_id to reassign curriculum context (must exist in DB).
    Nullable fields (explanation, difficulty_level) can be explicitly set to null to clear them.
    """

    question_text: str | None = None
    question_type: str | None = None
    options: list[dict[str, Any]] | None = None
    correct_answer: str | None = None
    explanation: str | None = None
    difficulty_level: float | None = Field(None, ge=1.0, le=5.0)
    is_active: bool | None = None
    subtopic_id: UUID | None = None


class QuestionBankCreateRequest(BaseModel):
    """Request schema for creating a new question in the bank."""

    subtopic_id: UUID
    question_text: str
    question_type: str
    options: list[dict[str, Any]] | None = None
    correct_answer: str
    explanation: str | None = None
    difficulty_level: float | None = Field(None, ge=1.0, le=5.0)
    is_active: bool = True
