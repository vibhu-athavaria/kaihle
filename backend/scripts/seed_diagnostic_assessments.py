"""Seed Tier 1 diagnostic assessments for Future School classes.

Creates and publishes a diagnostic for every class that does not already have one.
Topic selection follows the 80/20 rule:
  - 80 % of topics from the previous grade (grade N-1), same subject
  - 20 % of topics from the current grade (grade N), same subject
  - When the same subject does not exist at the previous grade
    (e.g., Chemistry at grade 9 ← Integrated Science at grade 8),
    the script falls back to Integrated Science (SCI) at grade N-1.
  - When no previous-grade topics are found at all (e.g., grade 6 with
    no grade 5 SCI/MATH/ENG data), 100 % current-grade topics are used.

Idempotent: classes that already have a DIAGNOSTIC assessment (any status)
are skipped entirely.

Usage (from project root):
    cd backend
    DATABASE_URL=postgresql+asyncpg://kaihle:kaihle@localhost:5433/kaihle \\
        uv run python -m scripts.seed_diagnostic_assessments
"""

import asyncio
import math
import random
import sys
import uuid
from pathlib import Path

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.models.assessment import Assessment, AssessmentType  # noqa: E402
from app.models.curriculum import CurriculumTopic, Grade, Subject  # noqa: E402
from app.models.school import Class  # noqa: E402
from app.schemas.assessments import DesignTier1DiagnosticRequest  # noqa: E402
from app.services.assessment_service import AssessmentService  # noqa: E402

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

# When a subject doesn't exist at the previous grade, fall back to these subjects
# (in order of preference). This handles PHY/CHEM/BIO at grade 9 ← SCI at grade 8.
SUBJECT_PREV_GRADE_FALLBACKS: dict[str, list[str]] = {
    "PHY": ["PHY", "SCI"],
    "CHEM": ["CHEM", "SCI"],
    "BIO": ["BIO", "SCI"],
    "ENGL": ["ENGL", "ENG"],  # English Literature ← English Language if needed
}


def get_database_url() -> str:
    db_url = settings.database_url
    if not db_url:
        db_url = "postgresql+asyncpg://kaihle:kaihle@postgres:5432/kaihle"
    return db_url


def _compute_80_20_split(
    prev_topic_ids: list[uuid.UUID],
    curr_topic_ids: list[uuid.UUID],
    rng: random.Random,
) -> list[uuid.UUID]:
    """Return topic IDs with 80 % from prev grade, 20 % from current grade.

    Strategy:
    - Take ALL available previous-grade topics (these form the 80 % pool).
    - Derive current-grade count as ceil(n_prev × 0.25); cap to available.
      (0.25 = 20 / 80 — keeps the ratio at 80:20 regardless of pool size.)
    - If no previous-grade topics, fall back to 100 % current-grade topics.
    """
    if not prev_topic_ids:
        log.warning("no_prev_grade_topics_found_using_all_current")
        return list(curr_topic_ids)

    n_prev = len(prev_topic_ids)
    n_curr_target = max(1, math.ceil(n_prev * 0.25))
    n_curr_take = min(n_curr_target, len(curr_topic_ids))

    selected_curr = rng.sample(curr_topic_ids, n_curr_take) if n_curr_take else []

    total = n_prev + n_curr_take
    pct_prev = round(100 * n_prev / total) if total else 0
    log.info(
        "topic_split",
        prev_topics=n_prev,
        curr_topics=n_curr_take,
        approx_split=f"{pct_prev}%/{100 - pct_prev}%",
    )
    return list(prev_topic_ids) + selected_curr


async def get_curriculum_topic_ids(
    db: AsyncSession,
    subject_codes: list[str],
    grade_level: int,
) -> list[uuid.UUID]:
    """Fetch CurriculumTopic IDs for the first subject_code that has topics."""
    grade_id_row = (await db.execute(select(Grade.id).where(Grade.level == grade_level))).scalar_one_or_none()
    if grade_id_row is None:
        return []

    for code in subject_codes:
        subject_id_row = (await db.execute(select(Subject.id).where(Subject.code == code))).scalar_one_or_none()
        if subject_id_row is None:
            continue

        rows = (
            (
                await db.execute(
                    select(CurriculumTopic.id).where(
                        CurriculumTopic.grade_id == grade_id_row,
                        CurriculumTopic.subject_id == subject_id_row,
                    )
                )
            )
            .scalars()
            .all()
        )
        if rows:
            log.debug("topics_found", subject=code, grade=grade_level, count=len(rows))
            return list(rows)

    return []


