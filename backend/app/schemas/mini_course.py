"""Schemas for mini-course endpoints.

Covers: SubtopicCourseResponse, MarkProgressRequest, chat, transfer question,
        and AI grading nested types.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class LearningProfileItem(BaseModel):
    dominant_modality: str | None  # e.g. "Visual learner"
    interest: str | None  # e.g. "football"
    work_style_label: str | None  # e.g. "Task-based"


class SubtopicExplanationItem(BaseModel):
    content_id: UUID
    explanation_text: str
    interest_matched: bool  # True = interest-specific variant, False = generic fallback


class SubtopicVideoItem(BaseModel):
    video_url: str
    thumbnail_url: str | None = None
    duration_seconds: int | None = None


class CheckQuestionOption(BaseModel):
    key: str
    text: str


class CheckQuestion(BaseModel):
    question_id: UUID
    question_text: str
    options: list[CheckQuestionOption]
    correct_answer: str


class CourseProgressItem(BaseModel):
    explanation_accessed: bool
    video_accessed: bool
    check_questions_score: float | None
    last_visited_at: datetime | None


class NextSubtopicItem(BaseModel):
    id: UUID
    name: str


class LatestOpenAnswerItem(BaseModel):
    question_text: str
    student_answer: str
    ai_grade: str | None
    ai_feedback: str | None
    score: float


class SubtopicCourseResponse(BaseModel):
    subtopic_id: UUID
    subtopic_name: str
    topic_name: str
    explanation: SubtopicExplanationItem | None
    content_status: Literal["ready", "unavailable"]
    video: SubtopicVideoItem | None
    check_questions: list[CheckQuestion]
    progress: CourseProgressItem
    next_subtopic: NextSubtopicItem | None = None
    learning_profile: LearningProfileItem | None = None
    latest_open_answer: LatestOpenAnswerItem | None = None


class MarkProgressRequest(BaseModel):
    explanation_accessed: bool = False
    video_accessed: bool = False


class SubtopicProgressItem(BaseModel):
    subtopic_id: UUID
    subtopic_name: str
    topic_name: str
    last_visited_at: datetime
    explanation_accessed: bool
    video_accessed: bool
    check_questions_score: float | None


class StudentCourseProgressResponse(BaseModel):
    student_id: UUID
    progress: list[SubtopicProgressItem]


class QuizAnswerItem(BaseModel):
    question_id: UUID
    selected_key: str


class QuizSubmitRequest(BaseModel):
    answers: list[QuizAnswerItem]


class QuizSubmitResponse(BaseModel):
    score: float
    correct: int
    total: int
    status: Literal["not_started", "in_progress", "completed"]


class FeedbackRequest(BaseModel):
    feedback_type: Literal["thumbs_up", "thumbs_down"]
    comment: str | None = Field(None, max_length=140)


class FeedbackResponse(BaseModel):
    id: UUID
    feedback_type: str
    comment: str | None
    created_at: datetime


# ── Chat history ──────────────────────────────────────────────────────────────


class ChatMessageItem(BaseModel):
    role: Literal["student", "ai"]
    content: str
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageItem]


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


# ── Transfer question + AI grading ───────────────────────────────────────────


class TransferQuestionResponse(BaseModel):
    question_text: str


class GradeAnswerRequest(BaseModel):
    question_text: str = Field(..., min_length=1, max_length=2000)
    student_answer: str = Field(..., min_length=1, max_length=1000)


class GradeAnswerResponse(BaseModel):
    grade: Literal["correct", "partial", "incorrect"]
    feedback: str
    score: float
    updated_course_score: float | None
