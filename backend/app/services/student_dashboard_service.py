"""Dashboard data aggregation for the student app."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

import structlog
from sqlalchemy import and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment, AssessmentStatus, AssessmentType, AttemptStatus, StudentAttempt
from app.models.curriculum import CurriculumTopic, Grade, Subject, Subtopic, Topic
from app.models.gap import GapState
from app.models.school import Class, ClassEnrollment
from app.models.study_plan import StudyPlan, StudyPlanStatus
from app.models.user import StudentProfile, User
from app.schemas.student_dashboard import ActionItem, ClassSummary, DashboardResponse

logger = structlog.get_logger(__name__)

SUBJECT_DOT_CLASS: dict[str, str] = {
    "Mathematics": "bg-brand-primary",
    "Integrated Science": "bg-violet-600",
    "Biology": "bg-green-600",
    "Chemistry": "bg-amber-600",
    "Physics": "bg-blue-600",
    "English Language": "bg-red-600",
    "English Literature": "bg-purple-600",
}


def _mastery_label(score: float | None) -> Literal["Strong", "Developing", "Needs Work", "Not assessed"]:
    if score is None:
        return "Not assessed"
    if score > 0.7:
        return "Strong"
    if score >= 0.4:
        return "Developing"
    return "Needs Work"


def _trend(recent_avg: float | None, prev_avg: float | None) -> Literal["up", "down", "flat", "none"]:
    if recent_avg is None or prev_avg is None:
        return "none"
    diff = recent_avg - prev_avg
    if diff > 0.05:
        return "up"
    if diff < -0.05:
        return "down"
    return "flat"


class StudentDashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_dashboard(self, student: User) -> DashboardResponse:
        logger.info("student_dashboard_requested", student_id=str(student.id))

        # 1. Student profile (grade name only; StudentProfile has no curriculum_id)
        profile_row = await self.db.execute(
            select(
                StudentProfile,
                Grade.name.label("grade_name"),
            )
            .join(Grade, Grade.id == StudentProfile.grade_id, isouter=True)
            .where(StudentProfile.user_id == student.id)
        )
        profile_result = profile_row.one_or_none()
        grade_name: str = profile_result.grade_name if profile_result and profile_result.grade_name else ""
        # curriculum_id is not on StudentProfile — leave empty string for now
        curriculum_name: str = ""

        # 2. Enrolled classes (filtered by school_id)
        enrollments_q = await self.db.execute(
            select(
                ClassEnrollment.class_id,
                ClassEnrollment.onboarding_diagnostic_status,
                Class.name.label("class_name"),
                Subject.id.label("subject_id"),
                Subject.name.label("subject_name"),
                User.first_name.label("teacher_first"),
                User.last_name.label("teacher_last"),
            )
            .join(Class, Class.id == ClassEnrollment.class_id)
            .join(Subject, Subject.id == Class.subject_id)
            .outerjoin(User, User.id == Class.teacher_id)
            .where(
                ClassEnrollment.student_id == student.id,
                ClassEnrollment.is_active.is_(True),  # noqa: E712
                Class.school_id == student.school_id,
            )
        )
        enrollments = enrollments_q.all()
        class_ids = [row.class_id for row in enrollments]

        # 3. Mastery averages per class
        mastery_by_class: dict[uuid.UUID, float] = {}
        if class_ids:
            mastery_q = await self.db.execute(
                select(
                    GapState.class_id,
                    func.avg(GapState.mastery_score).label("avg_mastery"),
                )
                .where(
                    GapState.student_id == student.id,
                    GapState.class_id.in_(class_ids),
                    GapState.attempt_count > 0,
                )
                .group_by(GapState.class_id)
            )
            mastery_by_class = {row.class_id: float(row.avg_mastery) for row in mastery_q.all()}

        # 4. Total topics per class (via curriculum_topics join)
        topics_total_by_class: dict[uuid.UUID, int] = {}
        if class_ids:
            topics_q = await self.db.execute(
                select(
                    Class.id.label("class_id"),
                    func.count(distinct(Topic.id)).label("total"),
                )
                .join(
                    CurriculumTopic,
                    and_(
                        CurriculumTopic.curriculum_id == Class.curriculum_id,
                        CurriculumTopic.subject_id == Class.subject_id,
                    ),
                )
                .join(Topic, Topic.id == CurriculumTopic.topic_id)
                .where(Class.id.in_(class_ids))
                .group_by(Class.id)
            )
            topics_total_by_class = {row.class_id: row.total for row in topics_q.all()}

        # 5. Assessed topics per class
        assessed_by_class: dict[uuid.UUID, int] = {}
        if class_ids:
            assessed_q = await self.db.execute(
                select(
                    GapState.class_id,
                    func.count(distinct(CurriculumTopic.topic_id)).label("assessed"),
                )
                .join(Subtopic, Subtopic.id == GapState.subtopic_id)
                .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
                .where(
                    GapState.student_id == student.id,
                    GapState.class_id.in_(class_ids),
                    GapState.attempt_count > 0,
                )
                .group_by(GapState.class_id)
            )
            assessed_by_class = {row.class_id: row.assessed for row in assessed_q.all()}

        # 6. Trend (recent vs prev week)
        # now = datetime.now(UTC)
        # week_ago = now - timedelta(days=7)
        # two_weeks_ago = now - timedelta(days=14)
        trend_by_class: dict[uuid.UUID, Literal["up", "down", "flat", "none"]] = {}
        # Let's comment for now We don't need show this for MVP (TODO)
        # if class_ids:
        #     trend_q = await self.db.execute(
        #         text(
        #             """
        #             SELECT gs.class_id,
        #                    AVG(CASE WHEN sats.attempted_at >= :week_ago THEN sats.score END) AS recent_avg,
        #                    AVG(CASE WHEN sats.attempted_at < :week_ago
        #                              AND sats.attempted_at >= :two_weeks_ago THEN sats.score END) AS prev_avg
        #             FROM student_attempt_subtopic_scores sats
        #             JOIN gap_states gs
        #               ON gs.subtopic_id = sats.subtopic_id
        #              AND gs.student_id = sats.student_id
        #             WHERE sats.student_id = :student_id
        #               AND sats.attempted_at >= :two_weeks_ago
        #               AND gs.class_id = ANY(:class_ids)
        #             GROUP BY gs.class_id
        #             """
        #         ),
        #         {
        #             "student_id": student.id,
        #             "week_ago": week_ago,
        #             "two_weeks_ago": two_weeks_ago,
        #             "class_ids": class_ids,
        #         },
        #     )
        #     trend_by_class = {
        #         row.class_id: _trend(
        #             float(row.recent_avg) if row.recent_avg is not None else None,
        #             float(row.prev_avg) if row.prev_avg is not None else None,
        #         )
        #         for row in trend_q.all()
        #     }

        # 7. Build ClassSummary list
        classes: list[ClassSummary] = []
        for row in enrollments:
            mastery = mastery_by_class.get(row.class_id)
            classes.append(
                ClassSummary(
                    class_id=row.class_id,
                    class_name=row.class_name,
                    subject_id=row.subject_id,
                    subject_name=row.subject_name,
                    subject_color=SUBJECT_DOT_CLASS.get(row.subject_name, "bg-brand-muted"),
                    teacher_name=f"{row.teacher_first} {row.teacher_last}".strip(),
                    mastery_score=mastery if mastery is not None else None,
                    mastery_label=_mastery_label(mastery),
                    topics_total=topics_total_by_class.get(row.class_id, 0),
                    topics_assessed=assessed_by_class.get(row.class_id, 0),
                    diagnostic_status=row.onboarding_diagnostic_status,
                    trend=trend_by_class.get(row.class_id, "none"),
                )
            )

        # 8. Action items
        action_items: list[ActionItem] = []

        # (a) Class assessments Pending
        if class_ids:
            assessments_q = await self.db.execute(
                select(
                    Assessment.id,
                    Assessment.deadline,
                    Assessment.class_id,
                    Assessment.title,
                    StudentAttempt.id.label("attempt_id"),
                    Class.name.label("class_name"),
                    Subject.name.label("subject_name"),
                )
                .join(Class, Class.id == Assessment.class_id)
                .join(Subject, Subject.id == Class.subject_id)
                .outerjoin(
                    StudentAttempt,
                    and_(
                        StudentAttempt.assessment_id == Assessment.id,
                        StudentAttempt.student_id == student.id,
                    ),
                )
                .where(
                    Assessment.class_id.in_(class_ids),
                    Assessment.status == AssessmentStatus.ACTIVE,
                    Assessment.assessment_type != AssessmentType.DIAGNOSTIC,
                    # Only surface assessments not yet completed
                    (StudentAttempt.id.is_(None) | (StudentAttempt.status != AttemptStatus.COMPLETED)),
                )
                .order_by(Assessment.created_at.desc())
            )
            for a in assessments_q.all():
                a_url = f"/student/assessments/{a.attempt_id}/take" if a.attempt_id else ""
                action_items.append(
                    ActionItem(
                        type="assessment_due",
                        title=a.title,
                        class_id=a.class_id,
                        assessment_id=a.id,
                        class_name=a.class_name,
                        subject_name=a.subject_name,
                        priority=1,
                        due_date=None,
                        action_url=a_url,
                    )
                )

        # (b) Study plans ACTIVE
        if class_ids:
            plans_q = await self.db.execute(
                select(
                    StudyPlan.id,
                    StudyPlan.class_id,
                    Class.name.label("class_name"),
                    Subject.name.label("subject_name"),
                )
                .join(Class, Class.id == StudyPlan.class_id)
                .join(Subject, Subject.id == Class.subject_id)
                .where(
                    StudyPlan.student_id == student.id,
                    StudyPlan.class_id.in_(class_ids),
                    StudyPlan.status == StudyPlanStatus.ACTIVE,
                )
            )
            for p in plans_q.all():
                action_items.append(
                    ActionItem(
                        type="study_plan_continue",
                        class_id=p.class_id,
                        class_name=p.class_name,
                        subject_name=p.subject_name,
                        priority=2,
                        due_date=None,
                        action_url=f"/student/classes/{p.class_id}?tab=study-plan",
                    )
                )

        # (c) Diagnostic pending
        if class_ids:
            diagnostics_q = await self.db.execute(
                select(
                    Assessment.id,
                    Assessment.class_id,
                    Class.name.label("class_name"),
                    Subject.name.label("subject_name"),
                    StudentAttempt.id.label("attempt_id"),
                    StudentAttempt.status.label("attempt_status"),
                )
                .join(Class, Class.id == Assessment.class_id)
                .join(Subject, Subject.id == Class.subject_id)
                .outerjoin(
                    StudentAttempt,
                    and_(
                        StudentAttempt.assessment_id == Assessment.id,
                        StudentAttempt.student_id == student.id,
                    ),
                )
                .where(
                    Assessment.class_id.in_(class_ids),
                    Assessment.status == AssessmentStatus.ACTIVE,
                    Assessment.assessment_type == AssessmentType.DIAGNOSTIC,
                    (StudentAttempt.id.is_(None) | (StudentAttempt.status != AttemptStatus.COMPLETED)),
                )
            )
            for d in diagnostics_q.all():
                if d.attempt_id and d.attempt_status != AttemptStatus.COMPLETED:
                    d_url: str | None = f"/student/assessments/{d.attempt_id}/take"
                else:
                    d_url = None
                action_items.append(
                    ActionItem(
                        type="diagnostic_pending",
                        class_id=d.class_id,
                        assessment_id=d.id,
                        class_name=d.class_name,
                        subject_name=d.subject_name,
                        priority=3,
                        due_date=None,
                        action_url=d_url,
                    )
                )

        action_items.sort(
            key=lambda a: (
                a.priority,
                a.due_date or datetime.max.replace(tzinfo=UTC),
            )
        )

        return DashboardResponse(
            student_name=f"{student.first_name} {student.last_name}".strip(),
            grade=grade_name,
            curriculum=curriculum_name,
            action_items=action_items,
            classes=classes,
        )
