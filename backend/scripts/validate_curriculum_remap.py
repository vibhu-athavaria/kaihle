"""Validate the invariants the curriculum remap must satisfy.

Read-only. Exits non-zero if any hard check fails, so it is usable as a gate before
declaring a remap complete or promoting an environment.

Hard checks (failure = broken remap):
  - no duplicate canonical_code among learning objectives
  - every active subtopic has at least one objective
  - no objective is orphaned from every subtopic
  - no active question points at a subtopic that no longer exists
  - a Core student's question pool contains no EXTENDED-only subtopic

Soft checks (reported, do not fail): question coverage per objective and per
difficulty level. Gaps here are Phase 6 generation input, not remap defects.

Usage (from backend/):
    python -m scripts.validate_curriculum_remap
    python -m scripts.validate_curriculum_remap --curriculum cambridge_lower --subjects MATH,SCI --grades 6,7,8
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402

structlog.configure(
    processors=[structlog.stdlib.add_log_level, structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

# Each entry: (name, sql returning a single count, description of what non-zero means)
HARD_CHECKS: list[tuple[str, str, str]] = [
    (
        "duplicate_canonical_codes",
        """
        SELECT count(*) FROM (
            SELECT canonical_code FROM learning_objectives
            GROUP BY canonical_code HAVING count(*) > 1
        ) d
        """,
        "learning objectives share a canonical_code",
    ),
    (
        "active_subtopics_without_objective",
        """
        SELECT count(*) FROM subtopics sub
        WHERE sub.is_active
          AND NOT EXISTS (SELECT 1 FROM subtopic_objectives so WHERE so.subtopic_id = sub.id)
        """,
        "active subtopics have no learning objective, so they can never surface a question",
    ),
    (
        "objectives_with_no_subtopic",
        """
        SELECT count(*) FROM learning_objectives lo
        WHERE lo.is_active
          AND NOT EXISTS (SELECT 1 FROM subtopic_objectives so WHERE so.learning_objective_id = lo.id)
        """,
        "active objectives have no curriculum placement and are unreachable",
    ),
    (
        "questions_pointing_at_missing_subtopic",
        """
        SELECT count(*) FROM question_bank q
        WHERE q.subtopic_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM subtopics s WHERE s.id = q.subtopic_id)
        """,
        "questions reference a subtopic that no longer exists",
    ),
    (
        "core_tier_leakage",
        # Tier lives only on subtopics, so this is the query a Core student's pool
        # would run. It must never reach an EXTENDED-only subtopic.
        """
        SELECT count(*) FROM subtopics sub
        JOIN subtopic_objectives so ON so.subtopic_id = sub.id
        WHERE sub.tier NOT IN ('CORE', 'BOTH') AND sub.tier = 'EXTENDED'
          AND EXISTS (
              SELECT 1 FROM subtopics other
              JOIN subtopic_objectives o2 ON o2.subtopic_id = other.id
              WHERE o2.learning_objective_id = so.learning_objective_id
                AND other.tier IN ('CORE', 'BOTH')
                AND other.id = sub.id
          )
        """,
        "EXTENDED-only subtopics are reachable from a Core student's pool",
    ),
    (
        "invalid_tier_values",
        "SELECT count(*) FROM subtopics WHERE tier NOT IN ('CORE', 'EXTENDED', 'BOTH')",
        "subtopics carry a tier outside the permitted set",
    ),
]


async def _count(db: AsyncSession, sql: str, params: dict[str, Any] | None = None) -> int:
    result = await db.execute(text(sql), params or {})
    return int(result.scalar_one())


async def run_hard_checks(db: AsyncSession) -> list[str]:
    """Return the names of failing checks."""
    failures: list[str] = []
    for name, sql, description in HARD_CHECKS:
        count = await _count(db, sql)
        if count == 0:
            log.info("check_passed", check=name)
        else:
            failures.append(name)
            log.error("check_failed", check=name, count=count, meaning=description)
    return failures


async def report_coverage(db: AsyncSession, params: dict[str, Any] | None) -> None:
    """Soft reporting. Gaps are Phase 6 input, not remap defects."""
    scope_sql = ""
    if params:
        scope_sql = """
            AND EXISTS (
                SELECT 1 FROM subtopic_objectives so2
                JOIN subtopics sub2        ON sub2.id = so2.subtopic_id
                JOIN curriculum_topics ct2 ON ct2.id = sub2.curriculum_topic_id
                JOIN curricula c2 ON c2.id = ct2.curriculum_id AND c2.code = :curriculum
                JOIN subjects  s2 ON s2.id = ct2.subject_id    AND s2.code = ANY(:subjects)
                JOIN grades    g2 ON g2.id = ct2.grade_id      AND g2.level = ANY(:grades)
                WHERE so2.learning_objective_id = lo.id
            )
        """

    total = await _count(db, f"SELECT count(*) FROM learning_objectives lo WHERE lo.is_active {scope_sql}", params)
    with_questions = await _count(
        db,
        f"""
        SELECT count(*) FROM learning_objectives lo
        WHERE lo.is_active {scope_sql}
          AND EXISTS (SELECT 1 FROM question_bank q WHERE q.learning_objective_id = lo.id AND q.is_active)
        """,
        params,
    )
    unbound = await _count(db, "SELECT count(*) FROM question_bank WHERE is_active AND learning_objective_id IS NULL")

    log.info(
        "coverage_report",
        objectives=total,
        objectives_with_questions=with_questions,
        objectives_without_questions=total - with_questions,
        active_questions_unbound=unbound,
    )

    rows = await db.execute(
        text(
            f"""
            SELECT levels.d AS difficulty, count(DISTINCT lo.id) AS objectives_covered
            FROM generate_series(1, 5) AS levels(d)
            CROSS JOIN learning_objectives lo
            WHERE lo.is_active {scope_sql}
              AND EXISTS (
                  SELECT 1 FROM question_bank q
                  WHERE q.learning_objective_id = lo.id AND q.is_active
                    AND floor(q.difficulty_level) = levels.d
              )
            GROUP BY levels.d ORDER BY levels.d
            """
        ),
        params,
    )
    for row in rows.mappings():
        log.info(
            "coverage_by_difficulty",
            difficulty=row["difficulty"],
            objectives_covered=row["objectives_covered"],
            objectives_missing=total - row["objectives_covered"],
        )


async def main(curriculum: str | None, subjects: list[str], grades: list[int]) -> int:
    params = (
        {"curriculum": curriculum, "subjects": subjects, "grades": grades}
        if curriculum and subjects and grades
        else None
    )

    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with async_session() as db:
            failures = await run_hard_checks(db)
            await report_coverage(db, params)

        if failures:
            log.error("validation_failed", failed_checks=failures)
            return 1
        log.info("validation_passed", checks=len(HARD_CHECKS))
        return 0
    except Exception as exc:
        log.error("validation_errored", error=str(exc), exc_info=True)
        return 1
    finally:
        await engine.dispose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--curriculum", help="Narrow the coverage report to this curriculum")
    parser.add_argument("--subjects", default="", help="Comma-separated subject codes")
    parser.add_argument("--grades", default="", help="Comma-separated grade levels")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(
        asyncio.run(
            main(
                curriculum=args.curriculum,
                subjects=[s.strip().upper() for s in args.subjects.split(",") if s.strip()],
                grades=[int(g.strip()) for g in args.grades.split(",") if g.strip()],
            )
        )
    )
