"""Gap state SQLAlchemy model.

Covers: gap_states
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class GapState(Base, UUIDMixin, TimestampMixin):
    """Normalised mastery tracking. Replaces v1 student_knowledge_profiles JSONB blobs.

    Updated by Celery task: calculate_gap_states(attempt_id) after each attempt.
    Also updated when student completes a study_plan_quiz.
    """

    __tablename__ = "gap_states"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    subtopic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subtopics.id", ondelete="CASCADE"),
        nullable=False,
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    # class_id: A student in Cambridge Math AND IB Math has separate gap_states per class.
    mastery_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    # 0.0–1.0 rolling average.
    # < 0.4: Needs Work (Red) | 0.4–0.7: Developing (Amber) | > 0.7: Strong (Green)
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.0)
    # 0.0–1.0. Grows with attempt_count. Low confidence = insufficient data points.
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_attempted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    needs_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    last_assessed_at: Mapped[datetime | None]

    __table_args__ = (
        CheckConstraint(
            "mastery_score BETWEEN 0.0 AND 1.0", name="chk_gs_mastery"
        ),
        CheckConstraint(
            "confidence BETWEEN 0.0 AND 1.0", name="chk_gs_confidence"
        ),
        CheckConstraint(
            "total_correct <= total_attempted", name="chk_gs_counts"
        ),
    )
