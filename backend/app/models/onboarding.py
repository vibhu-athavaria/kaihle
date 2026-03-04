"""Onboarding-related SQLAlchemy models.

Covers: student_learning_profiles
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class StudentLearningProfile(Base, UUIDMixin, TimestampMixin):
    """Normalised learning profile collected during student onboarding.

    Replaces learning_profile JSONB blob on student_profiles (v2.0).
    completed_at IS NOT NULL = profile is usable by AI features.
    completed_at IS NULL = student started questionnaire but did not finish.
    """

    __tablename__ = "student_learning_profiles"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    modality_scores: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    # Expected shape: {"visual": 0.8, "auditory": 0.3,
    #                  "reading_writing": 0.6, "kinesthetic": 0.5}

    work_style: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    # Expected shape: {"prefers_solo": True, "short_sessions": False,
    #                  "task_based": True, "group_learning": False,
    #                  "concept_first": False}

    interests: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    # e.g. ["football", "music", "gaming"]
    # Stored lowercase. Top 2 injected into quiz generation prompts.

    questionnaire_version: Mapped[str] = mapped_column(
        String(10), nullable=False, default="v1"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # NULL means questionnaire not yet submitted. Non-null means complete.
