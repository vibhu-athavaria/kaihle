"""ClassTopic SQLAlchemy model.

Covers: class_topics — teacher-configured topic list for a class, with ordering
and covered/not-covered state. Replaces the implicit "all curriculum topics for
the class grade/subject/curriculum" assumption.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ClassTopic(Base):
    """One topic included in a class, with teacher-defined order and covered state."""

    __tablename__ = "class_topics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="RESTRICT"),
        nullable=False,
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    curriculum_topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_topics.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_covered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("class_id", "curriculum_topic_id", name="uq_class_topic"),)
