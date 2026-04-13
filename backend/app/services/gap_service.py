"""Gap state service.

Computes per-subtopic mastery scores and upserts gap_states rows.
Used by the calculate_gap_states Celery task.

Also provides read methods for the gap map UI (M2-1-T2):
  - get_class_gap_map: teacher heatmap
  - get_student_gap_map: student progress view
  - get_class_summary: lightweight class card summary
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import CurriculumTopic, Subtopic, Topic
from app.models.gap import GapState
from app.models.school import Class, ClassEnrollment
from app.models.user import User
from app.schemas.gap_map import (
    ClassGapMap,
    ClassSummary,
    GapMapNode,
    StudentGapMap,
    StudentGapScore,
    StudentSubtopicScore,
)

logger = structlog.get_logger()


class GapService:
    """Service responsible for maintaining student gap states.

    All writes use PostgreSQL INSERT ... ON CONFLICT DO UPDATE to be idempotent.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert_gap_state(
        self,
        student_id: uuid.UUID,
        subtopic_id: uuid.UUID,
        school_id: uuid.UUID,
        class_id: uuid.UUID,
        new_mastery: float,
        rolling_attempt_count: int,
        last_assessed_at: datetime,
    ) -> None:
        """Atomically upsert a gap_state row using ON CONFLICT DO UPDATE.

        Uses the unique constraint (student_id, subtopic_id, class_id) as conflict target.
        On conflict, updates mastery_score, attempt_count, and related fields.
        needs_review is set TRUE when mastery < 0.4, FALSE otherwise.

        Args:
            student_id: The student UUID.
            subtopic_id: The subtopic UUID.
            school_id: The school UUID (stored for context — gap_states is school-scoped via class).
            class_id: The class UUID (gap states are per-class).
            new_mastery: Recency-weighted mastery score [0.0, 1.0].
            rolling_attempt_count: Total number of attempts for this subtopic.
            last_assessed_at: Timestamp of the most recent assessment.
        """
        needs_review = new_mastery < 0.4

        # Confidence grows with attempt count: min(attempt_count / 5, 1.0)
        # 5+ attempts = full confidence (1.0), fewer = proportional confidence
        confidence = min(rolling_attempt_count / 5.0, 1.0)

        # gap_states.last_assessed_at is TIMESTAMP WITHOUT TIME ZONE in the schema.
        # asyncpg rejects timezone-aware datetimes for non-tz columns — strip tzinfo.
        if last_assessed_at.tzinfo is not None:
            last_assessed_at = last_assessed_at.replace(tzinfo=None)

        stmt = text(
            """
            INSERT INTO gap_states (
                id,
                student_id,
                subtopic_id,
                class_id,
                mastery_score,
                confidence,
                attempt_count,
                total_correct,
                total_attempted,
                needs_review,
                last_assessed_at,
                updated_at
            )
            VALUES (
                gen_random_uuid(),
                :student_id,
                :subtopic_id,
                :class_id,
                :mastery_score,
                :confidence,
                :attempt_count,
                0,
                0,
                :needs_review,
                :last_assessed_at,
                NOW()
            )
            ON CONFLICT (student_id, subtopic_id, class_id) DO UPDATE SET
                mastery_score    = EXCLUDED.mastery_score,
                confidence       = EXCLUDED.confidence,
                attempt_count    = EXCLUDED.attempt_count,
                needs_review     = EXCLUDED.needs_review,
                last_assessed_at = EXCLUDED.last_assessed_at,
                updated_at       = NOW()
            """
        )

        await self.db.execute(
            stmt,
            {
                "student_id": student_id,
                "subtopic_id": subtopic_id,
                "class_id": class_id,
                "mastery_score": new_mastery,
                "confidence": confidence,
                "attempt_count": rolling_attempt_count,
                "needs_review": needs_review,
                "last_assessed_at": last_assessed_at,
            },
        )

        logger.info(
            "gap_state_upserted",
            student_id=str(student_id),
            subtopic_id=str(subtopic_id),
            class_id=str(class_id),
            mastery_score=new_mastery,
            needs_review=needs_review,
            attempt_count=rolling_attempt_count,
        )

    async def calculate_gap_states_for_attempt(self, attempt_id: uuid.UUID) -> dict[str, object]:
        """Calculate and persist gap states for a completed attempt.

        This is the async core of the calculate_gap_states Celery task.
        Can be called directly in tests (no event loop nesting issue).

        Args:
            attempt_id: The StudentAttempt UUID.

        Returns:
            Dict with attempt_id and subtopics_updated count.
        """
        from app.models.assessment import (
            Assessment,
            AttemptStatus,
            StudentAttempt,
            StudentResponse,
        )
        from app.models.curriculum import QuestionBank

        attempt_id_str = str(attempt_id)

        # Step 1: Load attempt, verify COMPLETED
        attempt_result = await self.db.execute(select(StudentAttempt).where(StudentAttempt.id == attempt_id))
        attempt: StudentAttempt | None = attempt_result.scalar_one_or_none()

        if attempt is None:
            logger.warning("calculate_gap_states_skipped_attempt_not_found", attempt_id=attempt_id_str)
            return {"attempt_id": attempt_id_str, "subtopics_updated": 0}

        if attempt.status != AttemptStatus.COMPLETED:
            logger.warning(
                "calculate_gap_states_skipped_attempt_not_completed",
                attempt_id=attempt_id_str,
                status=attempt.status,
            )
            return {"attempt_id": attempt_id_str, "subtopics_updated": 0}

        # Step 2: Load assessment
        assessment_result = await self.db.execute(select(Assessment).where(Assessment.id == attempt.assessment_id))
        assessment: Assessment | None = assessment_result.scalar_one_or_none()
        if assessment is None:
            logger.warning("calculate_gap_states_skipped_assessment_not_found", attempt_id=attempt_id_str)
            return {"attempt_id": attempt_id_str, "subtopics_updated": 0}

        is_system_generated: bool = assessment.is_system_generated

        # Step 3: Load responses
        responses_result = await self.db.execute(
            select(StudentResponse).where(StudentResponse.attempt_id == attempt_id)
        )
        responses: list[StudentResponse] = list(responses_result.scalars().all())

        if not responses:
            logger.warning("calculate_gap_states_skipped_no_responses", attempt_id=attempt_id_str)
            return {"attempt_id": attempt_id_str, "subtopics_updated": 0}

        # Step 4: Map question_id → subtopic_id
        question_ids = [r.question_id for r in responses]
        q_result = await self.db.execute(
            select(QuestionBank.id, QuestionBank.subtopic_id).where(QuestionBank.id.in_(question_ids))
        )
        question_to_subtopic: dict[uuid.UUID, uuid.UUID] = {row[0]: row[1] for row in q_result.all()}

        # Step 5: Group responses by subtopic, compute per-subtopic score
        subtopic_correct: dict[uuid.UUID, int] = defaultdict(int)
        subtopic_total: dict[uuid.UUID, int] = defaultdict(int)
        for response in responses:
            sub_id = question_to_subtopic.get(response.question_id)
            if sub_id is None:
                logger.error(
                    "calculate_gap_states_unknown_question_skipped",
                    question_id=str(response.question_id),
                    attempt_id=attempt_id_str,
                )
                continue
            subtopic_total[sub_id] += 1
            if response.is_correct:
                subtopic_correct[sub_id] += 1

        # Step 6 + 7 + 8: Compute mastery, upsert gap_state, insert score row
        raw_completed_at = attempt.completed_at or datetime.now(UTC)
        # Normalise to timezone-aware for use with TIMESTAMPTZ columns.
        # upsert_gap_state handles stripping tzinfo for gap_states.last_assessed_at
        # (TIMESTAMP WITHOUT TIME ZONE), while student_attempt_subtopic_scores.attempted_at
        # is TIMESTAMPTZ and needs timezone-aware datetime.
        if raw_completed_at.tzinfo is None:
            assessed_at = raw_completed_at.replace(tzinfo=UTC)
        else:
            assessed_at = raw_completed_at
        subtopics_updated = 0

        for sub_id, total in subtopic_total.items():
            if total == 0:
                continue

            current_score = subtopic_correct[sub_id] / total

            # Load last 2 historical scores (excluding this attempt)
            hist_result = await self.db.execute(
                text(
                    """
                    SELECT score, attempted_at
                    FROM student_attempt_subtopic_scores
                    WHERE student_id = :student_id
                      AND subtopic_id = :subtopic_id
                      AND attempt_id != :attempt_id
                    ORDER BY attempted_at DESC
                    LIMIT 2
                    """
                ),
                {
                    "student_id": attempt.student_id,
                    "subtopic_id": sub_id,
                    "attempt_id": attempt_id,
                },
            )
            historical = hist_result.all()

            if len(historical) == 0:
                mastery = current_score * 0.7 if is_system_generated else current_score * 1.0
                rolling_count = 1
            elif len(historical) == 1:
                mastery = (current_score * 0.65) + (historical[0][0] * 0.35)
                rolling_count = 2
            else:
                mastery = (current_score * 0.5) + (historical[0][0] * 0.3) + (historical[1][0] * 0.2)
                rolling_count = len(historical) + 1

            mastery = max(0.0, min(1.0, mastery))

            await self.upsert_gap_state(
                student_id=attempt.student_id,
                subtopic_id=sub_id,
                school_id=assessment.school_id,
                class_id=assessment.class_id,
                new_mastery=mastery,
                rolling_attempt_count=rolling_count,
                last_assessed_at=assessed_at,
            )

            await self.db.execute(
                text(
                    """
                    INSERT INTO student_attempt_subtopic_scores
                        (id, student_id, subtopic_id, attempt_id, score, attempted_at)
                    VALUES
                        (gen_random_uuid(), :student_id, :subtopic_id, :attempt_id,
                         :score, :attempted_at)
                    ON CONFLICT (student_id, subtopic_id, attempt_id) DO NOTHING
                    """
                ),
                {
                    "student_id": attempt.student_id,
                    "subtopic_id": sub_id,
                    "attempt_id": attempt_id,
                    "score": current_score,
                    "attempted_at": assessed_at,
                },
            )

            subtopics_updated += 1

        return {"attempt_id": attempt_id_str, "subtopics_updated": subtopics_updated}

    async def get_class_gap_map(
        self,
        class_id: uuid.UUID,
        school_id: uuid.UUID,
        subject_id: uuid.UUID,
    ) -> ClassGapMap:
        """Aggregate gap_states for all enrolled students in a class, grouped by subtopic.

        Returns one GapMapNode per subtopic belonging to the given subject and grade.
        Subtopics with no gap_state rows are still included with empty student_scores
        and class_average=None (not yet assessed, different from low mastery).

        Multi-tenancy: verifies class_.school_id == school_id before any data access.
        gap_states does not have school_id — scoping is enforced via class_id which
        is itself scoped to school_id.

        Args:
            class_id: The class to aggregate for. Must belong to school_id.
            school_id: Used to verify class ownership — CONSTITUTION Rule 3.
            subject_id: Filter subtopics to this subject.
        """
        class_ = await self.db.scalar(
            select(Class).where(
                Class.id == class_id,
                Class.school_id == school_id,
                Class.is_active.is_(True),
            )
        )
        if not class_:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Class {class_id} not found in school {school_id}",
            )

        subtopic_rows = (
            await self.db.execute(
                select(
                    Subtopic.id.label("subtopic_id"),
                    Subtopic.name.label("subtopic_name"),
                    Topic.id.label("topic_id"),
                    Topic.name.label("topic_name"),
                )
                .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
                .join(Topic, Topic.id == CurriculumTopic.topic_id)
                .where(
                    CurriculumTopic.subject_id == subject_id,
                    CurriculumTopic.grade_id == class_.grade_id,
                    CurriculumTopic.is_active.is_(True),
                    Subtopic.is_active.is_(True),
                )
                .order_by(Topic.name, Subtopic.name)
            )
        ).all()

        gap_rows = (
            await self.db.execute(
                select(
                    GapState.subtopic_id,
                    GapState.student_id,
                    GapState.mastery_score,
                    GapState.last_assessed_at,
                    User.first_name,
                    User.last_name,
                )
                .join(User, User.id == GapState.student_id)
                .where(
                    GapState.class_id == class_id,
                )
            )
        ).all()

        gaps_by_subtopic: dict[uuid.UUID, list[Any]] = defaultdict(list)
        for row in gap_rows:
            gaps_by_subtopic[row.subtopic_id].append(row)

        nodes = []
        for st in subtopic_rows:
            student_gaps = gaps_by_subtopic.get(st.subtopic_id, [])
            student_scores = [
                StudentGapScore(
                    student_id=g.student_id,
                    student_name=f"{g.first_name} {g.last_name}",
                    mastery_score=g.mastery_score,
                    last_assessed_at=g.last_assessed_at,
                )
                for g in student_gaps
            ]
            scored = [s for s in student_scores if s.mastery_score is not None]
            class_average: float | None = (
                sum(s.mastery_score for s in scored if s.mastery_score is not None) / len(scored) if scored else None
            )
            nodes.append(
                GapMapNode(
                    subtopic_id=st.subtopic_id,
                    subtopic_name=st.subtopic_name,
                    topic_id=st.topic_id,
                    topic_name=st.topic_name,
                    class_average=class_average,
                    student_count=len(student_scores),
                    student_scores=student_scores,
                )
            )

        return ClassGapMap(
            class_id=class_id,
            subject_id=subject_id,
            generated_at=datetime.now(UTC),
            nodes=nodes,
        )

    async def get_student_gap_map(
        self,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
        subject_id: uuid.UUID,
    ) -> StudentGapMap:
        """Return gap_states for a single student filtered by subject.

        Subtopics with no gap state are included with mastery_score=None and
        last_assessed_at=None (frontend renders as grey "Not assessed").

        Multi-tenancy: only returns data for classes where Class.school_id == school_id.

        Args:
            student_id: The student to return data for.
            school_id: Multi-tenancy guard — CONSTITUTION Rule 3.
            subject_id: Filter to one subject's subtopics.
        """
        enrolled_class = await self.db.scalar(
            select(Class)
            .join(ClassEnrollment, ClassEnrollment.class_id == Class.id)
            .where(
                ClassEnrollment.student_id == student_id,
                ClassEnrollment.is_active.is_(True),
                Class.school_id == school_id,
                Class.subject_id == subject_id,
                Class.is_active.is_(True),
            )
        )

        if not enrolled_class:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No class enrollment found for student in this subject",
            )

        subtopic_rows = (
            await self.db.execute(
                select(
                    Subtopic.id.label("subtopic_id"),
                    Subtopic.name.label("subtopic_name"),
                    Topic.id.label("topic_id"),
                    Topic.name.label("topic_name"),
                )
                .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
                .join(Topic, Topic.id == CurriculumTopic.topic_id)
                .where(
                    CurriculumTopic.subject_id == subject_id,
                    CurriculumTopic.grade_id == enrolled_class.grade_id,
                    CurriculumTopic.is_active.is_(True),
                    Subtopic.is_active.is_(True),
                )
                .order_by(Topic.name, Subtopic.name)
            )
        ).all()

        subtopic_ids = [row.subtopic_id for row in subtopic_rows]

        gap_rows = (
            (
                await self.db.execute(
                    select(
                        GapState.subtopic_id,
                        GapState.mastery_score,
                        GapState.last_assessed_at,
                    ).where(
                        GapState.student_id == student_id,
                        GapState.class_id == enrolled_class.id,
                        GapState.subtopic_id.in_(subtopic_ids),
                    )
                )
            ).all()
            if subtopic_ids
            else []
        )

        gaps_by_subtopic = {row.subtopic_id: row for row in gap_rows}

        scores = [
            StudentSubtopicScore(
                subtopic_id=st.subtopic_id,
                subtopic_name=st.subtopic_name,
                topic_id=st.topic_id,
                topic_name=st.topic_name,
                mastery_score=gaps_by_subtopic[st.subtopic_id].mastery_score
                if st.subtopic_id in gaps_by_subtopic
                else None,
                last_assessed_at=gaps_by_subtopic[st.subtopic_id].last_assessed_at
                if st.subtopic_id in gaps_by_subtopic
                else None,
            )
            for st in subtopic_rows
        ]

        return StudentGapMap(
            student_id=student_id,
            subject_id=subject_id,
            generated_at=datetime.now(UTC),
            scores=scores,
        )

    async def get_class_summary(
        self,
        class_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> ClassSummary:
        """Return lightweight mastery summary for a teacher dashboard class card.

        Cheaper than get_class_gap_map — returns aggregate counts only, no per-student
        breakdown. Used to populate avg_mastery on class cards.

        Multi-tenancy: verifies class_.school_id == school_id before any data access.

        Args:
            class_id: Must belong to school_id.
            school_id: Multi-tenancy guard — CONSTITUTION Rule 3.
        """
        class_ = await self.db.scalar(
            select(Class).where(
                Class.id == class_id,
                Class.school_id == school_id,
            )
        )
        if not class_:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Class {class_id} not found in school {school_id}",
            )

        agg_result = await self.db.execute(
            select(
                func.avg(GapState.mastery_score).label("avg_mastery"),
                func.count(func.distinct(GapState.student_id)).label("assessed_students"),
                func.max(GapState.last_assessed_at).label("last_updated"),
            ).where(
                GapState.class_id == class_id,
            )
        )
        row = agg_result.one()

        # Count students whose per-student average mastery is below the 0.4 threshold.
        # Uses a subquery so we compare per-student averages, not individual gap rows.
        student_avg_sub = (
            select(
                GapState.student_id,
                func.avg(GapState.mastery_score).label("student_avg"),
            )
            .where(GapState.class_id == class_id)
            .group_by(GapState.student_id)
            .subquery()
        )
        below_result = await self.db.scalar(
            select(func.count()).select_from(student_avg_sub).where(student_avg_sub.c.student_avg < 0.4)
        )

        total_students = await self.db.scalar(
            select(func.count())
            .select_from(ClassEnrollment)
            .where(
                ClassEnrollment.class_id == class_id,
                ClassEnrollment.is_active.is_(True),
            )
        )

        return ClassSummary(
            class_id=class_id,
            avg_mastery=float(row.avg_mastery) if row.avg_mastery is not None else None,
            student_count=total_students or 0,
            assessed_student_count=row.assessed_students or 0,
            students_below_threshold=below_result or 0,
            last_updated_at=row.last_updated,
        )

    async def _verify_teacher_has_student_access(
        self,
        teacher_id: uuid.UUID,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> bool:
        """Return True if the teacher owns at least one active class the student is enrolled in,
        within the given school.

        CONSTITUTION Rule 3: school_id filter prevents cross-school enrollment leakage.
        """
        result = await self.db.execute(
            select(ClassEnrollment.class_id)
            .join(Class, Class.id == ClassEnrollment.class_id)
            .where(
                ClassEnrollment.student_id == student_id,
                ClassEnrollment.is_active.is_(True),
                Class.teacher_id == teacher_id,
                Class.school_id == school_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_class_summaries_batch(
        self,
        class_ids: list[uuid.UUID],
        school_id: uuid.UUID,
    ) -> dict[uuid.UUID, ClassSummary]:
        """Return mastery summaries for multiple classes in a single query.

        More efficient than calling get_class_summary() in a loop - uses batched
        queries with GROUP BY class_id.

        Args:
            class_ids: List of class UUIDs to fetch summaries for.
            school_id: Multi-tenancy guard - only returns classes belonging to this school.

        Returns:
            Dict mapping class_id to ClassSummary (missing classes not included).
        """
        if not class_ids:
            return {}

        classes_result = await self.db.execute(
            select(Class.id).where(
                Class.id.in_(class_ids),
                Class.school_id == school_id,
            )
        )
        valid_class_ids = [row for row in classes_result.scalars().all()]

        if not valid_class_ids:
            return {}

        gap_agg = (
            select(
                GapState.class_id,
                func.avg(GapState.mastery_score).label("avg_mastery"),
                func.count(func.distinct(GapState.student_id)).label("assessed_students"),
                func.max(GapState.last_assessed_at).label("last_updated"),
            )
            .where(GapState.class_id.in_(valid_class_ids))
            .group_by(GapState.class_id)
        )
        gap_results = {row.class_id: row for row in (await self.db.execute(gap_agg)).all()}

        enroll_counts_query = (
            select(
                ClassEnrollment.class_id,
                func.count(ClassEnrollment.student_id).label("count"),
            )
            .where(
                ClassEnrollment.class_id.in_(valid_class_ids),
                ClassEnrollment.is_active.is_(True),
            )
            .group_by(ClassEnrollment.class_id)
        )
        enroll_results = {row.class_id: row.count for row in (await self.db.execute(enroll_counts_query)).all()}

        student_avgs = (
            select(
                GapState.class_id,
                GapState.student_id,
                func.avg(GapState.mastery_score).label("student_avg"),
            )
            .where(GapState.class_id.in_(valid_class_ids))
            .group_by(GapState.class_id, GapState.student_id)
            .subquery()
        )
        below_counts_query = (
            select(
                student_avgs.c.class_id,
                func.count(student_avgs.c.student_id).label("below_count"),
            )
            .where(student_avgs.c.student_avg < 0.4)
            .group_by(student_avgs.c.class_id)
        )
        below_results = {row.class_id: row.below_count for row in (await self.db.execute(below_counts_query)).all()}

        results = {}
        for class_id in valid_class_ids:
            row = gap_results.get(class_id)
            results[class_id] = ClassSummary(
                class_id=class_id,
                avg_mastery=float(row.avg_mastery) if row and row.avg_mastery is not None else None,
                student_count=enroll_results.get(class_id, 0),
                assessed_student_count=row.assessed_students if row and row.assessed_students else 0,
                students_below_threshold=below_results.get(class_id, 0),
                last_updated_at=row.last_updated if row else None,
            )

        return results
