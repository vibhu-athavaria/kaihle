"""Backfill learning_objectives.grade_id and .normalised_objective (ADR-003 T1).

Grade is derived from where an objective is actually placed:

    learning_objectives <- subtopic_objectives <- subtopics <- curriculum_topics.grade_id

An objective reachable from exactly ONE grade gets that grade. An objective reachable
from several is left NULL — it is a genuine grade-spanning objective and cannot be
assigned mechanically. Task T3 splits those; T4 then sets the column NOT NULL.

normalised_objective is filled for every row using app.ai.similarity.normalise_text —
the same function create_learning_objectives.py de-duplicates with, imported rather than
copied so the two cannot disagree about what "the same objective text" means.

Idempotent. Both updates are guarded on IS NULL, so re-running touches nothing. The
run FAILS (exit 1) if the number of unresolved objectives differs from --expected-null,
because a different number means the data has moved since ADR-003 was measured and T3's
split plan needs revisiting before it runs.

Usage (from backend/):
    python -m scripts.backfill_objective_grades --dry-run
    python -m scripts.backfill_objective_grades
    python -m scripts.backfill_objective_grades --expected-null 12
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, cast

import structlog
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.ai.similarity import normalise_text  # noqa: E402
from app.core.config import settings  # noqa: E402

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

# ADR-003 measured 12 grade-spanning objectives on the dev database (2026-08-12).
DEFAULT_EXPECTED_NULL = 12


async def backfill_grade_ids(db: AsyncSession) -> int:
    """Set grade_id for every objective that resolves to exactly one grade.

    Returns the number of rows updated. Guarded on grade_id IS NULL so a second run
    is a no-op rather than a rewrite.
    """
    result = await db.execute(
        text("""
            UPDATE learning_objectives lo
            SET grade_id = x.grade_id
            FROM (
                SELECT so.learning_objective_id, MIN(ct.grade_id::text)::uuid AS grade_id
                FROM subtopic_objectives so
                JOIN subtopics st ON st.id = so.subtopic_id
                JOIN curriculum_topics ct ON ct.id = st.curriculum_topic_id
                GROUP BY so.learning_objective_id
                HAVING COUNT(DISTINCT ct.grade_id) = 1   -- unambiguous only
            ) x
            WHERE lo.id = x.learning_objective_id AND lo.grade_id IS NULL
        """)
    )
    return cast("CursorResult[Any]", result).rowcount or 0


async def backfill_normalised_objectives(db: AsyncSession) -> int:
    """Fill normalised_objective from learning_objective, in Python.

    Done row-by-row rather than in SQL because the normalisation folds accents via
    NFKD; Postgres can only approximate that with unaccent(), which is a different
    algorithm and would produce keys that disagree with the de-duplicator's.
    """
    rows = (
        await db.execute(
            text("""
                SELECT id, learning_objective
                FROM learning_objectives
                WHERE normalised_objective IS NULL
            """)
        )
    ).all()

    if not rows:
        return 0

    payload = [{"id": str(row.id), "norm": normalise_text(row.learning_objective)} for row in rows]
    await db.execute(
        text("UPDATE learning_objectives SET normalised_objective = :norm WHERE id = CAST(:id AS uuid)"),
        payload,
    )
    return len(payload)


async def count_unresolved(db: AsyncSession) -> int:
    """Objectives still without a grade after the backfill."""
    result = await db.execute(text("SELECT count(*) FROM learning_objectives WHERE grade_id IS NULL"))
    return int(result.scalar() or 0)


async def describe_unresolved(db: AsyncSession) -> list[tuple[str, str]]:
    """(canonical_code, grade levels) for EVERY objective left without a grade.

    LEFT JOIN, not JOIN. Two different things leave grade_id NULL:

      - grade-spanning objectives, reachable from several grades (what T3 splits), and
      - objectives reachable from NO subtopic at all, e.g. after a curriculum wipe
        cascaded their bridge rows away.

    An inner join reports only the first kind, so the count guard in main() could fail
    on a number this function could not account for — leaving an operator staring at
    "found 14, expected 12" with twelve rows listed and no hint about the other two.
    Unplaced objectives are reported with levels "none".
    """
    rows = (
        await db.execute(
            text("""
                SELECT lo.canonical_code,
                       coalesce(
                           string_agg(DISTINCT g.level::text, ',' ORDER BY g.level::text),
                           'none'
                       ) AS levels
                FROM learning_objectives lo
                LEFT JOIN subtopic_objectives so ON so.learning_objective_id = lo.id
                LEFT JOIN subtopics st ON st.id = so.subtopic_id
                LEFT JOIN curriculum_topics ct ON ct.id = st.curriculum_topic_id
                LEFT JOIN grades g ON g.id = ct.grade_id
                WHERE lo.grade_id IS NULL
                GROUP BY lo.canonical_code
                ORDER BY lo.canonical_code
            """)
        )
    ).all()
    return [(row.canonical_code, row.levels) for row in rows]


async def main(dry_run: bool, expected_null: int) -> int:
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with async_session() as db:
            graded = await backfill_grade_ids(db)
            normalised = await backfill_normalised_objectives(db)
            unresolved = await count_unresolved(db)
            spanning = await describe_unresolved(db)

            log.info(
                "backfill_complete",
                grade_id_set=graded,
                normalised_objective_set=normalised,
                unresolved=unresolved,
                expected_unresolved=expected_null,
                dry_run=dry_run,
            )
            for code, levels in spanning:
                if levels == "none":
                    log.warning("unplaced_objective", canonical_code=code, hint="no subtopic links it")
                else:
                    log.info("spanning_objective", canonical_code=code, grades=levels)

            if unresolved != expected_null:
                # Not a warning. T3's split is planned against a specific set of
                # objectives; a different count means that plan is stale.
                log.error(
                    "unresolved_count_mismatch",
                    found=unresolved,
                    expected=expected_null,
                    described=len(spanning),
                    spanning=sum(1 for _, levels in spanning if levels != "none"),
                    unplaced=sum(1 for _, levels in spanning if levels == "none"),
                    hint="data has moved since ADR-003 was measured — re-verify T3 before running it",
                )
                await db.rollback()
                return 1

            if dry_run:
                await db.rollback()
                log.warning("dry_run_no_changes_made", hint="re-run without --dry-run to apply")
            else:
                await db.commit()
    finally:
        await engine.dispose()

    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    parser.add_argument(
        "--expected-null",
        type=int,
        default=DEFAULT_EXPECTED_NULL,
        help=(
            f"Grade-spanning objectives expected to remain unresolved (default {DEFAULT_EXPECTED_NULL}). "
            "Exits non-zero on mismatch."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(asyncio.run(main(dry_run=args.dry_run, expected_null=args.expected_null)))
