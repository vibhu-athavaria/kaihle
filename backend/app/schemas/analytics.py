"""Analytics schemas — school-level and platform-level usage data."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ClassBreakdown(BaseModel):
    class_id: UUID
    class_name: str
    student_count: int
    avg_mastery: float | None  # None if no assessments taken
    assessments_completed: int


class OnboardingFunnel(BaseModel):
    """Step-by-step counts through the student onboarding flow."""

    invited: int
    password_set: int
    profile_complete: int
    diagnostic_done: int


class AtRiskStudent(BaseModel):
    """Student with at least one class where mastery < 0.4."""

    student_id: UUID
    first_name: str
    last_name: str
    worst_mastery: float | None
    needs_work_class_count: int


class StudentMasterySummary(BaseModel):
    """Aggregated mastery data per student across all their classes."""

    student_id: UUID
    worst_mastery: float | None
    class_count: int
    needs_work_class_count: int


class SchoolAnalyticsData(BaseModel):
    """New analytics payload for the school-admin redesign dashboard."""

    school_id: UUID
    generated_at: datetime
    total_students: int
    active_students: int
    assessments_completed: int
    study_plans_active: int
    onboarding_funnel: OnboardingFunnel
    classes: list[ClassBreakdown]
    at_risk_students: list[AtRiskStudent]


# SchoolAnalytics is the canonical response schema for GET /schools/{id}/analytics.
# It is a type alias for SchoolAnalyticsData — kept as a stable name so that routes
# and downstream consumers can import it without depending on the internal class name.
SchoolAnalytics = SchoolAnalyticsData


class PlatformStats(BaseModel):
    """KaihleAdmin view — platform-wide counts across all schools."""

    total_schools: int
    total_active_students: int
    total_teachers: int
    assessments_completed_last_7_days: int
    generated_at: datetime
