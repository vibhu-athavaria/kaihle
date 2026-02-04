from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID

# -------------------
# TEACHER SCHEMAS
# -------------------
class TeacherBase(BaseModel):
    user_id: UUID
    school_id: UUID
    qualifications: Optional[List[str]] = None
    subjects_taught: Optional[List[Any]] = None  # Can be list of subject_ids or names
    experience_years: Optional[int] = None
    bio: Optional[str] = None
    hire_date: Optional[datetime] = None
    is_active: Optional[bool] = True


class TeacherCreate(TeacherBase):
    pass


class TeacherUpdate(BaseModel):
    school_id: Optional[UUID] = None
    qualifications: Optional[List[str]] = None
    subjects_taught: Optional[List[Any]] = None
    experience_years: Optional[int] = None
    bio: Optional[str] = None
    hire_date: Optional[datetime] = None
    is_active: Optional[bool] = None


class Teacher(TeacherBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    # user: Optional["User"] = None
    # school: Optional["School"] = None