"""User-related Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.user import UserRole


class UserInvite(BaseModel):
    """Schema for inviting a new user to a school."""

    email: EmailStr
    role: UserRole  # TEACHER | SCHOOL_ADMIN | PARENT
    first_name: str
    last_name: str
    subjects: list[str] | None = None  # for TEACHER role only
    student_ids: list[uuid.UUID] | None = None  # for PARENT role only


class UserUpdate(BaseModel):
    """Schema for updating user information."""

    first_name: str | None = None
    last_name: str | None = None
    is_active: bool | None = None
    # Password - if provided, hashed and stored as hashed_password.
    # NULL = leave current password unchanged.
    password: str | None = Field(default=None, min_length=8)


class UserResponse(BaseModel):
    """Schema for user response."""

    id: uuid.UUID
    email: str
    role: str  # Using str for response compatibility
    first_name: str
    last_name: str
    is_active: bool
    school_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Schema for paginated user list response."""

    users: list[UserResponse]
    total: int
    page: int
    page_size: int


class StudentListItem(BaseModel):
    """Schema for a single student in the school admin student list."""

    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    is_active: bool
    last_login_at: datetime | None
    # NULL = no enrollments yet (or no gap states recorded)
    worst_mastery: float | None
    class_count: int
    needs_work_class_count: int
    diagnostic_completed: bool


class StudentListResponse(BaseModel):
    """Paginated student list with mastery and diagnostic enrichment."""

    users: list[StudentListItem]
    total: int
    page: int
    page_size: int


class UserSelfUpdate(BaseModel):
    """Only first_name and last_name are user-updatable via /users/me."""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
        return v

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UserSelfUpdate":
        if self.first_name is None and self.last_name is None:
            raise ValueError("At least one of first_name or last_name must be provided")
        return self


class MeResponse(BaseModel):
    """Response schema for /users/me endpoint.

    Never includes hashed_password — Pixel: response body drives the UI.
    """

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    school_id: uuid.UUID | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class UserDirectCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    role: UserRole

    # Student-only fields
    age: int | None = Field(default=None, ge=5, le=25)
    grade_id: uuid.UUID | None = None

    # Teacher-only fields
    class_ids: list[uuid.UUID] | None = None

    # Parent-only fields
    student_ids: list[uuid.UUID] | None = None

    @model_validator(mode="after")
    def validate_role_fields(self) -> "UserDirectCreate":
        if self.role == UserRole.STUDENT:
            if self.grade_id is None:
                raise ValueError("grade_id is required for students")
            if self.age is None:
                raise ValueError("age is required for students")
        if self.role not in (UserRole.STUDENT, UserRole.TEACHER, UserRole.PARENT):
            raise ValueError("role must be STUDENT, TEACHER, or PARENT")
        return self
