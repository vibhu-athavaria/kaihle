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
    # Number of student attempts recorded against this assessment (populated in list endpoint)
    attempt_count: int = 0
    # Populated only when the requesting user is a STUDENT
    attempt_status: str | None = None  # "NOT_STARTED" | "IN_PROGRESS" | "COMPLETED"
    attempt_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class AssessmentCreateResponse(AssessmentResponse):
    """Response for assessment creation — includes sampled questions for teacher preview."""

    questions: list[AssessmentQuestionWithAnswer] = []


class AssessmentWithClassResponse(BaseModel):
    """Assessment response with class info for teacher's all-assessments list."""

    id: UUID
    class_id: UUID
    class_name: str
    grade_name: str
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
    Minimum 3 questions per topic enforced for statistically reliable placement.
    """

    topic_ids: list[UUID] = Field(..., min_length=1, description="Curriculum topic IDs to include")
    questions_per_topic: int = Field(5, ge=3, le=20)
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
    status: Literal["COMPLETED", "IN_PROGRESS", "NOT_STARTED"]


class TopicBreakdownItem(BaseModel):
    """Per-topic aggregated performance for an assessment result summary.

    Aggregated across all students who completed this assessment.
    Sorted weakest-first so the teacher's eye lands on gaps immediately.
    """

    topic_name: str
    correct_count: int
    total_count: int
    avg_score: float  # correct_count / total_count, 0.0–1.0


class AssessmentResultsSummary(BaseModel):
    assessment_id: UUID
    assessment_title: str
    assessment_type: str
    class_id: UUID
    class_name: str
    total_students: int
    submitted_count: int
    attempts: list[StudentAttemptSummary]
    topic_breakdown: list[TopicBreakdownItem] = []


# ── Preview (teacher-facing — correct answers included) ───────────────────────


class AssessmentPreviewQuestion(BaseModel):
    """Teacher-facing question in the assessment preview — includes correct answer."""

    question_id: UUID
    question_text: str
    question_type: str
    options: list[QuestionOption]
    correct_answer_key: str
    explanation: str | None
    difficulty_level: int
    subtopic_id: UUID
    subtopic_name: str
    topic_name: str
    order_index: int
    is_teacher_submitted: bool = False  # True if source='teacher' (pending review)


class AssessmentPreviewResponse(BaseModel):
    """Full assessment preview for the owning teacher."""

    id: UUID
    class_id: UUID
    title: str
    assessment_type: str
    status: str
    question_count: int | None
    questions_per_topic: int
    minimum_difficulty: int
    maximum_difficulty: int
    time_limit_minutes: int
    deadline: datetime | None
    instructions: str | None
    questions: list[AssessmentPreviewQuestion]
    attempt_count: int  # frontend shows warning banner if > 0


# ── Assessment detail edit ────────────────────────────────────────────────────


class AssessmentUpdateRequest(BaseModel):
    """Partial update for assessment details. Omitted fields are unchanged.

    Safe fields (always editable): title, instructions, deadline.
    Risky fields (editable with frontend warning when attempt_count > 0):
        question_count, time_limit_minutes, questions_per_topic,
        minimum_difficulty, maximum_difficulty.
    CLOSED assessments: only title and instructions accepted.
    """

    title: str | None = None
    instructions: str | None = None
    deadline: datetime | None = Field(default=None)
    question_count: int | None = Field(default=None, ge=1)
    time_limit_minutes: int | None = Field(default=None, ge=0)
    questions_per_topic: int | None = Field(default=None, ge=1)
    minimum_difficulty: int | None = Field(default=None, ge=1, le=5)
    maximum_difficulty: int | None = Field(default=None, ge=1, le=5)


class AssessmentUpdateResponse(BaseModel):
    """Response to PATCH /assessments/{id} — includes has_attempts warning flag."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    class_id: UUID
    title: str
    assessment_type: str
    status: str
    question_count: int | None
    questions_per_topic: int
    minimum_difficulty: int
    maximum_difficulty: int
    question_types: list[str]
    time_limit_minutes: int
    instructions: str | None
    deadline: datetime | None
    published_at: datetime | None
    created_at: datetime
    has_attempts: bool  # True if any attempt exists — frontend shows risky-field warning


# ── Question pool management ──────────────────────────────────────────────────


class AddQuestionRequest(BaseModel):
    """Request to add a teacher-created question to an assessment pool."""

    subtopic_id: UUID
    question_text: str
    question_type: str = "MCQ"
    options: list[dict[str, str]] | None = None  # [{"key": "A", "text": "..."}]
    correct_answer: str
    difficulty_level: float = Field(default=3.0, ge=1.0, le=5.0)
    explanation: str | None = None


class AddQuestionResponse(BaseModel):
    """Response after adding a teacher-created question."""

    question_id: UUID
    review_item_id: UUID
    message: str = "Question added to pool and submitted for KaihleAdmin review."


class RemoveQuestionResponse(BaseModel):
    """Response after removing a question from the pool."""

    removed: bool = True
    has_responses: bool  # True if students have already answered this question


class ReplacementCandidate(BaseModel):
    """A question from the bank that can replace one in the assessment pool."""

    question_id: UUID
    question_text: str
    question_type: str
    options: list[QuestionOption]
    correct_answer_key: str
    difficulty_level: int
    subtopic_name: str
    topic_name: str


class ReplaceQuestionRequest(BaseModel):
    replacement_question_id: UUID


class ReplaceQuestionResponse(BaseModel):
    """Response after replacing a question in the pool."""

    replaced: bool = True
    has_responses_for_old: bool  # True if students have answered the replaced question


class SuggestEditRequest(BaseModel):
    """Teacher's proposed edit to an existing question in their assessment pool."""

    suggested_question_text: str | None = None
    suggested_options: list[dict[str, str]] | None = None
    suggested_correct_answer: str | None = None
    suggested_explanation: str | None = None
    suggested_difficulty_level: float | None = Field(default=None, ge=1.0, le=5.0)
    reason: str  # required — teacher must explain why the edit is needed


class SuggestEditResponse(BaseModel):
    """Response after submitting an edit suggestion."""

    review_item_id: UUID
    message: str = "Edit suggestion submitted for KaihleAdmin review."
