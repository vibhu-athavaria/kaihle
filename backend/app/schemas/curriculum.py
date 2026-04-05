"""Curriculum schemas — global read-only data, no school_id."""

from uuid import UUID

from pydantic import BaseModel


class GradeResponse(BaseModel):
    id: UUID
    name: str  # e.g. "Grade 9"
    level: int  # e.g. 9
    curriculum_id: UUID | None = None  # None when no curriculum filter applied


class SubjectResponse(BaseModel):
    id: UUID
    name: str  # e.g. "Mathematics"
    code: str  # e.g. "MATH"


class TopicResponse(BaseModel):
    id: UUID
    name: str
    subject_id: UUID
    grade_id: UUID
    order: int


class SubtopicResponse(BaseModel):
    id: UUID
    name: str
    topic_id: UUID
    order: int


class CurriculumResponse(BaseModel):
    id: UUID
    name: str  # e.g. "Cambridge IGCSE"
    code: str  # e.g. "igcse"
    is_active: bool


# Simplified schemas for dropdown use (id, name only)
class TopicSimpleResponse(BaseModel):
    id: UUID
    name: str


class SubtopicSimpleResponse(BaseModel):
    id: UUID
    name: str


class CurriculumTopicSimpleResponse(BaseModel):
    id: UUID
    name: str
