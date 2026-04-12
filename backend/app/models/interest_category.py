"""InterestCategory model — lookup table for content personalisation tags."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InterestCategory(Base):
    __tablename__ = "interest_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
