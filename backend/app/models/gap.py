"""Gap state SQLAlchemy model.

Covers: gap_states
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
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
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_assessed_at: Mapped[datetime | None]

    __table_args__ = (
        UniqueConstraint("student_id", "subtopic_id", "class_id", name="gap_states_unique"),
        CheckConstraint("mastery_score BETWEEN 0.0 AND 1.0", name="chk_gs_mastery"),
        CheckConstraint("confidence BETWEEN 0.0 AND 1.0", name="chk_gs_confidence"),
        CheckConstraint("total_correct <= total_attempted", name="chk_gs_counts"),
    )


class MasteryPrior(Base):
    """The hierarchical Bayesian prior a subtopic's mastery estimate shrinks toward.

    Exactly one row per ACTIVE subtopic, always — including subtopics with zero response
    data (source_level='GLOBAL' in that case). Written offline by
    scripts/calibrate_mastery_prior.py, either invoked directly or via the weekly
    recalibrate_mastery_priors Celery task; read by GapService at attempt-submission time.

    This separation exists because fitting the hierarchical prior means scanning every
    response for a subtopic's topic and subject, which is too expensive to redo on every
    attempt submission (.claude/rules/07-performance.md prohibits unbounded scans in hot
    paths). Precompute, store, read cheaply — the same pattern
    learning_objectives.embedding already uses.

    No school_id: curriculum-derived, like learning_objectives, and applies platform-wide.
    """

    __tablename__ = "mastery_priors"

    subtopic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subtopics.id", ondelete="CASCADE"),
        primary_key=True,
    )
    alpha: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    beta: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    # Which level of the backoff chain this row's alpha/beta actually came from —
    # SUBTOPIC | TOPIC | SUBJECT | GLOBAL — shown for transparency/debugging, not read by
    # gap_service itself (which only needs alpha/beta).
    source_level: Mapped[str] = mapped_column(String(10), nullable=False)
    # Observations backing the level actually used, NOT this subtopic's own count — a
    # subtopic resolved to GLOBAL reports the global observation count here, which is the
    # evidence actually behind its prior.
    source_n: Mapped[int] = mapped_column(Integer, nullable=False)
    fitted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("alpha > 0", name="chk_mastery_prior_alpha_positive"),
        CheckConstraint("beta > 0", name="chk_mastery_prior_beta_positive"),
        CheckConstraint(
            "source_level IN ('SUBTOPIC', 'TOPIC', 'SUBJECT', 'GLOBAL')",
            name="chk_mastery_prior_source_level",
        ),
        CheckConstraint("source_n >= 0", name="chk_mastery_prior_source_n_non_negative"),
    )
