"""User-related SQLAlchemy models.

Covers: users, student_profiles, teacher_profiles, parent_student, auth_tokens
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserRole(StrEnum):
    """User role constants."""

    STUDENT = "STUDENT"
    TEACHER = "TEACHER"
    SCHOOL_ADMIN = "SCHOOL_ADMIN"
    PARENT = "PARENT"
    KAIHLE_ADMIN = "KAIHLE_ADMIN"


class OnboardingStatus:
    """Onboarding status constants."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class AuthTokenType:
    """Auth token type constants."""

    MAGIC_LINK = "MAGIC_LINK"
    REFRESH = "REFRESH"


class User(Base, TimestampMixin):
    """All human users across all roles."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum(
            UserRole.STUDENT,
            UserRole.TEACHER,
            UserRole.SCHOOL_ADMIN,
            UserRole.PARENT,
            UserRole.KAIHLE_ADMIN,
            name="user_role",
            native_enum=False,
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StudentProfile(Base, TimestampMixin):
    """Extended profile for student users."""

    __tablename__ = "student_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    grade_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("grades.id", ondelete="SET NULL"),
    )
    age: Mapped[int | None]
    is_learning_profile_complete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    # Note: onboarding_diagnostic_status moved to class_enrollments (v2.1)
    # Tracks diagnostic completion per class enrollment


class TeacherProfile(Base, TimestampMixin):
    """Extended profile for teacher users."""

    __tablename__ = "teacher_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    qualifications: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    experience_years: Mapped[int | None]
    bio: Mapped[str | None] = mapped_column(Text)
    hire_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ParentStudent(Base):
    """Explicit many-to-many link: parent → child students."""

    __tablename__ = "parent_student"

    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "parent_id <> student_id",
            name="chk_ps_not_same",
        ),
    )


class AuthToken(Base):
    """Magic link and refresh token storage."""

    __tablename__ = "auth_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    type: Mapped[str] = mapped_column(
        Enum(
            AuthTokenType.MAGIC_LINK,
            AuthTokenType.REFRESH,
            name="auth_token_type",
            native_enum=False,
        ),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    @property
    def is_used(self) -> bool:
        """Return True if token has been used."""
        return self.used_at is not None
