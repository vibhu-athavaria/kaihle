"""Pydantic schemas for school management."""

import uuid

from pydantic import BaseModel, ConfigDict


class SchoolCreate(BaseModel):
    """Schema for creating a new school."""

    name: str
    slug: str  # URL-safe identifier e.g. "bali-green-school"
    country: str | None = None
    timezone: str | None = "UTC"


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

    model_config = ConfigDict(from_attributes=True)


class SchoolListResponse(BaseModel):
    """Schema for paginated school list response."""

    schools: list[SchoolResponse]
    total: int
    page: int
    page_size: int
