"""Shared Pydantic schemas used across all API domains."""

from typing import Any, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page[T](BaseModel):
    """Standard pagination envelope. Every list endpoint returns this shape.

    Usage:
        response_model=Page[MyItemSchema]
    """

    data: list[T]
    total: int = Field(..., description="Total number of matching records")
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)


class ErrorDetail(BaseModel):
    """Standard error response shape. Registered globally in M6-3-T2.

    All HTTP error responses use this shape — never raw strings.
    error_code is machine-readable for frontend switch statements.
    message is safe to display to end users.
    details holds field-level validation errors when applicable.
    """

    error_code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
