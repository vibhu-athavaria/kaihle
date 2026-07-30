"""Authentication Pydantic schemas."""

import uuid
from typing import Any

from pydantic import BaseModel, EmailStr, Field, model_validator


class RegisterRequest(BaseModel):
    email: EmailStr | None = None
    username: str | None = Field(default=None, min_length=3, max_length=100)
    password: str
    role: str
    school_id: uuid.UUID | None = None
    first_name: str
    last_name: str

    @model_validator(mode="after")
    def validate_email_or_username(self) -> "RegisterRequest":
        if not self.email and not self.username:
            raise ValueError("Either email or username must be provided")
        return self


class RegisterResponse(BaseModel):
    user_id: uuid.UUID
    email: str | None = None
    username: str | None = None
    role: str


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)  # Accepts email or username
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    must_change_password: bool = False
    user: dict[str, Any]


class TokenResponse(BaseModel):
    access_token: str


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkVerifyResponse(BaseModel):
    """Response from magic link verification — scoped token only."""

    setup_token: str
    token_type: str = "bearer"
    requires_password_setup: bool = True


class SetPasswordRequest(BaseModel):
    """Request body for POST /api/v1/auth/set-password."""

    password: str = Field(
        ...,
        min_length=8,
        description="New password — minimum 8 characters",
    )
    confirm_password: str = Field(..., description="Must match password")

    @model_validator(mode="after")
    def passwords_match(self) -> "SetPasswordRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(..., min_length=8)
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class ChangePasswordRequest(BaseModel):
    """Request body for POST /api/v1/auth/change-password."""

    current_password: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self

    @model_validator(mode="after")
    def new_differs_from_current(self) -> "ChangePasswordRequest":
        if self.current_password == self.new_password:
            raise ValueError("New password must differ from current password")
        return self
