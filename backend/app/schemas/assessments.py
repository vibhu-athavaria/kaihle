"""Assessment schemas. Note: correct_answer is NEVER in student-facing responses."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QuestionOption(BaseModel):
    key: str  # e.g. "a", "b", "c", "d"
    text: str


class AssessmentQuestion(BaseModel):
    """Student-facing question — no correct_answer field by design."""

    question_id: UUID
    question_text: str
    question_type: str  # "MCQ" | "TRUE_FALSE" | "SHORT_ANSWER"
    options: list[QuestionOption]
    difficulty_level: int = 0
    subtopic_name: str = ""


class AssessmentQuestionWithAnswer(AssessmentQuestion):
    """Teacher/admin-facing question — includes correct_answer for review."""

    correct_answer_key: str
    explanation: str | None


class AssessmentResponse(BaseModel):
    id: UUID
    class_id: UUID
    title: str
    assessment_type: str  # "DIAGNOSTIC" | "PROGRESS_CHECK"
    status: str  # "DRAFT" | "ACTIVE" | "CLOSED"
    topic_ids: list[UUID]
    question_count: int | None
    questions_per_topic: int
    minimum_difficulty: int
    maximum_difficulty: int
    question_types: list[str]
    time_limit_minutes: int
    created_at: datetime
    published_at: datetime | None
    deadline: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AssessmentCreateResponse(AssessmentResponse):
    """Response for assessment creation — includes sampled questions for teacher preview."""

    questions: list[AssessmentQuestionWithAnswer] = []


class AssessmentWithClassResponse(BaseModel):
    """Assessment response with class info for teacher's all-assessments list."""

    id: UUID
    class_id: UUID
    class_name: str
    title: str
    assessment_type: str
    status: str
    topic_ids: list[UUID]
    question_count: int | None
    questions_per_topic: int
    minimum_difficulty: int
    maximum_difficulty: int
    question_types: list[str]
    time_limit_minutes: int
    created_at: datetime
    published_at: datetime | None
    deadline: datetime | None


class AssessmentCreateRequest(BaseModel):
    title: str | None = None
    topic_ids: list[UUID]
    questions_per_topic: int = Field(2, ge=1, le=20)
    assessment_type: str = "PROGRESS_CHECK"
    minimum_difficulty: int = Field(1, ge=1, le=5)
    maximum_difficulty: int = Field(5, ge=1, le=5)
    question_types: list[str] = Field(default_factory=lambda: ["MCQ", "TRUE_FALSE"])
    time_limit_minutes: int | None = Field(None, ge=1, le=300)
    deadline: datetime | None = None


class DesignTier1DiagnosticRequest(BaseModel):
    """Request body for teacher-designed Tier 1 diagnostic.

    Topics may come from the class's current grade or the previous grade (grade.level - 1).
    Questions are sampled 2 per difficulty level per topic (DIAGNOSTIC_QUESTIONS_PER_DIFFICULTY).
    """

    topic_ids: list[UUID] = Field(..., min_length=1, description="Curriculum topic IDs to include")
    questions_per_topic: int = Field(2, ge=1, le=20)
    time_limit_minutes: int | None = Field(None, ge=1, le=300)
    question_types: list[str] = Field(default_factory=lambda: ["MCQ", "TRUE_FALSE"])
    minimum_difficulty: int = Field(1, ge=1, le=5)
    maximum_difficulty: int = Field(5, ge=1, le=5)
    deadline: datetime | None = None


class TopicAvailability(BaseModel):
    curriculum_topic_id: UUID
    topic_name: str
    grade_level: int
    available_questions: int
    per_difficulty_available: dict[int, int]
    fulfillable: bool


class TopicAvailabilityRequest(BaseModel):
    topic_ids: list[UUID] = Field(..., min_length=1)
    questions_per_topic: int = Field(2, ge=1)
    minimum_difficulty: int = Field(1, ge=1, le=5)
    maximum_difficulty: int = Field(5, ge=1, le=5)
    question_types: list[str] = Field(default_factory=lambda: ["MCQ", "TRUE_FALSE"])


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
