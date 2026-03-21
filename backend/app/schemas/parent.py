"""Parent portal schemas. CRITICAL: numeric mastery scores are never exposed here."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class ChildSummary(BaseModel):
    student_id: UUID
    first_name: str
    last_name: str
    grade_name: str
    school_name: str
    subjects: list[str]


class TopicStatus(BaseModel):
    topic_name: str
    status: str  # "Strong" | "Developing" | "Needs Work" — plain language only
    status_label: str  # "green" | "amber" | "red"


class SubjectGapSummary(BaseModel):
    subject_name: str
    topics: list[TopicStatus]


class ParentGapMap(BaseModel):
    """Simplified gap map for parents. No mastery_score field — by design.

    Parents see plain-language labels only. The mastery_to_status() conversion
    happens in the service layer before this schema is populated.
    """

    student_name: str
    grade_name: str
    subjects: list[SubjectGapSummary]


class WeeklyReport(BaseModel):
    report_id: UUID
    week_start: date
    subject_name: str
    narrative: str
    highlights: list[str]
    created_at: datetime
