from pydantic import BaseModel, EmailStr, validator
from typing import Dict, Optional, List
from datetime import datetime
from app.models.user import UserRole
from app.schemas.assessment import AssessmentOut

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
    parent_id: Optional[int] = None
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
    id: int
    is_active: bool
    created_at: datetime
    student_profile: Optional["StudentProfileResponse"] = None

    class Config:
        from_attributes = True


# -------------------
# STUDENT PROFILE SCHEMAS
# -------------------
class StudentProfileCreate(BaseModel):
    # User fields
    name: str                              # full name
    username: str                          # required for students
    email: Optional[EmailStr] = None       # optional
    password: str                          # plain text (hash before save)

    # Profile fields
    age: Optional[int] = None
    grade_level: Optional[int] = None
    checkpoints: Optional[Dict[str, str]] = None   # {"math": "A", "science": "B", ...}



class StudentProfileUpdate(BaseModel):
    # User fields
    full_name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None   # if updating, re-hash before save

    # Profile fields
    age: Optional[int] = None
    grade_level: Optional[int] = None
    checkpoints: Optional[Dict[str, str]] = None
    interests: Optional[List[str]] = None
    preferred_format: Optional[str] = None
    preferred_session_length: Optional[int] = None


class StudentProfileResponse(BaseModel):
    id: int
    parent_id: int
    age: Optional[int] = None
    grade_level: Optional[int] = None
    interests: Optional[List[str]] = None
    preferred_format: Optional[str] = None
    preferred_session_length: Optional[int] = None
    registration_completed_at: Optional[datetime] = None
    # has_active_subscription: bool
    # active_subscription_id: Optional[int] = None
    user: UserBase

    class Config:
        from_attributes = True


class LearningProfileUpdate(BaseModel):
    interests: List[str]
    preferred_format: str
    preferred_session_length: int

class AssessmentSubjectStatus(BaseModel):
    assessment_id: int
    status: str

    class Config:
        from_attributes = True

class StudentDetailResponse(BaseModel):
    id: int
    parent_id: int
    age: Optional[int] = None
    grade_level: Optional[int] = None
    interests: Optional[List[str]] = None
    preferred_format: Optional[str] = None
    preferred_session_length: Optional[int] = None
    user: Optional[UserBase] = None
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
