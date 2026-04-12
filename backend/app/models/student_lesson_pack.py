"""Student Lesson Pack model — generated collections of content for individual students."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    UUID,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

if TYPE_CHECKING:
    pass


class PackType(str):
    QUIZ = "quiz"
    VIDEO = "video"
    EXPLANATION = "explanation"
    MIXED = "mixed"


class PackStatus(str):
    GENERATED = "generated"
    SENT = "sent"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"


class StudentLessonPack(Base):
    __tablename__ = "student_lesson_packs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # ARRAY of UUID — references to subtopic_content.id
    content_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID()), nullable=False)
    # Denormalised subtopic IDs for quick lookup
    subtopic_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID()), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    pack_type: Mapped[str] = mapped_column(
        Enum(
            "quiz",
            "video",
            "explanation",
            "mixed",
            name="pack_type_enum",
            create_type=False,
        ),
        nullable=False,
        default="mixed",
    )
    target_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    mastery_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            "generated",
            "sent",
            "in_progress",
            "completed",
            "expired",
            name="pack_status_enum",
            create_type=False,
        ),
        nullable=False,
        default="generated",
        index=True,
    )
    generated_by_teacher_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    def is_expired(self) -> bool:
        """Check if this pack has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(self.expires_at.tzinfo) > self.expires_at

    def is_active(self) -> bool:
        """Check if this pack is in an active (non-terminal) state."""
        return (
            self.status
            in (
                PackStatus.GENERATED,
                PackStatus.SENT,
                PackStatus.IN_PROGRESS,
            )
            and not self.is_archived
        )
