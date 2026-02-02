# app/schemas/assessment.py
from pydantic import BaseModel, Field, computed_field
from typing import Optional, List, Any, Dict
from datetime import datetime
from uuid import UUID

class QuestionCreateRequest(BaseModel):
    question_text: str
    question_type: str  # "multiple_choice"|"short_answer"|"true_false"
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    difficulty_level: Optional[str] = None  # "easy"|"medium"|"hard"
    metadata: Optional[Dict[str, Any]] = None

class QuestionOut(BaseModel):
    id: UUID
    assessment_id: UUID
    question_bank_id: UUID
    is_correct: Optional[bool]
    score: Optional[float]
    student_answer: Optional[str]
    question_number: int
    # Nested QuestionBank fields
    question_bank: Optional["QuestionBankResponse"]

class QuestionBankResponse(BaseModel):
    id: UUID
    question_text: str
    question_type: str
    difficulty_level: float
    options: Optional[List[str]] = None
    correct_answer: str
    learning_objectives: Optional[List[str]] = None
    prerequisites: Optional[List[str]] = None
    subject: Optional[str] = None
    topic: Optional[str] = None
    description: Optional[str] = None

    @computed_field
    @property
    def difficulty_label(self) -> str:
        if self.difficulty_level is None:
            return "unknown"
        if self.difficulty_level < 0.33:
            return "easy"
        elif self.difficulty_level < 0.66:
            return "medium"
        else:
            return "hard"

    class Config:
        orm_mode = True

class AssessmentQuestionOut(BaseModel):
    id: UUID
    assessment_id: UUID
    knowledge_area_id: UUID
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
    student_id: UUID
    subject: str


class AssessmentOut(BaseModel):
    id: UUID
    student_id: UUID
    subject: str
    grade_level: int
    status: str
    total_questions: int = 0
    questions_answered: int = 0
    overall_score: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    questions: List[QuestionOut] = []

    class Config:
        orm_mode = True

class AnswerSubmit(BaseModel):
    answer_text: str
    time_taken: Optional[int] = Field(None, description="seconds")

class AnswerOut(BaseModel):
    question_id: UUID
    is_correct: bool
    score: float
    feedback: Optional[str]
    next_question: Optional[QuestionOut]
    status: str  # "in_progress"|"completed"

class AssessmentReport(BaseModel):
    id: UUID
    assessment_id: UUID
    diagnostic_summary: str
    study_plan_json: List[Dict[str, Any]]
    mastery_table_json: List[Dict[str, Any]]

    class Config:
        orm_mode = True

class AssessmentTopic(BaseModel):
    name: str
    correct: int
    total: int

class AssessmentReportSchema(BaseModel):
    score: int
    total: int
    topics: List[AssessmentTopic]

class AssessmentReportResponse(BaseModel):
    completed: bool
    subject: str
    assessment_id: UUID
    assessment_report: Optional[AssessmentReportSchema]
    diagnostic_summary: Optional[str]
