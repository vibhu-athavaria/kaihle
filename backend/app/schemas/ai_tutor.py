from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class TutorSessionBase(BaseModel):
    student_id: int
    lesson_id: Optional[int] = None
    session_type: str

class TutorSessionCreate(TutorSessionBase):
    pass

class TutorSession(TutorSessionBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class TutorInteractionBase(BaseModel):
    user_message: str
    context_data: Optional[Dict[str, Any]] = None

class TutorInteractionCreate(TutorInteractionBase):
    session_id: int

class TutorInteraction(TutorInteractionBase):
    id: int
    session_id: int
    ai_response: str
    feedback_score: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class RecommendationRequest(BaseModel):
    student_id: int
    subject: Optional[str] = None
    difficulty_preference: Optional[str] = None
    learning_goals: Optional[List[str]] = None

class RecommendationResponse(BaseModel):
    recommendations: List[str]
    suggested_lessons: List[int]
    reasoning: str
    personalization_factors: Dict[str, Any]

class AnswerSubmission(BaseModel):
    student_id: int
    lesson_id: int
    question: str
    student_answer: str
    correct_answer: Optional[str] = None

class AnswerEvaluation(BaseModel):
    score: int
    feedback: str
    suggestions: List[str]
    is_correct: bool

class StudentAnswerResponse(BaseModel):
    id: int
    question: str
    student_answer: str
    ai_evaluation: str
    score: Optional[int] = None
    feedback: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChatMessage(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str
    session_id: int
    suggestions: Optional[List[str]] = None
