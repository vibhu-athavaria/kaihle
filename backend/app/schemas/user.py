from pydantic import BaseModel, EmailStr, validator, Field
from typing import Dict, Optional, List, Union
from datetime import datetime
from uuid import UUID
from app.models.user import UserRole
from app.schemas.grade import GradeBase
from app.schemas.subject import SubjectResponse

AnswerValue = Union[str, int, List[str]]

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
    student_profile: Optional["StudentProfileBase"] = None

    class Config:
        from_attributes = True


# --------------------------
# STUDENT PROFILE SCHEMAS
# --------------------------
class StudentProfileBase(BaseModel):
    # User fields
    id: UUID
    user_id: UUID
    parent_id: UUID
    age: int
    curriculum_id: Optional[UUID] = None
    registration_completed_at: Optional[datetime] = None
    grade: Optional[GradeBase] = None
    subjects: Optional[List[SubjectResponse]] = None

class StudentProfileCreate(BaseModel):
    full_name: str
    age: int
    grade_id: str
    username: str
    password: str

class StudentProfileUpdate(StudentProfileBase):
    id: UUID

class StudentProfileResponse(StudentProfileBase):
    # has_active_subscription: bool
    # active_subscription_id: Optional[UUID] = None
    user: UserBase

    class Config:
        from_attributes = True

# --------------------------
# STUDENT LEARNING PROFILE SCHEMAS
# --------------------------
class LearningProfileIntakePayload(BaseModel):
    answers: Dict[str, AnswerValue] = Field(
        ...,
        description="Question ID → Answer value"
    )

    @validator("answers")
    def validate_not_empty(cls, v):
        if not v:
            raise ValueError("Intake answers cannot be empty")
        return v


class LearningStyle(BaseModel):
    scaffolding_level: str
    example_dependency: bool
    exploration_tolerance: str

class AttentionProfile(BaseModel):
    focus_duration_minutes: int
    preferred_chunk_size_minutes: int

class AccessibilityFlags(BaseModel):
    reading_load_sensitive: bool
    auditory_memory_support: bool
    visual_simplicity_required: bool
    attention_regulation_support: bool

class LearningProfile(BaseModel):
    learning_style: LearningStyle
    interest_signals: list[str]
    attention_profile: AttentionProfile
    accessibility_flags: AccessibilityFlags
    expression_preferences: list[str]

class StudentLearningProfileUpdate(StudentProfileBase):
    learning_profile: LearningProfile


class AssessmentSubjectStatus(BaseModel):
    assessment_id: UUID
    status: str

    class Config:
        from_attributes = True

class StudentDetailResponse(StudentProfileBase):
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
