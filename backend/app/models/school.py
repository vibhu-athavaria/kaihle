"""School-related SQLAlchemy models.

Covers: schools, school_curricula, classes, class_enrollments
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.curriculum import Grade, Subject
from app.models.user import User


class ClassEnrollment(Base):
    """Many-to-many: students enrolled in classes."""

    __tablename__ = "class_enrollments"

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    enrolled_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    onboarding_diagnostic_status: Mapped[str] = mapped_column(
        Enum("PENDING", "IN_PROGRESS", "COMPLETED", name="onboarding_status", native_enum=False),
        nullable=False,
        server_default="PENDING",
    )


class SchoolCurriculum(Base):
    """Which curricula a school offers."""

    __tablename__ = "school_curricula"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        primary_key=True,
    )
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curricula.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    adopted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class Class(Base, UUIDMixin, TimestampMixin):
    """Operational unit. One class = one teacher + one subject + one curriculum + one grade."""

    __tablename__ = "classes"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    grade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("grades.id", ondelete="RESTRICT"),
        nullable=False,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curricula.id", ondelete="RESTRICT"),
        nullable=False,
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships for eager loading (avoids N+1 queries when listing classes)
    subject: Mapped["Subject"] = relationship("Subject", lazy="joined")
    grade: Mapped["Grade"] = relationship("Grade", lazy="joined")
    teacher: Mapped["User"] = relationship("User", lazy="joined")


class School(Base, UUIDMixin, TimestampMixin):
    """One row per tenant. This is the multi-tenancy anchor."""

    __tablename__ = "schools"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    address: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Asia/Singapore")
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(50))
    website: Mapped[str | None] = mapped_column(String(255))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'suspended')",
            name="chk_school_status",
        ),
    )
