"""Lesson plan SQLAlchemy model.

Covers: lesson_plans
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class LessonPlanStatus:
    """Lesson plan status constants."""

    GENERATED = "GENERATED"
    EDITED = "EDITED"
    USED = "USED"
    ARCHIVED = "ARCHIVED"


class LessonPlan(Base, UUIDMixin):
    """Weekly AI-generated lesson plan per class."""

    __tablename__ = "lesson_plans"

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    week_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Originally "week start date" for weekly auto-gen. Now the generation date
    # (informational only). Nullable because on-demand plans may not map to a week.
    focus_subtopic_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    # Top 2 subtopic_ids with lowest class-average mastery this week
    gap_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # Snapshot at generation time:
    # {"subtopic_id": {"name": "...", "class_avg": 0.32, "group_a_count": 8, ...}}
    generated_plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # Full lesson plan structure
    teacher_edits: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Teacher's modifications. UI merges generated_plan + teacher_edits for display.
    status: Mapped[str] = mapped_column(
        Enum(
            LessonPlanStatus.GENERATED,
            LessonPlanStatus.EDITED,
            LessonPlanStatus.USED,
            LessonPlanStatus.ARCHIVED,
            name="lesson_plan_status",
            native_enum=False,
        ),
        nullable=False,
        default=LessonPlanStatus.GENERATED,
    )
    generated_at: Mapped[datetime]
    updated_at: Mapped[datetime | None]

    # No unique constraint — on-demand generation; dedup handled at service layer.
