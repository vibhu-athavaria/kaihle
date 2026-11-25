"""School-related SQLAlchemy models.

Covers: schools, school_curricula, classes, class_enrollments
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Index, String, func, text
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
        Enum("PENDING", "IN_PROGRESS", "COMPLETED", name="onboarding_status"),
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


class SchoolType(StrEnum):
    """Kind of tenant a `schools` row represents.

    The values are part of the persistent contract (CHECK `chk_school_type`).
    SCHOOL            a real school, administered by a SCHOOL_ADMIN (the default, all legacy rows).
    TEACHER_WORKSPACE a self-serve workspace owned by one independent teacher.
    FAMILY            a self-serve workspace owned by one homeschooling parent.
    A workspace has exactly one operator, its owner, who has role TEACHER.
    """

    SCHOOL = "SCHOOL"
    TEACHER_WORKSPACE = "TEACHER_WORKSPACE"
    FAMILY = "FAMILY"


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
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SchoolType.SCHOOL,
        server_default=SchoolType.SCHOOL.value,
    )
    # NULL means: this row has no owner. That is always true for type SCHOOL, and briefly true
    # for a workspace inside the single transaction that creates the school before its owner
    # user exists. The "workspace must have an owner" rule is enforced in WorkspaceService because
    # a DB CHECK would fail that insert order. use_alter breaks the schools <-> users FK cycle.
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True, name="fk_schools_owner_user_id"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'suspended')",
            name="chk_school_status",
        ),
        CheckConstraint(
            "type IN ('SCHOOL', 'TEACHER_WORKSPACE', 'FAMILY')",
            name="chk_school_type",
        ),
        Index("idx_schools_type", "type"),
        # One user can own at most one workspace.
        Index(
            "uq_schools_owner_user_id",
            "owner_user_id",
            unique=True,
            postgresql_where=text("owner_user_id IS NOT NULL"),
        ),
    )
