"""Gap map response schemas — used by M2-1-T2 real implementation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class StudentGapScore(BaseModel):
    student_id: UUID
    student_name: str
    mastery_score: float | None  # None = this student has not yet been assessed
    last_assessed_at: datetime | None

    # How much evidence stands behind mastery_score, in [0,1]. Computed and stored on every
    # gap_states row since M1 but never surfaced — a student assessed on two questions and
    # one assessed on forty could render identically, and a teacher deciding whether to
    # intervene cannot tell "this student is middling" from "we barely have data".
    # None when never assessed, matching mastery_score.
    confidence: float | None = None

    # Responses behind the estimate. ALWAYS None until MLH-T3 adds
    # student_attempt_subtopic_scores.total_count — gap_states.attempt_count counts
    # ATTEMPTS, and three attempts of one question each is not the evidence of one attempt
    # of thirty. The field ships now so the frontend contract does not change when T3 lands.
    total_responses: int | None = None


class GapMapNode(BaseModel):
    subtopic_id: UUID
    subtopic_name: str
    topic_id: UUID
    topic_name: str
    grade_id: UUID
    grade_name: str
    grade_level: int
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
    confidence: float | None = None  # see StudentGapScore.confidence
    total_responses: int | None = None  # see StudentGapScore.total_responses


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
