"""Schemas for the KaihleAdmin question review queue.

Handles both TEACHER_QUESTION (teacher-submitted questions pending promotion)
and EDIT_SUGGESTION (teacher-proposed edits to existing questions) item types.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class QuestionReviewItemResponse(BaseModel):
    """A pending review item in the KaihleAdmin queue."""

    id: UUID
    item_type: str  # 'TEACHER_QUESTION' | 'EDIT_SUGGESTION'
    question_id: UUID
    # Current question_bank content
    question_text: str
    question_type: str
    options: list[dict[str, str]] | None
    correct_answer: str
    explanation: str | None
    difficulty_level: float | None
    subtopic_name: str
    topic_name: str
    # Submission metadata
    school_name: str
    submitted_by_name: str
    assessment_id: UUID | None
    # Suggested changes (populated for EDIT_SUGGESTION; None for TEACHER_QUESTION)
    suggested_question_text: str | None
    suggested_options: list[dict[str, str]] | None
    suggested_correct_answer: str | None
    suggested_explanation: str | None
    suggested_difficulty_level: float | None
    reason: str | None
    # Review state
    status: str
    admin_note: str | None
    created_at: datetime


class QuestionReviewListResponse(BaseModel):
    items: list[QuestionReviewItemResponse]
    total: int
    page: int
    page_size: int


class ApproveReviewItemRequest(BaseModel):
    """Optional admin edits applied before promoting / applying changes.

    For TEACHER_QUESTION: these override the submitted question content before
    promoting to global bank. Omitted fields keep the original submitted values.

    For EDIT_SUGGESTION: these override the teacher's suggested fields before
    applying to question_bank. Omitted fields fall back to the teacher's suggestion.
    """

    question_text: str | None = None
    options: list[dict[str, str]] | None = None
    correct_answer: str | None = None
    explanation: str | None = None
    difficulty_level: float | None = Field(default=None, ge=1.0, le=5.0)


class RejectReviewItemRequest(BaseModel):
    admin_note: str | None = None
