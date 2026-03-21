"""Study plan schemas — personalised per-student gap remediation plans."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class StudyPlanResource(BaseModel):
    resource_id: UUID
    title: str
    resource_type: str  # "VIDEO" | "ARTICLE" | "INTERACTIVE"
    url: str
    source: str  # "YOUTUBE" | "KHAN_ACADEMY" | "KAIHLE"
    duration_minutes: int | None
    is_watched: bool


class StudyPlanQuizQuestion(BaseModel):
    """Note: correct_answer is NEVER included — same rule as AssessmentQuestion."""

    question_index: int
    question_text: str
    options: list[dict[str, Any]]


class StudyPlanResponse(BaseModel):
    id: UUID
    student_id: UUID
    class_id: UUID
    subtopic_id: UUID
    subtopic_name: str
    status: str  # "GENERATING"|"ACTIVE"|"IN_PROGRESS"|"COMPLETED"
    resources: list[StudyPlanResource]
    quiz_questions: list[StudyPlanQuizQuestion]
    quiz_score: float | None  # None until quiz submitted
    created_at: datetime


class StudyPlanAssignRequest(BaseModel):
    subtopic_id: UUID
    student_ids: list[UUID] | None = Field(
        None,
        description="List of student UUIDs, or null to assign to all enrolled students",
    )


class StudyPlanAssignResponse(BaseModel):
    status: str = "generating"
    plans: list[dict[str, Any]]  # [{"plan_id": uuid, "student_id": uuid, "status": "GENERATING"}]


class QuizSubmitRequest(BaseModel):
    responses: list[dict[str, Any]]  # [{"question_index": int, "answer": str}]


class QuizSubmitResponse(BaseModel):
    score: float
    correct_count: int
    total_questions: int
    plan_status: str
