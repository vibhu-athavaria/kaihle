# app/schemas/course.py

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID

# -----------------------------
# Course Schemas
# -----------------------------
class CourseBase(BaseModel):
    title: str
    description: Optional[str] = None
    subject_id: UUID
    grade_id: Optional[UUID] = None
    topic_id: UUID
    subtopic_id: Optional[UUID] = None
    learning_objectives: Optional[Any] = None  # JSONB
    duration_minutes: int = Field(default=15, ge=1)
    difficulty_level: Optional[int] = Field(None, ge=1, le=5)
    prerequisite_topic_ids: Optional[List[UUID]] = None
    generated_by_ai: bool = False
    generation_context: Optional[Any] = None  # JSONB
    is_active: bool = True
    is_published: bool = False


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    subject_id: Optional[UUID] = None
    grade_id: Optional[UUID] = None
    topic_id: Optional[UUID] = None
    subtopic_id: Optional[UUID] = None
    learning_objectives: Optional[Any] = None
    duration_minutes: Optional[int] = Field(None, ge=1)
    difficulty_level: Optional[int] = Field(None, ge=1, le=5)
    prerequisite_topic_ids: Optional[List[UUID]] = None
    generated_by_ai: Optional[bool] = None
    generation_context: Optional[Any] = None
    is_active: Optional[bool] = None
    is_published: Optional[bool] = None


class CourseOut(CourseBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

