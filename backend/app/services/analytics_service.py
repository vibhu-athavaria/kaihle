"""Analytics service — aggregated views for School Admin dashboards.

Business logic only. Route handlers must not perform aggregation directly.
"""

import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gap import GapState
from app.models.school import Class, ClassEnrollment

logger = structlog.get_logger()


@dataclass
class StudentMasterySummary:
    """Aggregated mastery data for a single student within a school."""

    student_id: uuid.UUID
    worst_mastery: float | None  # None if no GapState rows exist for this student
    class_count: int  # number of active enrollments
    needs_work_class_count: int  # classes where any subtopic is < 0.4


class AnalyticsService:
    """Service for school-level analytics aggregations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_student_mastery_summaries(
        self,
        school_id: uuid.UUID,
    ) -> list[StudentMasterySummary]:
        """Return one StudentMasterySummary per student enrolled in the given school.

        Performs two batch queries — no N+1.
        """
        # ── Query 1: enrollment counts per student ────────────────────────────
        # We need total class count AND the number of classes that have at least
        # one subtopic with mastery_score < 0.4 (Needs Work).
        #
        # "needs_work_class" = a class where MIN(mastery_score) < 0.4 for that
        # student, i.e., the student has at least one Needs Work subtopic there.
        #
        # To avoid a correlated subquery, we calculate both in one pass:
        #   1) JOIN class_enrollments → classes (school filter on classes)
        #   2) LEFT JOIN gap_states to pick up mastery data per class
        #   3) GROUP BY (student_id, class_id) to get min mastery per class
        #   4) Outer GROUP BY student_id to roll up class-level aggregates

        # Step A — per-(student, class) min mastery
        per_class_subq = (
            select(
                ClassEnrollment.student_id,
                ClassEnrollment.class_id,
                func.min(GapState.mastery_score).label("min_mastery"),
            )
            .join(Class, Class.id == ClassEnrollment.class_id)
            .outerjoin(
                GapState,
                (GapState.student_id == ClassEnrollment.student_id) & (GapState.class_id == ClassEnrollment.class_id),
            )
            .where(
                Class.school_id == school_id,
                ClassEnrollment.is_active.is_(True),
            )
            .group_by(ClassEnrollment.student_id, ClassEnrollment.class_id)
            .subquery()
        )

        # Step B — roll up to student level
        student_agg_stmt = select(
            per_class_subq.c.student_id,
            func.count().label("class_count"),
            func.min(per_class_subq.c.min_mastery).label("worst_mastery"),
            # SUM(CASE WHEN min_mastery IS NOT NULL AND min_mastery < 0.4 THEN 1 ELSE 0 END)
            # counts the number of Needs Work classes per student.
            func.sum(
                case(
                    (
                        (per_class_subq.c.min_mastery.isnot(None)) & (per_class_subq.c.min_mastery < 0.4),
                        1,
                    ),
                    else_=0,
                )
            ).label("needs_work_class_count"),
        ).group_by(per_class_subq.c.student_id)

        result = await self.db.execute(student_agg_stmt)
        rows = result.fetchall()

        summaries = [
            StudentMasterySummary(
                student_id=row.student_id,
                worst_mastery=float(row.worst_mastery) if row.worst_mastery is not None else None,
                class_count=row.class_count,
                needs_work_class_count=row.needs_work_class_count,
            )
            for row in rows
        ]

        logger.info(
            "student_mastery_summaries_fetched",
            school_id=str(school_id),
            student_count=len(summaries),
        )

        return summaries

    async def get_diagnostic_completed_student_ids(
        self,
        school_id: uuid.UUID,
        student_ids: list[uuid.UUID],
    ) -> set[uuid.UUID]:
        """Return the subset of student_ids that have at least one COMPLETED diagnostic.

        One batch query — no N+1.
        """
        if not student_ids:
            return set()

        stmt = (
            select(ClassEnrollment.student_id)
            .join(Class, Class.id == ClassEnrollment.class_id)
            .where(
                Class.school_id == school_id,
                ClassEnrollment.student_id.in_(student_ids),
                ClassEnrollment.onboarding_diagnostic_status == "COMPLETED",
            )
            .distinct()
        )

        result = await self.db.execute(stmt)
        return {row[0] for row in result.fetchall()}
