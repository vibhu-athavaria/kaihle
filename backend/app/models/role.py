# backend/app/models/role.py
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base
from app.crud.mixin import SerializerMixin


class Role(Base, SerializerMixin):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    permissions = Column(JSONB, nullable=True)  # e.g., {"can_manage_users": true, "can_view_reports": true}
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships - can be added later if needed for user-role assignments