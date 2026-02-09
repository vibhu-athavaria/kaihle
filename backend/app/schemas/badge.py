# app/schemas/badge.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class BadgeBase(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    points_required: int = 0

class BadgeCreate(BadgeBase):
    pass

class BadgeResponse(BadgeBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class StudentBadgeResponse(BaseModel):
    id: UUID
    badge: BadgeResponse
    earned_at: datetime

    class Config:
        from_attributes = True
