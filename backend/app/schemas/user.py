"""User-related Pydantic schemas."""

import uuid

from pydantic import BaseModel, EmailStr


class UserInvite(BaseModel):
    """Schema for inviting a new user to a school."""

    email: EmailStr
    role: str  # TEACHER | SCHOOL_ADMIN | PARENT
    first_name: str
    last_name: str
    subjects: list[str] | None = None  # for TEACHER role only


class UserUpdate(BaseModel):
    """Schema for updating user information."""

    first_name: str | None = None
    last_name: str | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    """Schema for user response."""

    id: uuid.UUID
    email: str
    role: str
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
