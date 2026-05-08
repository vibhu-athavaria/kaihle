"""Lesson plan SQLAlchemy model."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class LessonPlanStatus:
    GENERATING = "GENERATING"
    GENERATED = "GENERATED"
    EDITED = "EDITED"
    USED = "USED"
    ARCHIVED = "ARCHIVED"


class LessonPlanFailureCode:
    LLM_AUTH_ERROR = "llm_auth_error"
    LLM_RATE_LIMIT_ERROR = "llm_rate_limit_error"
    LLM_CONNECTION_ERROR = "llm_connection_error"
    LLM_UNEXPECTED_ERROR = "llm_unexpected_error"
    JSON_PARSE_FAILED = "json_parse_failed"
    CLASS_NOT_FOUND = "class_not_found"


_FAILURE_CODE_ENUM = Enum(
    LessonPlanFailureCode.LLM_AUTH_ERROR,
    LessonPlanFailureCode.LLM_RATE_LIMIT_ERROR,
    LessonPlanFailureCode.LLM_CONNECTION_ERROR,
    LessonPlanFailureCode.LLM_UNEXPECTED_ERROR,
    LessonPlanFailureCode.JSON_PARSE_FAILED,
    LessonPlanFailureCode.CLASS_NOT_FOUND,
    name="lesson_plan_failure_code",
)


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
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(_FAILURE_CODE_ENUM, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(nullable=True)
    raw_llm_output: Mapped[str | None] = mapped_column(Text, nullable=True)
