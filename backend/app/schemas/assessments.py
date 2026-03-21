"""Assessment schemas. Note: correct_answer is NEVER in student-facing responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class QuestionOption(BaseModel):
    key: str  # e.g. "a", "b", "c", "d"
    text: str


class AssessmentQuestion(BaseModel):
    """Student-facing question — no correct_answer field by design."""

    question_id: UUID
    question_text: str
    options: list[QuestionOption]


class AssessmentQuestionWithAnswer(AssessmentQuestion):
    """Teacher/admin-facing question — includes correct_answer for review."""

    correct_answer_key: str
    explanation: str | None


class AssessmentResponse(BaseModel):
    id: UUID
    class_id: UUID
    title: str
    assessment_type: str  # "DIAGNOSTIC" | "PROGRESS_CHECK"
    is_system_generated: bool  # True = Tier 1, False = Tier 2
    status: str  # "DRAFT" | "ACTIVE" | "CLOSED"
    topic_ids: list[UUID]
    question_count: int
    created_at: datetime
    published_at: datetime | None
    deadline: datetime | None


class AssessmentCreateRequest(BaseModel):
    title: str
    topic_ids: list[UUID]
    question_count: int = 20
    deadline: datetime | None = None
