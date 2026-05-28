"""Seed completed diagnostic attempts for all Future School students.

For every student enrolled in a class that has a published DIAGNOSTIC assessment,
creates a completed attempt with randomly distributed mastery results.

Mastery tier distribution (per student, applied uniformly across their subtopics
with ±noise so no two students have identical scores):
  - ~34% of students: Needs Work  (target score band 0.10–0.38)
  - ~33% of students: Developing  (target score band 0.40–0.69)
  - ~33% of students: Strong      (target score band 0.72–0.95)

Writes directly to four tables (bypassing Celery — safe for seeding):
  student_attempts, student_responses,
  student_attempt_subtopic_scores, gap_states

Also updates class_enrollments.onboarding_diagnostic_status → COMPLETED.

Idempotent: students who already have a COMPLETED attempt for a class's
diagnostic assessment are skipped.

Usage (from project root):
    cd backend
    DATABASE_URL=postgresql+asyncpg://kaihle:kaihle@localhost:5433/kaihle \\
        uv run python -m scripts.seed_diagnostic_attempts
"""

import asyncio
import random
import sys
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import structlog
from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.models.assessment import (  # noqa: E402
    Assessment,
    AssessmentSelectedQuestion,
    AssessmentType,
    AttemptStatus,
    ScoredBy,
    StudentAttempt,
    StudentAttemptSubtopicScore,
    StudentResponse,
)
from app.models.curriculum import QuestionBank  # noqa: E402
from app.models.gap import GapState  # noqa: E402
from app.models.school import Class, ClassEnrollment  # noqa: E402

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
log = structlog.get_logger()

SCHOOL_SLUG = "future-school-bali"

# Mastery tier definitions: (label, score_min, score_max, weight)
# Weights determine how many students fall into each tier.
MASTERY_TIERS = [
    ("needs_work", 0.10, 0.38, 34),
    ("developing", 0.40, 0.69, 33),
    ("strong", 0.72, 0.95, 33),
]


def get_database_url() -> str:
    db_url = settings.database_url
    if not db_url:
        db_url = "postgresql+asyncpg://kaihle:kaihle@postgres:5432/kaihle"
    return db_url


def _assign_tier(student_index: int, rng: random.Random) -> tuple[float, float]:
    """Return (score_min, score_max) for a student based on their index.

    The population cycles through tiers in proportion to their weights,
    with a small random shuffle so the distribution isn't perfectly ordered.
    """
    # Build tier pool (34 needs_work, 33 developing, 33 strong per 100 students)
    pool: list[tuple[float, float]] = []
    for _, lo, hi, weight in MASTERY_TIERS:
        pool.extend([(lo, hi)] * weight)
    # Deterministic shuffle per student index so re-runs are reproducible
    pool_rng = random.Random(student_index)
    pool_rng.shuffle(pool)
    return pool[student_index % len(pool)]


def _student_base_score(student_seed: int, rng: random.Random) -> float:
    """Pick a base mastery score for a student drawn from their assigned tier."""
    lo, hi = _assign_tier(student_seed, rng)
    return lo + rng.random() * (hi - lo)


def _subtopic_score(base: float, rng: random.Random) -> float:
    """Vary the base score per subtopic with ±0.12 noise, clamped to [0.05, 0.98]."""
    noise = rng.uniform(-0.12, 0.12)
    return max(0.05, min(0.98, base + noise))


def _simulate_responses(
    questions: list[tuple[uuid.UUID, str, uuid.UUID]],  # (question_id, correct_answer, subtopic_id)
    base_score: float,
    rng: random.Random,
) -> list[dict]:
    """Return a list of response dicts, each question answered with realistic correctness."""
    responses = []
    for q_id, correct_answer, subtopic_id in questions:
        # Probability of getting this question right ≈ subtopic score
        s_score = _subtopic_score(base_score, rng)
        is_correct = rng.random() < s_score
        responses.append(
            {
                "question_id": q_id,
                "subtopic_id": subtopic_id,
                "answer_given": correct_answer if is_correct else _wrong_answer(correct_answer, rng),
                "is_correct": is_correct,
                "score": 1.0 if is_correct else 0.0,
            }
        )
    return responses


def _wrong_answer(correct: str, rng: random.Random) -> str:
    """Return a plausible wrong answer string."""
    if correct.lower() in ("true", "false"):
        return "false" if correct.lower() == "true" else "true"
    # MCQ: pick a different letter
    options = ["A", "B", "C", "D"]
    wrong = [o for o in options if o != correct.upper()]
    return rng.choice(wrong) if wrong else "A"


