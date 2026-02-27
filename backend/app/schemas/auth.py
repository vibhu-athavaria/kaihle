from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID


class UserCreate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    full_name: Optional[str] = None
    role: str


class UserLogin(BaseModel):
    identifier: str
    password: str
    role: str  # 'parent' or 'student'


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    school_id: Optional[UUID] = None


class TokenData(BaseModel):
    username: Optional[str] = None


class UserResponse(BaseModel):
    id: UUID
    email: Optional[str] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    is_active: bool

    class Config:
        from_attributes = True


# School Admin Registration Schemas
class SchoolAdminRegisterRequest(BaseModel):
    admin_name: str
    admin_email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    school_name: str
    country: str
    curriculum_id: UUID


class SchoolAdminRegisterResponse(BaseModel):
    user_id: UUID
    school_id: UUID
    status: str  # "pending_approval"


# Student Registration Schemas
class StudentRegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    school_code: str = Field(..., min_length=8, max_length=8, description="School code must be exactly 8 characters")


class StudentRegisterResponse(BaseModel):
    user_id: UUID
    school_name: str
    status: str  # "pending_approval"


class CurrentUserResponse(BaseModel):
    id: UUID
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: str
    role: str
    school_id: Optional[UUID] = None
    is_active: bool

    class Config:
        from_attributes = True
