# app/schemas/assessment.py
from pydantic import BaseModel, Field, computed_field
from typing import Optional, List, Any, Dict
from datetime import datetime
from uuid import UUID

from app.models.assessment import AssessmentStatus, AssessmentType

class QuestionBankBase(BaseModel):
    id : UUID
    question_text: str
    question_type: str
    difficulty_level: float
    options: Optional[List[str]] = None
    learning_objectives: Optional[List[str]] = None
    prerequisite_topic_ids: Optional[List[UUID]] = None
    meta_tags: Optional[Dict[str, Any]] = None

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

class QuestionBankDetailResponse(QuestionBankBase):
    correct_answer: str
    subject_id: UUID
    topic_id: Optional[UUID] = None
    subtopic_id: Optional[UUID] = None
    grade_id: Optional[UUID] = None
    bloom_taxonomy_level: Optional[str] = None
    estimated_time_seconds: Optional[int] = None
    explanation: Optional[str] = None
    hints: Optional[Dict[str, Any]] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


class QuestionBankCreate(BaseModel):
    subject_id: UUID
    topic_id: Optional[UUID] = None
    subtopic_id: Optional[UUID] = None
    grade_id: Optional[UUID] = None
    question_text: str
    question_type: str
    options: Optional[List[str]] = None
    correct_answer: str
    difficulty_level: Optional[float] = None
    meta_tags: Optional[Dict[str, Any]] = None

class QuestionBankUpdate(BaseModel):
    id: UUID
    subject_id: Optional[UUID] = None
    topic_id: Optional[UUID] = None
    subtopic_id: Optional[UUID] = None
    grade_id: Optional[UUID] = None
    question_text: Optional[str] = None
    question_type: Optional[str] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    difficulty_level: Optional[float] = None
    meta_tags: Optional[Dict[str, Any]] = None


class AssessmentQuestionBase(BaseModel):
    id: UUID
    assessment_id: UUID
    question_number: int
    question_bank: Optional[QuestionBankBase]

class AssessmentQuestionOut(AssessmentQuestionBase):
    is_correct: Optional[bool]
    score: Optional[float]
    student_answer: Optional[str]
    hints_used: int
    time_taken: Optional[int]
    created_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None

class AssessmentCreate(BaseModel):
    student_id: UUID
    subject_id: UUID
    assessment_type: Optional[AssessmentType] = None
    total_questions_configurable: Optional[int] = None

class AssessmentUpdate(BaseModel):
    total_questions_configurable: Optional[int] = None

class AssessmentOut(BaseModel):
    id: UUID
    student_id: UUID
    subject: str
    grade_level: int
    status: str
    total_questions: int = 0
    total_questions_configurable: Optional[int] = None
    questions_answered: int = 0
    overall_score: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    questions: List[AssessmentQuestionBase] = []

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
    next_question: Optional[AssessmentQuestionBase]
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
    subject_id: UUID
    assessment_id: UUID
    assessment_report: Optional[AssessmentReportSchema]
    diagnostic_summary: Optional[str]
