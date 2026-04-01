"""Pydantic schemas for school management."""

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SchoolCreate(BaseModel):
    """Schema for creating a new school."""

    name: str
    slug: str  # URL-safe identifier e.g. "bali-green-school"
    country: str | None = None
    timezone: str | None = "UTC"
    # Admin user fields - creates a SCHOOL_ADMIN user with the school
    admin_email: EmailStr
    admin_first_name: str
    admin_last_name: str
    admin_password: str | None = Field(default=None, min_length=8)
    # NULL = magic-link only; if provided, must be >= 8 chars


class SchoolUpdate(BaseModel):
    """Schema for updating a school."""

    name: str | None = None
    country: str | None = None
    timezone: str | None = None
    is_active: bool | None = None


class SchoolResponse(BaseModel):
    """Schema for school response."""

    id: uuid.UUID
    name: str
    slug: str
    country: str | None
    timezone: str
    is_active: bool
    joined: str
    # Admin user info - available when fetching single school
    admin_user_id: uuid.UUID | None = None
    admin_email: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SchoolListResponse(BaseModel):
    """Schema for paginated school list response."""

    schools: list[SchoolResponse]
    total: int
    page: int
    page_size: int
