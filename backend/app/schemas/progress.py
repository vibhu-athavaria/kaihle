from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ProgressBase(BaseModel):
    points_earned: int = 0
    streak_days: int = 0
    lessons_completed: int = 0

class ProgressCreate(ProgressBase):
    student_id: int
    week_start: datetime

class ProgressUpdate(BaseModel):
    points_earned: Optional[int] = None
    streak_days: Optional[int] = None
    lessons_completed: Optional[int] = None

class Progress(ProgressBase):
    id: int
    student_id: int
    week_start: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class BadgeBase(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    points_required: int = 0

class BadgeCreate(BadgeBase):
    pass

class Badge(BadgeBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class StudentBadgeResponse(BaseModel):
    id: int
    badge: Badge
    earned_at: datetime
    
    class Config:
        from_attributes = True

class ProgressSummary(BaseModel):
    total_points: int
    current_streak: int
    total_lessons_completed: int
    badges_earned: List[StudentBadgeResponse]
    weekly_progress: List[Progress]