async def seed_diagnostics() -> None:
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

        # ── Find classes with NO diagnostic ───────────────────────────────
        classes_with_diag_subq = (
            select(Assessment.class_id).where(Assessment.assessment_type == AssessmentType.DIAGNOSTIC).scalar_subquery()
        )
        target_classes = (
            (
                await db.execute(
                    select(Class).where(
                        Class.school_id == school_id,
                        Class.id.not_in(classes_with_diag_subq),
                        Class.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )

        log.info("classes_needing_diagnostics", count=len(target_classes))
        if not target_classes:
            log.info("nothing_to_do")
            return

        # ── Pre-load subject codes for all classes ────────────────────────
        subject_ids = {c.subject_id for c in target_classes}
        subject_rows = (await db.execute(select(Subject).where(Subject.id.in_(subject_ids)))).scalars().all()
        subject_code_by_id: dict[uuid.UUID, str] = {s.id: s.code for s in subject_rows}

        # ── Pre-load grade levels for all classes ─────────────────────────
        grade_ids = {c.grade_id for c in target_classes}
        grade_rows = (await db.execute(select(Grade).where(Grade.id.in_(grade_ids)))).scalars().all()
        grade_level_by_id: dict[uuid.UUID, int] = {g.id: g.level for g in grade_rows}

        # ── Create diagnostic for each class ──────────────────────────────
        service = AssessmentService(db)
        rng = random.Random(42)  # noqa: S311 — deterministic seed for reproducibility

        created = 0
        skipped = 0

        for cls in target_classes:
            subject_code = subject_code_by_id.get(cls.subject_id)
            grade_level = grade_level_by_id.get(cls.grade_id)

            if subject_code is None or grade_level is None:
                log.warning("missing_subject_or_grade", class_id=str(cls.id), class_name=cls.name)
                skipped += 1
                continue

            log.info(
                "processing_class",
                class_name=cls.name,
                subject=subject_code,
                grade=grade_level,
            )

            # ── Select topics: current grade ──────────────────────────────
            curr_subject_codes = [subject_code]
            curr_topic_ids = await get_curriculum_topic_ids(db, curr_subject_codes, grade_level)

            if not curr_topic_ids:
                log.warning(
                    "no_current_grade_topics_skipping",
                    class_name=cls.name,
                    subject=subject_code,
                    grade=grade_level,
                )
                skipped += 1
                continue

            # ── Select topics: previous grade (with subject fallback) ─────
            prev_grade_level = grade_level - 1
            prev_subject_codes = SUBJECT_PREV_GRADE_FALLBACKS.get(subject_code, [subject_code])
            prev_topic_ids = await get_curriculum_topic_ids(db, prev_subject_codes, prev_grade_level)

            # ── Compute 80/20 split ───────────────────────────────────────
            selected_topic_ids = _compute_80_20_split(prev_topic_ids, curr_topic_ids, rng)

            if not selected_topic_ids:
                log.warning("no_topics_selected_skipping", class_name=cls.name)
                skipped += 1
                continue

            # ── Build the request ─────────────────────────────────────────
            body = DesignTier1DiagnosticRequest(
                topic_ids=selected_topic_ids,
                questions_per_topic=5,  # default per Vidhya rule (min 3, default 5)
                minimum_difficulty=1,
                maximum_difficulty=5,
                question_types=["MCQ", "TRUE_FALSE"],
                time_limit_minutes=None,
                deadline=None,
            )

            # Capture name before the try block — avoids lazy-load after rollback
            class_name = cls.name

            try:
                assessment = await service.design_tier1_diagnostic(
                    class_id=cls.id,
                    school_id=school_id,
                    teacher_id=cls.teacher_id,
                    body=body,
                )
                await db.flush()

                # ── Publish immediately so students can take it ───────────
                published = await service.publish_assessment(
                    assessment_id=assessment.id,
                    school_id=school_id,
                    teacher_id=cls.teacher_id,
                    deadline=None,
                )
                await db.commit()

                log.info(
                    "diagnostic_created_and_published",
                    class_name=class_name,
                    assessment_id=str(published.id),
                    question_pool=published.question_count,
                    topics=len(selected_topic_ids),
                    prev_grade_topics=len(prev_topic_ids),
                    curr_grade_topics=len(selected_topic_ids) - len(prev_topic_ids),
                )
                created += 1

            except Exception as exc:
                await db.rollback()
                log.error(
                    "diagnostic_creation_failed",
                    class_name=class_name,
                    subject=subject_code,
                    grade=grade_level,
                    error=str(exc),
                )
                skipped += 1

        log.info("seed_diagnostics_complete", created=created, skipped=skipped)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_diagnostics())
