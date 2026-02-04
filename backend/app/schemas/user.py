from pydantic import BaseModel, EmailStr, validator
from typing import Dict, Optional, List
from datetime import datetime
from uuid import UUID
from app.models.user import UserRole
from app.schemas.assessment import AssessmentOut
from app.schemas.grade import Grade

# -------------------
# USER SCHEMAS
# -------------------
class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: str
    role: str


class UserCreate(UserBase):
    password: str
    parent_id: Optional[UUID] = None
    student_profile: Optional["StudentProfileCreate"] = None  # forward reference

    # Role-based validation
    @validator("email", always=True)
    def validate_email(cls, v, values):
        role = values.get("role")
        if role in [UserRole.ADMIN.value, UserRole.PARENT.value] and not v:
            raise ValueError("Email is required for parents and admins")
        return v

    @validator("username", always=True)
    def validate_username(cls, v, values):
        role = values.get("role")
        if role == UserRole.STUDENT.value and not v:
            raise ValueError("Username is required for students")
        return v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None


class User(UserBase):
    id: UUID
    is_active: bool
    created_at: datetime
    student_profile: Optional["StudentProfileResponse"] = None

    class Config:
        from_attributes = True


# -------------------
# STUDENT PROFILE SCHEMAS
# -------------------
class StudentProfileBase(BaseModel):
    # User fields
    full_name: str                              # full name
    username: str                          # required for students
    email: Optional[EmailStr] = None       # optional


    # Profile fields
    age: Optional[int] = None
    grade_id: Optional[UUID] = None

class StudentProfileCreate(StudentProfileBase):
    password: str
    pass

class StudentProfileUpdate(StudentProfileBase):
    id: UUID
    interests: Optional[List[str]] = None
    preferred_format: Optional[str] = None
    preferred_session_length: Optional[int] = None


class StudentProfileResponse(BaseModel):
    id: UUID
    parent_id: UUID
    grade: Optional[Grade] = None
    interests: Optional[List[str]] = None
    preferred_format: Optional[str] = None
    preferred_session_length: Optional[int] = None
    registration_completed_at: Optional[datetime] = None
    # has_active_subscription: bool
    # active_subscription_id: Optional[UUID] = None
    user: UserBase

    class Config:
        from_attributes = True


class LearningProfileUpdate(BaseModel):
    interests: List[str]
    preferred_format: str
    preferred_session_length: int

class AssessmentSubjectStatus(BaseModel):
    assessment_id: UUID
    status: str

    class Config:
        from_attributes = True

class StudentDetailResponse(StudentProfileResponse):
    assessments: Dict[str, AssessmentSubjectStatus]

    class Config:
        from_attributes = True

# -------------------
# LOGIN + TOKEN
# -------------------
class UserLogin(BaseModel):
    identifier: str  # email or username
    password: str
    role: str

    @validator("identifier")
    def validate_identifier(cls, v, values):
        role = values.get("role")
        if role == UserRole.STUDENT.value and "@" in v:
            raise ValueError("Students must log in with username, not email")
        return v


class Token(BaseModel):
    access_token: str
    token_type: str
