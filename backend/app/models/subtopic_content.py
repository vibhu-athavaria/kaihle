"""Subtopic content SQLAlchemy model.

Stores content per subtopic across 4 content types: video, explanation, practice, quiz.
One row per (subtopic, content_type) combination — curriculum-layer table (no school_id).

Architecture: Replaces deprecated curriculum_chunks PDF RAG approach.
Resources are KaihleAdmin-approved YouTube videos stored as JSONB.
No pgvector, no embeddings, no semantic search.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class ContentType(str):
    VIDEO = "video"
    EXPLANATION = "explanation"
    PRACTICE = "practice"
    QUIZ = "quiz"


class ReviewStatus(str):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SubtopicContent(Base, UUIDMixin):
    """One row per (subtopic, content_type) — stores video, explanation, practice, or quiz content.

    review_status: 'pending' | 'approved' | 'rejected'
    quiz_questions JSONB entries: { "question_id": str, "question_text": str, "options": [...], "correct_answer": str, "explanation": str }
    applicable_tiers: array of ints e.g. [1, 2] or [1, 2, 3]
    """

    __tablename__ = "subtopic_content"

    subtopic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subtopics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Content type: video | explanation | practice | quiz
    content_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # Video fields (used when content_type == 'video')
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Explanation field (used when content_type == 'explanation')
    explanation_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Practice/quiz fields (used when content_type == 'practice' or 'quiz')
    # Each entry: { "question_id": str, "question_text": str, "options": [...], "correct_answer": str, "explanation": str }
    quiz_questions: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    quiz_questions_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Teacher-provided text explanation (not AI)
    teacher_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    teacher_explanation_author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Interest category for personalization
    interest_category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interest_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Tier levels this content applies to (array, e.g. [1, 2] or [1, 2, 3])
    applicable_tiers: Mapped[list[int]] = mapped_column(
        ARRAY(Integer),
        nullable=False,
        server_default="{1,2,3}",
    )

    # Review / approval workflow
    review_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="pending",
        index=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status flags
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", index=True)

    # Relationships
    interest_category = relationship("InterestCategory", viewonly=True)
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id], viewonly=True)

    __table_args__ = (
        Index("idx_subtopic_content_subtopic", "subtopic_id"),
        Index("idx_subtopic_content_explanation_status", "review_status"),
    )

    def get_approved_videos(self) -> list[dict[str, Any]]:
        """Return video metadata as a list if this is an approved active video content type."""
        if self.content_type != ContentType.VIDEO:
            return []
        if self.review_status != ReviewStatus.APPROVED:
            return []
        if not self.is_active or self.is_archived:
            return []
        return [
            {
                "url": self.video_url,
                "title": None,
                "channel": self.video_provider,
                "duration_seconds": self.video_duration_seconds,
                "thumbnail_url": self.video_thumbnail_url,
            }
        ]

    def get_display_explanation(self) -> str | None:
        """Return teacher explanation if available, otherwise explanation_text."""
        return self.teacher_explanation or self.explanation_text
