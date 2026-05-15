"""Schemas for mini-course endpoints.

Covers: SubtopicCourseResponse, MarkProgressRequest and nested types.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class SubtopicExplanationItem(BaseModel):
    content_id: UUID
    explanation_text: str
    interest_matched: bool  # True = interest-specific variant, False = generic fallback


class SubtopicVideoItem(BaseModel):
    video_url: str
    thumbnail_url: str | None = None
    duration_seconds: int | None = None


class CheckQuestion(BaseModel):
    question_id: UUID
    question_text: str
    options: list[str]
    # correct_answer is NOT included — evaluated server-side


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
