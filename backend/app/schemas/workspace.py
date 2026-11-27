"""Schemas for self-serve workspace signup."""

import uuid
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, EmailStr, Field, field_validator


class WorkspaceSignupRequest(BaseModel):
    """Body of POST /auth/signup/workspace.

    `kind` picks the workspace type: `teacher` for an independent teacher, `family` for a
    homeschooling parent. Both owners get role TEACHER (plan decision D1).
    """

    kind: Literal["teacher", "family"]
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    # Optional display name; derived from the owner's name when omitted.
    workspace_name: str | None = Field(default=None, min_length=1, max_length=200)
    country: str = Field(..., min_length=2, max_length=100)
    timezone: str = Field(..., min_length=1, max_length=50)
    # Optional: lesson plans use it for local examples when present.
    city: str | None = Field(default=None, min_length=1, max_length=100)
    curriculum_id: uuid.UUID

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError("timezone must be an IANA name such as Asia/Singapore") from e
        return value


class WorkspaceSignupResponse(BaseModel):
    """Always the same body, whether or not the email was new, so signup cannot enumerate accounts."""

    message: str
