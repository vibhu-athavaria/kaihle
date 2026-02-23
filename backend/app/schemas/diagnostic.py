"""
Pydantic schemas for the Diagnostic Assessment API.

Phase 7 REST API Layer schemas.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


DIFFICULTY_LABELS = {
    1: "beginner",
    2: "easy",
    3: "medium",
    4: "hard",
    5: "expert"
}


def get_difficulty_label(difficulty: int) -> str:
    return DIFFICULTY_LABELS.get(difficulty, "unknown")


class DiagnosticInitRequest(BaseModel):
    student_id: UUID


class SubtopicProgress(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subtopic_id: UUID
    subtopic_name: str
    questions_total: int
    questions_answered: int
    current_difficulty: int
    difficulty_label: str


class SessionSummaryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assessment_id: UUID
    subject_id: UUID
    subject_name: Optional[str] = None
    status: str
    total_questions: int = 0
    answered_count: int = 0
    current_subtopic_index: int = 0
    subtopics_count: int = 0
    started_at: Optional[str] = None
    last_activity: Optional[str] = None


class DiagnosticInitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sessions: List[SessionSummaryItem]
    student_id: UUID
    grade_id: Optional[UUID] = None
    curriculum_id: Optional[UUID] = None
    existing: bool = False


class SubjectStatusItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assessment_id: UUID
    subject_id: UUID
    subject_name: Optional[str] = None
    status: str
    total_questions: int = 0
    answered_count: int = 0
    progress_percentage: float = 0.0
    current_difficulty: int = 3
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class DiagnosticStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: UUID
    overall_status: str
    has_completed_assessment: bool = False
    subjects: List[SubjectStatusItem]
    all_complete: bool = False
    reports_ready: bool = False
    study_plan_ready: bool = False
    generation_status: Optional[str] = None
    generation_status_label: Optional[str] = None


class QuestionOption(BaseModel):
    key: str
    value: str


class QuestionItem(BaseModel):
    """
    Question data for delivery to client.

    CRITICAL: Never include correct_answer, explanation, or is_correct.
    These are report-only fields.
    """
    model_config = ConfigDict(from_attributes=True)

    question_id: UUID
    question_bank_id: UUID
    question_text: str
    question_type: str
    difficulty_level: int
    difficulty_label: str
    options: Optional[List[QuestionOption]] = None
    question_number: int = 1
    subtopic_name: Optional[str] = None
    estimated_time_seconds: Optional[int] = None


class NextQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assessment_id: UUID
    subject_id: UUID
    subject_name: Optional[str] = None
    question: Optional[QuestionItem] = None
    status: str
    answered_count: int = 0
    total_questions: int = 0
    current_subtopic_index: int = 0
    subtopics_count: int = 0
    subtopics: List[SubtopicProgress] = Field(default_factory=list)


class AnswerSubmitRequest(BaseModel):
    question_bank_id: UUID
    answer_text: str
    time_taken_seconds: Optional[int] = Field(None, ge=0)


class AnswerSubmitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_correct: bool
    score: float
    difficulty_level: int
    difficulty_label: str
    next_difficulty: int
    next_difficulty_label: str
    questions_answered: int
    total_questions: int
    subtopic_complete: bool
    assessment_status: str
    all_subjects_complete: bool


class SubtopicReportItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subtopic_id: Optional[UUID] = None
    subtopic_name: str
    topic_name: Optional[str] = None
    mastery_level: float
    mastery_label: str
    questions_attempted: int
    questions_correct: int
    difficulty_path: List[int] = Field(default_factory=list)
    correct_path: List[bool] = Field(default_factory=list)


class KnowledgeGapItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subtopic_id: Optional[UUID] = None
    subtopic_name: str
    topic_name: Optional[str] = None
    mastery_level: float
    mastery_label: str
    priority: str
    difficulty_reached: int
    correct_count: int
    total_count: int


class StrengthItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subtopic_id: Optional[UUID] = None
    subtopic_name: str
    topic_name: Optional[str] = None
    mastery_level: float
    mastery_label: str


class SubjectReportItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subject_id: UUID
    subject_name: Optional[str] = None
    assessment_id: UUID
    overall_mastery: float
    mastery_label: str
    total_questions: int
    total_correct: int
    highest_difficulty_reached: int
    average_difficulty_reached: float
    strongest_subtopic: Optional[str] = None
    weakest_subtopic: Optional[str] = None
    knowledge_gaps: List[KnowledgeGapItem] = Field(default_factory=list)
    strengths: List[StrengthItem] = Field(default_factory=list)
    subtopics: List[SubtopicReportItem] = Field(default_factory=list)


class DiagnosticReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: UUID
    status: str
    subjects: List[SubjectReportItem] = Field(default_factory=list)
    retry_after_seconds: Optional[int] = None
    generation_stage: Optional[str] = None


class StudyPlanCourseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: Optional[str] = None
    topic_id: Optional[UUID] = None
    subtopic_id: Optional[UUID] = None
    course_id: Optional[UUID] = None
    week: int
    day: int
    sequence_order: int
    suggested_duration_mins: int
    activity_type: str
    status: str


class StudyPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    title: str
    summary: Optional[str] = None
    total_weeks: Optional[int] = None
    status: str
    progress_percentage: int = 0
    courses: List[StudyPlanCourseItem] = Field(default_factory=list)
    retry_after_seconds: Optional[int] = None
    generation_stage: Optional[str] = None


class GenerationStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    stage: Optional[str] = None
    retry_after_seconds: int = 15


class DiagnosticAbandonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assessment_id: UUID
    status: str
    message: str
