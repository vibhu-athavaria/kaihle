from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

class TutorSessionBase(BaseModel):
    student_id: UUID
    session_type: str

class TutorSessionCreate(TutorSessionBase):
    pass

class TutorSession(TutorSessionBase):
    id: UUID
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TutorInteractionBase(BaseModel):
    user_message: str
    context_data: Optional[Dict[str, Any]] = None

class TutorInteractionCreate(TutorInteractionBase):
    id: UUID
    session_id: UUID
    ai_response: str
    feedback_score: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RecommendationRequest(BaseModel):
    student_id: UUID
    subject: Optional[str] = None
    difficulty_preference: Optional[str] = None
    learning_goals: Optional[List[str]] = None

class RecommendationResponse(BaseModel):
    recommendations: List[str]
    suggested_lessons: List[UUID]
    reasoning: str
    personalization_factors: Dict[str, Any]


class ChatMessage(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str
    session_id: UUID
    suggestions: Optional[List[str]] = None
