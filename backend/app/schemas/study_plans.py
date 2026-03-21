"""Study plan schemas — personalised per-student gap remediation plans."""

from datetime import datetime
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


class StudyPlanQuizOption(BaseModel):
    """Quiz option for study plan questions — matches AssessmentQuestion pattern."""

    key: str  # e.g. "a", "b", "c", "d"
    text: str


class StudyPlanQuizQuestion(BaseModel):
    """Note: correct_answer is NEVER included — same rule as AssessmentQuestion."""

    question_index: int
    question_text: str
    options: list[StudyPlanQuizOption]


class StudyPlanItem(BaseModel):
    """Individual study plan in an assign response."""

    plan_id: UUID
    student_id: UUID
    status: str  # "GENERATING"


class StudyPlanAssignRequest(BaseModel):
    subtopic_id: UUID
    student_ids: list[UUID] | None = Field(
        None,
        description="List of student UUIDs, or null to assign to all enrolled students",
    )


class StudyPlanAssignResponse(BaseModel):
    status: str = "generating"
    plans: list[StudyPlanItem]


class QuizResponse(BaseModel):
    """Individual quiz response in a submit request."""

    question_index: int
    answer: str


class QuizSubmitRequest(BaseModel):
    responses: list[QuizResponse]


class QuizSubmitResponse(BaseModel):
    score: float
    correct_count: int
    total_questions: int
    plan_status: str


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