async def seed_attempts() -> None:
    db_url = get_database_url()
    log.info("connecting_to_database", url=db_url.replace("//", "//***:***@"))

    engine = create_async_engine(db_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # ── Resolve school ────────────────────────────────────────────────
        school_id: uuid.UUID = (
            await db.execute(text("SELECT id FROM schools WHERE slug = :slug"), {"slug": SCHOOL_SLUG})
        ).scalar_one()
        log.info("school_resolved", school_id=str(school_id))

        # ── Find all ACTIVE DIAGNOSTIC assessments for this school ────────
        diagnostics = (
            (
                await db.execute(
                    select(Assessment)
                    .join(Class, Class.id == Assessment.class_id)
                    .where(
                        Class.school_id == school_id,
                        Assessment.assessment_type == AssessmentType.DIAGNOSTIC,
                        Assessment.status == "ACTIVE",
                    )
                )
            )
            .scalars()
            .all()
        )

        log.info("active_diagnostics_found", count=len(diagnostics))
        if not diagnostics:
            log.warning("no_active_diagnostics — run seed_diagnostic_assessments.py first")
            return

        # ── Pre-load all assessment questions (question_id, correct_answer, subtopic_id)
        assessment_ids = [a.id for a in diagnostics]
        q_rows = (
            await db.execute(
                select(
                    AssessmentSelectedQuestion.assessment_id,
                    AssessmentSelectedQuestion.question_id,
                    QuestionBank.correct_answer,
                    QuestionBank.subtopic_id,
                )
                .join(QuestionBank, QuestionBank.id == AssessmentSelectedQuestion.question_id)
                .where(AssessmentSelectedQuestion.assessment_id.in_(assessment_ids))
            )
        ).all()

        # Group: assessment_id → list[(question_id, correct_answer, subtopic_id)]
        questions_by_assessment: dict[uuid.UUID, list[tuple[uuid.UUID, str, uuid.UUID]]] = defaultdict(list)
        for row in q_rows:
            questions_by_assessment[row.assessment_id].append((row.question_id, row.correct_answer, row.subtopic_id))

        log.info(
            "questions_loaded",
            total=len(q_rows),
            assessments_with_questions=len(questions_by_assessment),
        )

        # ── Pre-load enrollments: who is enrolled in each class ───────────
        class_ids = [a.class_id for a in diagnostics]
        enrollments = (
            (
                await db.execute(
                    select(ClassEnrollment).where(
                        ClassEnrollment.class_id.in_(class_ids),
                        ClassEnrollment.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )

        # enrollment_map: class_id → [student_id, ...]
        enrollment_map: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for e in enrollments:
            enrollment_map[e.class_id].append(e.student_id)

        # ── Pre-load ALL existing attempts (any status) to skip them ─────
        # sa_unique constrains (assessment_id, student_id) regardless of status.
        existing_attempts = (
            await db.execute(
                select(StudentAttempt.assessment_id, StudentAttempt.student_id).where(
                    StudentAttempt.assessment_id.in_(assessment_ids)
                )
            )
        ).all()
        existing_set: set[tuple[uuid.UUID, uuid.UUID]] = {
            (row.assessment_id, row.student_id) for row in existing_attempts
        }
        log.info("existing_attempts_found", count=len(existing_set))

        # ── Seed attempts ─────────────────────────────────────────────────
        rng = random.Random(1337)  # deterministic — noqa: S311
        now = datetime.now(UTC)

        created = skipped = 0

        for assessment in diagnostics:
            questions = questions_by_assessment.get(assessment.id, [])
            if not questions:
                log.warning("no_questions_for_assessment", assessment_id=str(assessment.id))
                continue

            students = enrollment_map.get(assessment.class_id, [])
            if not students:
                log.warning("no_enrollments_for_class", class_id=str(assessment.class_id))
                continue

            log.info(
                "processing_assessment",
                assessment_id=str(assessment.id),
                class_id=str(assessment.class_id),
                questions=len(questions),
                students=len(students),
            )

            for student_index, student_id in enumerate(students):
                if (assessment.id, student_id) in existing_set:
                    skipped += 1
                    continue

                # Assign a stable base mastery score for this student
                base_score = _student_base_score(student_index, rng)

                # Simulate answers
                responses = _simulate_responses(questions, base_score, rng)

                correct_count = sum(1 for r in responses if r["is_correct"])
                overall_score = correct_count / len(responses) if responses else 0.0

                # ── student_attempts ──────────────────────────────────────
                attempt_id = uuid.uuid4()
                attempt_start = now.replace(minute=rng.randint(0, 59), second=rng.randint(0, 59))
                time_taken = rng.randint(900, 3600)  # 15–60 minutes

                db.add(
                    StudentAttempt(
                        id=attempt_id,
                        assessment_id=assessment.id,
                        student_id=student_id,
                        status=AttemptStatus.COMPLETED,
                        total_questions=len(questions),
                        questions_answered=len(responses),
                        overall_score=round(overall_score, 4),
                        time_taken_seconds=time_taken,
                        started_at=attempt_start,
                        completed_at=attempt_start,
                    )
                )

                # ── student_responses ─────────────────────────────────────
                for resp in responses:
                    db.add(
                        StudentResponse(
                            id=uuid.uuid4(),
                            attempt_id=attempt_id,
                            question_id=resp["question_id"],
                            answer_given=resp["answer_given"],
                            is_correct=resp["is_correct"],
                            score=resp["score"],
                            scored_by=ScoredBy.RULE,
                            ai_feedback=None,
                            hints_used=0,
                            time_taken_ms=rng.randint(10_000, 120_000),
                        )
                    )

                # ── Aggregate per-subtopic ────────────────────────────────
                subtopic_correct: dict[uuid.UUID, int] = defaultdict(int)
                subtopic_total: dict[uuid.UUID, int] = defaultdict(int)
                for resp in responses:
                    sid = resp["subtopic_id"]
                    subtopic_total[sid] += 1
                    if resp["is_correct"]:
                        subtopic_correct[sid] += 1

                # ── student_attempt_subtopic_scores ───────────────────────
                for subtopic_id, total in subtopic_total.items():
                    frac_correct = subtopic_correct[subtopic_id] / total if total else 0.0
                    db.add(
                        StudentAttemptSubtopicScore(
                            id=uuid.uuid4(),
                            student_id=student_id,
                            subtopic_id=subtopic_id,
                            attempt_id=attempt_id,
                            score=round(frac_correct, 4),
                            attempted_at=attempt_start,
                        )
                    )

                # ── gap_states (upsert) ───────────────────────────────────
                # gap_states.last_assessed_at is TIMESTAMP WITHOUT TIME ZONE
                attempt_start_naive = attempt_start.replace(tzinfo=None)
                for subtopic_id, total in subtopic_total.items():
                    correct = subtopic_correct[subtopic_id]
                    frac_correct = correct / total if total else 0.0
                    confidence = min(1.0, total / 5.0)  # reaches 1.0 after 5 questions

                    stmt = (
                        pg_insert(GapState)
                        .values(
                            id=uuid.uuid4(),
                            student_id=student_id,
                            subtopic_id=subtopic_id,
                            class_id=assessment.class_id,
                            mastery_score=round(frac_correct, 4),
                            confidence=round(confidence, 4),
                            attempt_count=1,
                            total_correct=correct,
                            total_attempted=total,
                            needs_review=(frac_correct < 0.4),
                            last_assessed_at=attempt_start_naive,
                        )
                        .on_conflict_do_update(
                            constraint="gap_states_unique",
                            set_={
                                "mastery_score": round(frac_correct, 4),
                                "confidence": round(confidence, 4),
                                "attempt_count": GapState.attempt_count + 1,
                                "total_correct": GapState.total_correct + correct,
                                "total_attempted": GapState.total_attempted + total,
                                "needs_review": frac_correct < 0.4,
                                "last_assessed_at": attempt_start_naive,
                                "updated_at": now,
                            },
                        )
                    )
                    await db.execute(stmt)

                # ── Mark enrollment diagnostic as COMPLETED ───────────────
                await db.execute(
                    update(ClassEnrollment)
                    .where(
                        ClassEnrollment.class_id == assessment.class_id,
                        ClassEnrollment.student_id == student_id,
                    )
                    .values(onboarding_diagnostic_status="COMPLETED")
                )

                await db.flush()
                created += 1

        await db.commit()
        log.info(
            "seed_attempts_complete",
            created=created,
            skipped=skipped,
            tier_distribution="~34% needs_work / ~33% developing / ~33% strong",
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_attempts())
