"""Schemas for mini-course endpoints.

Covers: SubtopicCourseResponse, MarkProgressRequest and nested types.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


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


class SubtopicCourseResponse(BaseModel):
    subtopic_id: UUID
    subtopic_name: str
    topic_name: str
    explanation: SubtopicExplanationItem | None
    content_status: Literal["ready", "generating", "unavailable"]
    video: SubtopicVideoItem | None
    check_questions: list[CheckQuestion]
    progress: CourseProgressItem


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


class FeedbackRequest(BaseModel):
    feedback_type: Literal["thumbs_up", "thumbs_down"]
    comment: str | None = Field(None, max_length=140)


class FeedbackResponse(BaseModel):
    id: UUID
    feedback_type: str
    comment: str | None
    created_at: datetime
