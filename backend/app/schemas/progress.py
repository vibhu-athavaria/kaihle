from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class ProgressBase(BaseModel):
    points_earned: int = 0
    streak_days: int = 0
    lessons_completed: int = 0

class ProgressCreate(ProgressBase):
    student_id: UUID
    week_start: datetime

class ProgressUpdate(BaseModel):
    points_earned: Optional[int] = None
    streak_days: Optional[int] = None
    lessons_completed: Optional[int] = None

class Progress(ProgressBase):
    id: UUID
    student_id: UUID
    week_start: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ProgressSummary(BaseModel):
    total_points: int
    current_streak: int
    total_lessons_completed: int
    weekly_progress: List[Progress]
