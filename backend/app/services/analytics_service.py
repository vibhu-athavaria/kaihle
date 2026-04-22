"""Analytics service — school-level aggregations for the school-admin dashboard."""

from datetime import UTC, date, datetime, timedelta
from datetime import time as dt_time
from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy import Executable, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.assessment import Assessment, AttemptStatus, StudentAttempt
from app.models.curriculum import Subject
from app.models.gap import GapState
from app.models.onboarding import StudentLearningProfile
from app.models.school import Class, ClassEnrollment, School
from app.models.study_plan import StudyPlan, StudyPlanStatus
from app.models.user import User, UserRole
from app.schemas.analytics import (
    AtRiskStudent,
    ClassBreakdown,
    OnboardingFunnel,
    PlatformStats,
    SchoolAnalyticsData,
    StudentMasterySummary,
)

logger = structlog.get_logger()

# Onboarding diagnostic status — stored as plain strings in the DB
_DIAGNOSTIC_COMPLETED = "COMPLETED"


class AnalyticsService:
    def __init__(self, db: AsyncSession, redis: "Redis[bytes]") -> None:
        self._db = db
        self._redis = redis

    async def get_school_analytics(
        self,
        school_id: UUID,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> SchoolAnalyticsData:
        cache_key = f"analytics:{school_id}:{from_date}:{to_date}"
        cached = await self._redis.get(cache_key)
        if cached:
            return SchoolAnalyticsData.model_validate_json(cached)

        today = date.today()
        effective_from = from_date or (today - timedelta(days=30))
        effective_to = to_date or today
        from_dt = datetime.combine(effective_from, dt_time.min).replace(tzinfo=UTC)
        to_dt = datetime.combine(effective_to, dt_time.max).replace(tzinfo=UTC)

        total_students = await self._count(
            select(func.count(User.id)).where(
                User.school_id == school_id,
                User.role == UserRole.STUDENT,
                User.is_active.is_(True),
            )
        )
        total_teachers = await self._count(
            select(func.count(User.id)).where(
                User.school_id == school_id,
                User.role == UserRole.TEACHER,
                User.is_active.is_(True),
            )
        )
        active_students = await self._count(
            select(func.count(User.id)).where(
                User.school_id == school_id,
                User.role == UserRole.STUDENT,
                User.is_active.is_(True),
                User.last_login_at >= from_dt,
            )
        )
        assessments_completed = await self._count(
            select(func.count(StudentAttempt.id))
            .join(Assessment, Assessment.id == StudentAttempt.assessment_id)
            .join(Class, Class.id == Assessment.class_id)
            .where(
                Class.school_id == school_id,
                StudentAttempt.status == AttemptStatus.COMPLETED,
                StudentAttempt.completed_at >= from_dt,
                StudentAttempt.completed_at <= to_dt,
            )
        )
        study_plans_active = await self._count(
            select(func.count(StudyPlan.id))
            .join(User, User.id == StudyPlan.student_id)
            .where(
                User.school_id == school_id,
                StudyPlan.status == StudyPlanStatus.ACTIVE,
            )
        )
        funnel = await self._get_onboarding_funnel(school_id)
        classes = await self._get_class_breakdown(school_id, from_dt, to_dt)
        at_risk = await self._get_at_risk_students(school_id)

        logger.info(
            "analytics.school.generated",
            school_id=str(school_id),
            total_students=total_students,
        )
        result = SchoolAnalyticsData(
            school_id=school_id,
            generated_at=datetime.now(UTC),
            total_students=total_students,
            total_teachers=total_teachers,
            active_students=active_students,
            assessments_completed=assessments_completed,
            study_plans_active=study_plans_active,
            onboarding_funnel=funnel,
            classes=classes,
            at_risk_students=at_risk,
        )
        await self._redis.setex(cache_key, 300, result.model_dump_json())
        return result

    async def get_student_mastery_summaries(self, school_id: UUID) -> list[StudentMasterySummary]:
        result = await self._db.execute(
            select(
                ClassEnrollment.student_id,
                Class.id.label("class_id"),
                func.avg(GapState.mastery_score).label("avg_mastery"),
            )
            .join(Class, Class.id == ClassEnrollment.class_id)
            .join(User, User.id == ClassEnrollment.student_id)
            .join(
                GapState,
                (GapState.class_id == ClassEnrollment.class_id) & (GapState.student_id == ClassEnrollment.student_id),
                isouter=True,
            )
            .where(
                Class.school_id == school_id,
                User.school_id == school_id,  # defence-in-depth Rule 3
                ClassEnrollment.is_active.is_(True),
            )
            .group_by(ClassEnrollment.student_id, Class.id)
        )
        rows = result.all()

        student_map: dict[UUID, list[float | None]] = {}
        for row in rows:
            student_map.setdefault(row.student_id, []).append(row.avg_mastery)

        summaries: list[StudentMasterySummary] = []
        for student_id, scores in student_map.items():
            valid = [s for s in scores if s is not None]
            worst = min(valid) if valid else None
            class_count = len(scores)
            needs_work_count = sum(1 for s in valid if s < 0.4)
            summaries.append(
                StudentMasterySummary(
                    student_id=student_id,
                    worst_mastery=worst,
                    class_count=class_count,
                    needs_work_class_count=needs_work_count,
                )
            )
        logger.info("analytics.student_mastery_summaries.generated", school_id=str(school_id), count=len(summaries))
        return summaries

    async def get_platform_stats(self) -> PlatformStats:
        cache_key = "analytics:platform"
        cached = await self._redis.get(cache_key)
        if cached:
            return PlatformStats.model_validate_json(cached)

        total_schools = await self._count(select(func.count(School.id)).where(School.status == "active"))
        total_active_students = await self._count(
            select(func.count(User.id)).where(
                User.role == UserRole.STUDENT,
                User.is_active.is_(True),
            )
        )
        total_teachers = await self._count(
            select(func.count(User.id)).where(
                User.role == UserRole.TEACHER,
                User.is_active.is_(True),
            )
        )
        cutoff = datetime.now(UTC) - timedelta(days=7)
        assessments_7d = await self._count(
            select(func.count(StudentAttempt.id)).where(
                StudentAttempt.status == AttemptStatus.COMPLETED,
                StudentAttempt.completed_at >= cutoff,
            )
        )
        result = PlatformStats(
            total_schools=total_schools,
            total_active_students=total_active_students,
            total_teachers=total_teachers,
            assessments_completed_last_7_days=assessments_7d,
            generated_at=datetime.now(UTC),
        )
        await self._redis.setex(cache_key, 300, result.model_dump_json())
        return result

    async def issue_impersonation_token(
        self,
        school_id: UUID,
        kaihle_admin_id: UUID,
    ) -> dict[str, object]:
        token = create_access_token(
            user_id=kaihle_admin_id,
            school_id=school_id,
            role="KAIHLE_ADMIN",
            expires_in=120,
            extra_claims={
                "scope": "impersonation",
                "impersonated_school_id": str(school_id),
            },
        )
        logger.info(
            "analytics.impersonation_token.issued",
            school_id=str(school_id),
            kaihle_admin_id=str(kaihle_admin_id),
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "impersonated_school_id": str(school_id),
            "expires_in_seconds": 7200,
        }

    async def get_diagnostic_completed_student_ids(self, school_id: UUID, student_ids: list[UUID]) -> set[UUID]:
        """Return the subset of student_ids that have at least one COMPLETED enrollment diagnostic.

        Issues a single query for all given student IDs — no N+1.
        Returns empty set immediately when student_ids is empty.
        """
        if not student_ids:
            return set()
        rows = (
            (
                await self._db.execute(
                    select(func.distinct(ClassEnrollment.student_id))
                    .join(Class, Class.id == ClassEnrollment.class_id)
                    .where(
                        Class.school_id == school_id,
                        ClassEnrollment.student_id.in_(student_ids),
                        ClassEnrollment.onboarding_diagnostic_status == _DIAGNOSTIC_COMPLETED,
                    )
                )
            )
            .scalars()
            .all()
        )
        completed_ids = set(rows)
        logger.info(
            "analytics.diagnostic_completed_ids.fetched",
            school_id=str(school_id),
            count=len(completed_ids),
        )
        return completed_ids

    async def _count(self, stmt: Executable) -> int:
        result = await self._db.execute(stmt)
        value = result.scalar()
        return value if value is not None else 0

    async def _get_onboarding_funnel(self, school_id: UUID) -> OnboardingFunnel:
        invited = await self._count(
            select(func.count(User.id)).where(User.school_id == school_id, User.role == UserRole.STUDENT)
        )
        # is_active is set to True when the user completes password setup via magic link
        password_set = await self._count(
            select(func.count(User.id)).where(
                User.school_id == school_id,
                User.role == UserRole.STUDENT,
                User.is_active.is_(True),
            )
        )
        profile_complete = await self._count(
            select(func.count(StudentLearningProfile.student_id))
            .join(User, User.id == StudentLearningProfile.student_id)
            .where(User.school_id == school_id)
        )
        diagnostic_done = await self._count(
            select(func.count(func.distinct(ClassEnrollment.student_id)))
            .join(Class, Class.id == ClassEnrollment.class_id)
            .where(
                Class.school_id == school_id,
                ClassEnrollment.onboarding_diagnostic_status == _DIAGNOSTIC_COMPLETED,
            )
        )
        return OnboardingFunnel(
            invited=invited,
            password_set=password_set,
            profile_complete=profile_complete,
            diagnostic_done=diagnostic_done,
        )

    async def _get_class_breakdown(self, school_id: UUID, from_dt: datetime, to_dt: datetime) -> list[ClassBreakdown]:
        # The joins create a Cartesian product across ClassEnrollment × GapState × Assessment × StudentAttempt.
        # Aggregates are correct because COUNT(DISTINCT) and CASE guards prevent double-counting.
        # Restructuring to CTEs would be safer but adds significant complexity for no behaviour change.
        result = await self._db.execute(
            select(
                Class.id,
                Class.name,
                Subject.name.label("subject_name"),
                User.first_name.label("teacher_first"),
                User.last_name.label("teacher_last"),
                func.count(func.distinct(ClassEnrollment.student_id)).label("student_count"),
                func.avg(GapState.mastery_score).label("avg_mastery"),
                func.count(
                    case(
                        (
                            (StudentAttempt.status == AttemptStatus.COMPLETED)
                            & (StudentAttempt.completed_at >= from_dt)
                            & (StudentAttempt.completed_at <= to_dt),
                            StudentAttempt.id,
                        ),
                    )
                ).label("assessments_completed"),
            )
            .join(Subject, Subject.id == Class.subject_id)
            .outerjoin(User, User.id == Class.teacher_id)
            .join(
                ClassEnrollment,
                ClassEnrollment.class_id == Class.id,
                isouter=True,
            )
            .join(
                GapState,
                GapState.class_id == Class.id,
                isouter=True,
            )
            .join(
                Assessment,
                Assessment.class_id == Class.id,
                isouter=True,
            )
            .join(
                StudentAttempt,
                StudentAttempt.assessment_id == Assessment.id,
                isouter=True,
            )
            .where(Class.school_id == school_id, Class.is_active.is_(True))
            .group_by(Class.id, Subject.name, User.first_name, User.last_name)
            .order_by(func.avg(GapState.mastery_score).asc().nulls_first())
        )
        rows = result.all()

        return [
            ClassBreakdown(
                class_id=row.id,
                class_name=row.name,
                subject_name=row.subject_name,
                teacher_name=(
                    f"{row.teacher_first} {row.teacher_last}" if row.teacher_first and row.teacher_last else None
                ),
                student_count=row.student_count or 0,
                avg_mastery=row.avg_mastery,
                assessments_completed=row.assessments_completed or 0,
            )
            for row in rows
        ]

    async def _get_at_risk_students(self, school_id: UUID) -> list[AtRiskStudent]:
        summaries = await self.get_student_mastery_summaries(school_id)
        at_risk = [s for s in summaries if s.worst_mastery is not None and s.worst_mastery < 0.4]
        at_risk.sort(key=lambda s: (s.worst_mastery or 1.0))

        if not at_risk:
            return []

        student_ids = [s.student_id for s in at_risk]
        user_result = await self._db.execute(
            select(User.id, User.first_name, User.last_name).where(
                User.school_id == school_id,
                User.id.in_(student_ids),
            )
        )
        users = user_result.all()
        user_map = {u.id: u for u in users}

        missing = [s.student_id for s in at_risk if s.student_id not in user_map]
        if missing:
            logger.warning(
                "analytics.at_risk.missing_users",
                school_id=str(school_id),
                missing_student_ids=[str(sid) for sid in missing],
            )

        return [
            AtRiskStudent(
                student_id=s.student_id,
                first_name=user_map[s.student_id].first_name if s.student_id in user_map else "",
                last_name=user_map[s.student_id].last_name if s.student_id in user_map else "",
                worst_mastery=s.worst_mastery,
                needs_work_class_count=s.needs_work_class_count,
            )
            for s in at_risk
            if s.student_id in user_map
        ]
