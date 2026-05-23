"""SubtopicExplanationSuggestion model.

Teachers submit text suggestions for KaihleAdmin-managed personalised explanations.
KaihleAdmin reviews the diff (original_text vs suggested_text) and accepts/rejects.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class SubtopicExplanationSuggestion(Base, UUIDMixin, TimestampMixin):
    """Teacher suggestion for a personalised explanation row."""

    __tablename__ = "subtopic_explanation_suggestions"

    subtopic_content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subtopic_content.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    suggested_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Snapshot of explanation_text at suggestion time — used for diff display
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            "pending",
            "accepted",
            "rejected",
            "accepted_with_edits",
            name="suggestion_status_enum",
            create_type=False,
        ),
        nullable=False,
        server_default="pending",
        index=True,
    )
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    subtopic_content = relationship("SubtopicContent", viewonly=True)
    suggested_by = relationship("User", foreign_keys=[suggested_by_id], viewonly=True)
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id], viewonly=True)
