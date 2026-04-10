"""Gap state calculation Celery task.

M1-4-T3: Computes per-subtopic recency-weighted mastery after each attempt is COMPLETED
and upserts gap_states rows via GapService.
"""

import asyncio
import uuid as _uuid
from collections import defaultdict
from datetime import UTC

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


def _parse_uuid(value: str, param_name: str) -> _uuid.UUID:
    """Parse a string as UUID and raise ValueError if invalid."""
    try:
        return _uuid.UUID(value)
    except ValueError:
        raise ValueError(f"Invalid UUID for {param_name}: {value}")


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name="app.tasks.gap_tasks.calculate_gap_states",
)
def calculate_gap_states(self, attempt_id: str) -> dict[str, object]:
    """Calculate and persist per-subtopic gap states after an attempt is COMPLETED.

    Step-by-step:
    1. Load attempt, verify status == "COMPLETED". If not, log WARNING and return early.
    2. Load all StudentResponse rows for this attempt.
    3. Load QuestionBank rows for those question_ids. Map question_id → subtopic_id.
    4. Group responses by subtopic, compute per-subtopic attempt score (correct / total).
    5. Load last 2 historical scores from student_attempt_subtopic_scores (ordered by
       attempted_at DESC, limit 2).
    6. Compute recency-weighted mastery:
       - 1 attempt (enrollment diagnostic): score × 0.7 if is_system_generated else score × 1.0
       - 2 attempts: (recent × 0.65) + (older × 0.35)
       - 3+ attempts: (most_recent × 0.5) + (second × 0.3) + (third × 0.2)
       - Clamp to [0.0, 1.0]
    7. Call GapService.upsert_gap_state(...) for each subtopic.
    8. Insert StudentAttemptSubtopicScore row per subtopic (ON CONFLICT DO NOTHING).
    9. Commit. Return {"attempt_id": attempt_id, "subtopics_updated": count}.

    Args:
        attempt_id: The StudentAttempt UUID as string.

    Returns:
        Dict with attempt_id and subtopics_updated count.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings

    logger.info("calculate_gap_states_started", attempt_id=attempt_id)

    try:
        attempt_uuid = _parse_uuid(attempt_id, "attempt_id")
    except ValueError as exc:
        logger.error("invalid_attempt_id_uuid", attempt_id=attempt_id, error=str(exc))
        raise

    async def _run() -> dict[str, object]:
        from datetime import datetime

        from sqlalchemy import select, text

        from app.models.assessment import (
            Assessment,
            AttemptStatus,
            StudentAttempt,
            StudentResponse,
        )
        from app.models.curriculum import QuestionBank
        from app.services.gap_service import GapService

        engine = create_async_engine(settings.database_url, echo=False)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as db:
            async with db.begin():
                # ── Step 1: Load attempt, verify COMPLETED ──────────────────
                attempt_result = await db.execute(select(StudentAttempt).where(StudentAttempt.id == attempt_uuid))
                attempt: StudentAttempt | None = attempt_result.scalar_one_or_none()

                if attempt is None:
                    logger.warning(
                        "calculate_gap_states_skipped_attempt_not_found",
                        attempt_id=attempt_id,
                    )
                    return {"attempt_id": attempt_id, "subtopics_updated": 0}

                if attempt.status != AttemptStatus.COMPLETED:
                    logger.warning(
                        "calculate_gap_states_skipped_attempt_not_completed",
                        attempt_id=attempt_id,
                        status=attempt.status,
                    )
                    return {"attempt_id": attempt_id, "subtopics_updated": 0}

                # ── Step 2: Load assessment (for is_system_generated + school_id + class_id) ─
                assessment_result = await db.execute(select(Assessment).where(Assessment.id == attempt.assessment_id))
                assessment: Assessment | None = assessment_result.scalar_one_or_none()
                if assessment is None:
                    logger.warning(
                        "calculate_gap_states_skipped_assessment_not_found",
                        attempt_id=attempt_id,
                        assessment_id=str(attempt.assessment_id),
                    )
                    return {"attempt_id": attempt_id, "subtopics_updated": 0}

                is_system_generated: bool = assessment.is_system_generated

                # ── Step 3: Load responses ───────────────────────────────────
                responses_result = await db.execute(
                    select(StudentResponse).where(StudentResponse.attempt_id == attempt_uuid)
                )
                responses: list[StudentResponse] = list(responses_result.scalars().all())

                if not responses:
                    logger.warning(
                        "calculate_gap_states_skipped_no_responses",
                        attempt_id=attempt_id,
                    )
                    return {"attempt_id": attempt_id, "subtopics_updated": 0}

                # ── Step 4: Map question_id → subtopic_id ────────────────────
                question_ids = [r.question_id for r in responses]
                q_result = await db.execute(
                    select(QuestionBank.id, QuestionBank.subtopic_id).where(QuestionBank.id.in_(question_ids))
                )
                question_to_subtopic: dict[_uuid.UUID, _uuid.UUID] = {row[0]: row[1] for row in q_result.all()}

                # ── Step 5: Group responses by subtopic, compute per-subtopic score ──
                subtopic_correct: dict[_uuid.UUID, int] = defaultdict(int)
                subtopic_total: dict[_uuid.UUID, int] = defaultdict(int)

                for response in responses:
                    subtopic_id = question_to_subtopic.get(response.question_id)
                    if subtopic_id is None:
                        logger.warning(
                            "calculate_gap_states_unknown_question_skipped",
                            question_id=str(response.question_id),
                            attempt_id=attempt_id,
                        )
                        continue
                    subtopic_total[subtopic_id] += 1
                    if response.is_correct:
                        subtopic_correct[subtopic_id] += 1

                # ── Step 6: Compute recency-weighted mastery per subtopic ────
                gap_service = GapService(db)
                assessed_at = attempt.completed_at or datetime.now(UTC)
                subtopics_updated = 0

                for subtopic_id, total in subtopic_total.items():
                    if total == 0:
                        continue

                    current_score = subtopic_correct[subtopic_id] / total

                    # Load last 2 historical scores (excluding this attempt)
                    hist_result = await db.execute(
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
                            "subtopic_id": subtopic_id,
                            "attempt_id": attempt_uuid,
                        },
                    )
                    historical = hist_result.all()  # [(score, attempted_at), ...]

                    if len(historical) == 0:
                        # First attempt
                        if is_system_generated:
                            mastery = current_score * 0.7
                        else:
                            mastery = current_score * 1.0
                        rolling_count = 1
                    elif len(historical) == 1:
                        # Second attempt (1 historical + current)
                        older_score = historical[0][0]
                        mastery = (current_score * 0.65) + (older_score * 0.35)
                        rolling_count = 2
                    else:
                        # Third or more (2 historical + current = 3+)
                        second_score = historical[0][0]  # most recent historical
                        third_score = historical[1][0]  # older historical
                        mastery = (current_score * 0.5) + (second_score * 0.3) + (third_score * 0.2)
                        rolling_count = len(historical) + 1

                    # Clamp to [0.0, 1.0]
                    mastery = max(0.0, min(1.0, mastery))

                    # ── Step 7: Upsert gap_state ──────────────────────────────
                    await gap_service.upsert_gap_state(
                        student_id=attempt.student_id,
                        subtopic_id=subtopic_id,
                        school_id=assessment.school_id,
                        class_id=assessment.class_id,
                        new_mastery=mastery,
                        rolling_attempt_count=rolling_count,
                        last_assessed_at=assessed_at,
                    )

                    # ── Step 8: Insert subtopic score row (idempotent) ────────
                    await db.execute(
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
                            "subtopic_id": subtopic_id,
                            "attempt_id": attempt_uuid,
                            "score": current_score,
                            "attempted_at": assessed_at,
                        },
                    )

                    subtopics_updated += 1

                return {"attempt_id": attempt_id, "subtopics_updated": subtopics_updated}

    try:
        loop = asyncio.new_event_loop()
        try:
            run_result = loop.run_until_complete(_run())
        finally:
            loop.close()

        logger.info(
            "calculate_gap_states_completed",
            attempt_id=attempt_id,
            subtopics_updated=run_result["subtopics_updated"],
        )
        return run_result

    except Exception as exc:
        logger.error(
            "calculate_gap_states_failed",
            attempt_id=attempt_id,
            error=str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc)

    def on_failure(self, exc, task_id, args, kwargs, einfo) -> None:
        """Called by Celery when all retries are exhausted.

        Emits a CRITICAL structured log event so the operations team is alerted.
        Per CONSTITUTION Rule 18.
        """
        logger.critical(
            "calculate_gap_states_permanently_failed",
            task_id=task_id,
            attempt_id=args[0] if args else kwargs.get("attempt_id"),
            error=str(exc),
            exc_info=True,
        )
