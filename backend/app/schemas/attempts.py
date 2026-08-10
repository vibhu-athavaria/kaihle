"""Student attempt schemas — the assessment-taking flow."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.assessments import AssessmentQuestion


class StudentResponseItem(BaseModel):
    """One saved response for a question — used to hydrate state on resume."""

    question_id: UUID
    selected_key: str
    is_correct: bool | None = None  # None if not yet scored


class AttemptResponse(BaseModel):
    id: UUID
    assessment_id: UUID
    student_id: UUID
    title: str  # Assessment title for display in the UI
    status: str  # "NOT_STARTED" | "IN_PROGRESS" | "SUBMITTED"
    started_at: datetime | None
    submitted_at: datetime | None
    score: float | None  # None until submitted and scored
    questions: list[AssessmentQuestion]  # full pool for adaptive difficulty
    num_questions: int  # configured question count to ask
    responses: list[StudentResponseItem]  # previously saved answers for resuming
    time_limit_minutes: int  # 0 = untimed


class NextQuestionResponse(BaseModel):
    """One adaptively-selected question, or completion when the pool is done."""

    question: AssessmentQuestion | None  # None when the attempt is complete
    answered_count: int  # questions already answered in this attempt
    question_count: int  # total the student will be asked
    complete: bool  # True when no further question will be served


class AnswerSubmitResponse(BaseModel):
    """Scoring outcome for a single answer — drives adaptive client flow."""

    scored: bool  # False when scoring is deferred (LLM-scored short answer)
    is_correct: bool
    next_question_available: bool


class AnswerSubmitRequest(BaseModel):
    question_id: UUID
    selected_key: str  # the option key the student chose
    time_taken_ms: int | None = None  # milliseconds spent on this question; None = not tracked


class AttemptSubmitRequest(BaseModel):
    """Submit all answers at once — used when student clicks final Submit."""

    answers: list[AnswerSubmitRequest]
    timed_out: bool = False  # True when the client timer expired; backend marks unanswered questions wrong


class AttemptReviewItem(BaseModel):
    """Per-question result for the student review screen shown after submission."""

    position: int  # 1-based order in this attempt
    question_id: UUID
    question_text: str
    subtopic_name: str
    topic_name: str
    difficulty_level: int  # 1–5
    options: list[dict[str, str]]  # [{"key": "A", "text": "..."}]
    selected_key: str | None  # None if student never answered (timed out)
    correct_answer: str  # the key that is correct
    is_correct: bool


class AttemptReviewResponse(BaseModel):
    """Full per-question breakdown returned to the student after submission."""

    attempt_id: UUID
    assessment_id: UUID
    title: str
    score: float  # 0.0–1.0
    correct_count: int
    total_questions: int
    time_limit_minutes: int
    timed_out: bool
    questions: list[AttemptReviewItem]


class AttemptResultResponse(BaseModel):
    attempt_id: UUID
    score: float  # 0.0–1.0 e.g. 0.75 = 75%
    total_questions: int
    correct_count: int
    time_taken_seconds: int | None
    submitted_at: datetime


class QuestionDetailItem(BaseModel):
    """Per-question result for teacher review — includes subtopic and difficulty context."""

    question_id: UUID
    question_text: str
    subtopic_name: str
    topic_name: str
    difficulty_level: int  # 1–5
    selected_key: str | None  # None if student skipped
    correct_answer: str  # the key (A/B/C/D) that is correct
    is_correct: bool
    position: int  # 1-based order in this attempt


class AttemptDetailResponse(BaseModel):
    """Full per-question breakdown for the teacher detail view.

    Distinct from AttemptResultResponse (which is the lightweight aggregate
    returned to the student after submit). This schema is for teacher review only.
    """

    attempt_id: UUID
    assessment_id: UUID
    assessment_title: str
    assessment_type: str
    student_id: UUID
    student_name: str
    score: float | None
    submitted_at: datetime | None
    status: str
    questions: list[QuestionDetailItem]


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
