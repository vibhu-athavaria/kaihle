# app/schemas/assessment.py
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

class GeneratedQuestion(BaseModel):
    question_text: str
    question_type: str  # "multiple_choice"|"short_answer"|"true_false"
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    difficulty_level: Optional[str] = None  # "easy"|"medium"|"hard"
    metadata: Optional[Dict[str, Any]] = None

class AssessmentQuestionCreate(BaseModel):
    assessment_id: int
    knowledge_area_id: int
    question_number: int
    difficulty_level: str
    question_text: str
    question_type: str
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None

class AssessmentQuestionOut(BaseModel):
    id: int
    assessment_id: int
    knowledge_area_id: int
    question_number: int
    difficulty_level: str
    question_text: str
    question_type: str
    options: Optional[List[str]] = None
    student_answer: Optional[str] = None
    is_correct: Optional[bool] = None
    score: Optional[float] = None
    created_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class AssessmentCreate(BaseModel):
    student_id: int
    student_age: Optional[int] = None
    subject: str
    assessment_type: str = "diagnostic"

class AssessmentOut(BaseModel):
    id: int
    student_id: int
    subject: str
    grade_level: str
    status: str
    total_questions: int = 0
    questions_answered: int = 0
    overall_score: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    questions: List[AssessmentQuestionOut] = []

    class Config:
        orm_mode = True

class AnswerSubmit(BaseModel):
    answer_text: str
    time_taken: Optional[int] = Field(None, description="seconds")

class AnswerOut(BaseModel):
    question_id: int
    is_correct: bool
    score: float
    feedback: Optional[str]
    next_question: Optional[AssessmentQuestionOut]
