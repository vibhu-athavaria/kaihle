"""Lesson plan SQLAlchemy model."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class LessonPlanStatus:
    GENERATING = "GENERATING"
    GENERATED = "GENERATED"
    EDITED = "EDITED"
    USED = "USED"
    ARCHIVED = "ARCHIVED"


class LessonPlan(Base, UUIDMixin):
    """On-demand AI-generated lesson plan per class."""

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
    focus_subtopic_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    gap_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # {"subtopic_id": {"name": "...", "class_avg": 0.32, "student_count": 8}}
    generated_plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # {starter_10min, group_a_activity, group_b_activity, group_c_activity,
    #  plenary_10min, homework, teacher_notes}
    teacher_edits: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        Enum(
            LessonPlanStatus.GENERATING,
            LessonPlanStatus.GENERATED,
            LessonPlanStatus.EDITED,
            LessonPlanStatus.USED,
            LessonPlanStatus.ARCHIVED,
            name="lesson_plan_status",
            native_enum=False,
        ),
        nullable=False,
        default=LessonPlanStatus.GENERATING,
    )
    generated_at: Mapped[datetime]
    updated_at: Mapped[datetime | None]
