"""Assessment schemas. Note: correct_answer is NEVER in student-facing responses."""

from datetime import datetime
from typing import Literal
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
    title: str | None = None  # Auto-generated from type+class+subject when omitted
    topic_ids: list[UUID]
    question_count: int = 20
    assessment_type: str = "PROGRESS_CHECK"  # DIAGNOSTIC | TOPIC_SPECIFIC | PROGRESS_CHECK
    difficulty_min: float = 1.0
    difficulty_max: float = 5.0
    deadline: datetime | None = None


class StudentAttemptSummary(BaseModel):
    attempt_id: UUID | None = None  # None when NOT_STARTED — student has not begun
    student_id: UUID
    student_name: str
    score: float | None
    submitted_at: datetime | None
    status: Literal["SUBMITTED", "IN_PROGRESS", "NOT_STARTED"]


class AssessmentResultsSummary(BaseModel):
    assessment_id: UUID
    assessment_title: str
    assessment_type: str
    class_id: UUID
    class_name: str
    total_students: int
    submitted_count: int
    attempts: list[StudentAttemptSummary]
