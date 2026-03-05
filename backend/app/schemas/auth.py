"""Authentication Pydantic schemas."""

import uuid
from typing import Any

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    role: str
    school_id: uuid.UUID | None = None
    first_name: str
    last_name: str


class RegisterResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    role: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: dict[str, Any]


class TokenResponse(BaseModel):
    access_token: str


class MagicLinkRequest(BaseModel):
    email: EmailStr


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str
