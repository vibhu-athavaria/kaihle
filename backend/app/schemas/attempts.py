"""Student attempt schemas — the assessment-taking flow."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.assessments import AssessmentQuestion


class AttemptResponse(BaseModel):
    id: UUID
    assessment_id: UUID
    student_id: UUID
    title: str  # Assessment title for display in the UI
    status: str  # "NOT_STARTED" | "IN_PROGRESS" | "SUBMITTED"
    started_at: datetime | None
    submitted_at: datetime | None
    score: float | None  # None until submitted and scored
    questions: list[AssessmentQuestion]  # empty until attempt is started


class AnswerSubmitRequest(BaseModel):
    question_id: UUID
    selected_key: str  # the option key the student chose


class AttemptSubmitRequest(BaseModel):
    """Submit all answers at once — used when student clicks final Submit."""

    answers: list[AnswerSubmitRequest]


class AttemptResultResponse(BaseModel):
    attempt_id: UUID
    score: float  # 0.0–1.0 e.g. 0.75 = 75%
    total_questions: int
    correct_count: int
    time_taken_seconds: int | None
    submitted_at: datetime


class StudentAttemptHistoryItem(BaseModel):
    attempt_id: UUID
    assessment_id: UUID
    assessment_title: str
    assessment_type: str
    class_id: UUID
    class_name: str
    score: float | None
    status: str
    submitted_at: datetime | None
    created_at: datetime
