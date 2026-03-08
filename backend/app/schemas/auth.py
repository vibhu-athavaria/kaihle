"""Authentication Pydantic schemas."""

import uuid
from typing import Any

from pydantic import BaseModel, EmailStr


# Generic registration (legacy - kept for backward compatibility)
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


# Role-specific registration requests
class SchoolAdminRegisterRequest(BaseModel):
    """Registration request for school administrators."""

    email: EmailStr
    password: str
    school_id: uuid.UUID
    first_name: str
    last_name: str


class TeacherRegisterRequest(BaseModel):
    """Registration request for teachers."""

    email: EmailStr
    password: str
    school_id: uuid.UUID
    first_name: str
    last_name: str


class StudentRegisterRequest(BaseModel):
    """Registration request for students."""

    email: EmailStr
    password: str
    school_id: uuid.UUID
    grade_id: uuid.UUID | None = None
    first_name: str
    last_name: str


class ParentRegisterRequest(BaseModel):
    """Registration request for parents."""

    email: EmailStr
    password: str
    first_name: str
    last_name: str


class KaihleAdminRegisterRequest(BaseModel):
    """Registration request for Kaihle administrators."""

    email: EmailStr
    password: str
    first_name: str
    last_name: str


# Login
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
