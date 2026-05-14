"""Gap map response schemas — used by M2-1-T2 real implementation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class StudentGapScore(BaseModel):
    student_id: UUID
    student_name: str
    mastery_score: float | None  # None = this student has not yet been assessed
    last_assessed_at: datetime | None


class GapMapNode(BaseModel):
    subtopic_id: UUID
    subtopic_name: str
    topic_id: UUID
    topic_name: str
    grade_id: UUID
    grade_name: str
    class_average: float | None  # None = no students assessed on this subtopic yet
    student_count: int
    student_scores: list[StudentGapScore]


class ClassGapMap(BaseModel):
    class_id: UUID
    subject_id: UUID
    generated_at: datetime
    nodes: list[GapMapNode]
    has_student_data: bool  # True if any student has a gap_state row for this class


class StudentSubtopicScore(BaseModel):
    subtopic_id: UUID
    subtopic_name: str
    topic_id: UUID
    topic_name: str
    mastery_score: float | None
    last_assessed_at: datetime | None


class StudentGapMap(BaseModel):
    student_id: UUID
    subject_id: UUID
    generated_at: datetime
    scores: list[StudentSubtopicScore]


class ClassSummary(BaseModel):
    """Lightweight per-class mastery summary for teacher dashboard class cards.

    Distinct from ClassGapMap — this is the minimal data needed to render
    a class card with a mastery indicator. ClassGapMap is the full heatmap.
    """

    class_id: UUID
    avg_mastery: float | None  # None when no assessments have been taken
    student_count: int
    assessed_student_count: int  # students who have taken at least one assessment
    students_below_threshold: int = 0  # count of students whose avg mastery < 0.4
    last_updated_at: datetime | None
