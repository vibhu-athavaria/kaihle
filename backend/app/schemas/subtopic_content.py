"""Pydantic schemas for subtopic_content and student_lesson_packs."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# --- Enums ---


class ContentType(StrEnum):
    VIDEO = "video"
    EXPLANATION = "explanation"
    PRACTICE = "practice"
    QUIZ = "quiz"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PackType(StrEnum):
    QUIZ = "quiz"
    VIDEO = "video"
    EXPLANATION = "explanation"
    MIXED = "mixed"


class PackStatus(StrEnum):
    GENERATED = "generated"
    SENT = "sent"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"


# --- SubtopicContent schemas ---


class SubtopicContentBase(BaseModel):
    subtopic_id: uuid.UUID
    content_type: ContentType
    # video fields
    video_url: str | None = None
    video_provider: str | None = None
    video_duration_seconds: int | None = None
    video_thumbnail_url: str | None = None
    # explanation fields
    explanation_text: str | None = None
    # quiz fields
    quiz_questions: list[dict[str, Any]] | None = None
    quiz_questions_count: int | None = None
    # teacher explanation
    teacher_explanation: str | None = None
    teacher_explanation_author_id: uuid.UUID | None = None
    # interest category
    interest_category_id: uuid.UUID | None = None
    # applicable tiers
    applicable_tiers: list[int] = Field(default=[1, 2, 3])
    # review
    review_status: ReviewStatus = ReviewStatus.PENDING
    # status
    is_active: bool = True
    is_stale: bool = False


class SubtopicContentCreate(SubtopicContentBase):
    """Used when creating content (admin/teacher uploads)."""

    id: uuid.UUID | None = None


class SubtopicContentUpdate(BaseModel):
    """Used when updating content fields."""

    video_url: str | None = None
    video_provider: str | None = None
    video_duration_seconds: int | None = None
    video_thumbnail_url: str | None = None
    explanation_text: str | None = None
    quiz_questions: list[dict[str, Any]] | None = None
    quiz_questions_count: int | None = None
    teacher_explanation: str | None = None
    teacher_explanation_author_id: uuid.UUID | None = None
    interest_category_id: uuid.UUID | None = None
    applicable_tiers: list[int] | None = None
    review_status: ReviewStatus | None = None
    is_active: bool | None = None
    is_stale: bool | None = None


class SubtopicContentReviewDecision(BaseModel):
    """Used by reviewer (KAIHLE_ADMIN) to approve/reject content."""

    review_status: ReviewStatus
    rejection_reason: str | None = None


class SubtopicContentResponse(SubtopicContentBase):
    """Full response schema including timestamps and review info."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reviewed_at: datetime | None = None
    reviewed_by_id: uuid.UUID | None = None
    rejection_reason: str | None = None
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime


class SubtopicContentSummary(SubtopicContentBase):
    """Lightweight summary for lists."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    is_stale: bool
    review_status: ReviewStatus
    created_at: datetime


# --- Video review schemas (M3-0-T2a) ---


class VideoEntry(BaseModel):
    """A single video entry from the videos JSONB array."""

    url: str
    title: str
    channel: str
    view_count: int | None = None
    status: str = "pending"  # 'pending' | 'approved' | 'rejected' | 'stale'
    last_checked_at: str | None = None


class SubtopicContentReviewResponse(BaseModel):
    """Full subtopic content detail for video review."""

    subtopic_id: uuid.UUID
    subtopic_name: str
    subject_code: str
    grade_level: int
    curriculum_code: str
    learning_objective: str
    videos: list[VideoEntry]
    pending_count: int
    approved_count: int
    explanation_review_status: str


class ReviewQueueItem(BaseModel):
    """One subtopic in the review queue list."""

    subtopic_id: uuid.UUID
    subtopic_name: str
    subject_code: str
    grade_level: int
    pending_video_count: int
    approved_video_count: int


class ReviewQueueResponse(BaseModel):
    """Paginated review queue response."""

    items: list[ReviewQueueItem]
    total: int
    pending_total: int  # total videos awaiting review across all subtopics


class VideoStatusUpdateRequest(BaseModel):
    """Request to update a video's status."""

    status: str = Field(..., pattern="^(approved|rejected)$")


class ManualVideoAddRequest(BaseModel):
    """Request to add a manual video entry."""

    url: str
    title: str
    channel: str = "manual"


# --- StudentLessonPack schemas ---


class StudentLessonPackBase(BaseModel):
    student_id: uuid.UUID
    school_id: uuid.UUID
    content_ids: list[uuid.UUID]
    subtopic_ids: list[uuid.UUID]
    title: str
    pack_type: PackType = PackType.MIXED
    target_tier: int
    mastery_score: float | None = None
    status: PackStatus = PackStatus.GENERATED
    generated_by_teacher_id: uuid.UUID | None = None
    expires_at: datetime | None = None


class StudentLessonPackCreate(StudentLessonPackBase):
    id: uuid.UUID | None = None


class StudentLessonPackUpdate(BaseModel):
    """Update pack status / timestamps."""

    status: PackStatus | None = None
    mastery_score: float | None = None
    expires_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    is_archived: bool | None = None


class StudentLessonPackResponse(StudentLessonPackBase):
    """Full response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sent_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime


class StudentLessonPackSummary(BaseModel):
    """Lightweight summary for lists."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: uuid.UUID
    title: str
    pack_type: PackType
    target_tier: int
    status: PackStatus
    mastery_score: float | None
    is_archived: bool
    created_at: datetime


# --- Content with pack info (for teacher view) ---


class ContentWithPackSummary(BaseModel):
    """SubtopicContent joined with its containing pack summary."""

    content: SubtopicContentSummary
    pack: StudentLessonPackSummary


# --- InterestCategory schemas ---


class InterestCategoryResponse(BaseModel):
    """Schema for interest category lookup."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None


class InterestCategoryUpdate(BaseModel):
    """Schema for updating an interest category."""

    name: str | None = None
    description: str | None = None
