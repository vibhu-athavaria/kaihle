"""Split grade-spanning learning objectives into one objective per grade (ADR-003 T3).

T1 gave every objective a grade_id wherever it could be derived unambiguously. Twelve
objectives could not be: they are reachable from subtopics at two or three different
grades, so "the" grade of the objective does not exist yet. This script makes it exist.

For each spanning objective:

  1. The existing row keeps its id and takes its LOWEST grade. Keeping the id matters —
     questions, review items and exports already reference it.
  2. One new objective per additional grade, identical in every respect except
     grade_id and a canonical_code suffixed -G{level}. The copies deliberately share
     normalised_objective: that is exactly what T4's UNIQUE (topic_id, grade_id,
     normalised_objective) permits once grade_id differs, and is the invariant this
     whole plan exists to establish.
  3. Each subtopic_objectives link moves to the objective for its own grade.
  4. Questions follow their surviving subtopic_id provenance to the right grade.
  5. Questions with NO subtopic_id go to the KaihleAdmin review queue.

Step 5 is the one that matters. A question whose subtopic_id was NULLed by a curriculum
remap carries no evidence of its grade. Step 1 keeps the original row at the lowest
grade, so doing nothing silently relabels every such question as the lowest grade —
assigning grade by accident of the algorithm rather than by evidence, which is the exact
failure ADR-003 exists to prevent. They are parked as OBJECTIVE_GRADE_SPLIT review items
instead, one per source objective, with every grade copy offered as a candidate.

Those questions stay bound to the lowest-grade objective while they wait. That keeps
them selectable rather than removing them from the bank for the duration of a human
review, and it is safe because the binding is only wrong about grade, never about
concept. The queue card reports them as outstanding regardless of being bound.

Idempotent. Detection is driven by grade_id IS NULL, the objective insert is
ON CONFLICT (canonical_code) DO NOTHING, and review items upsert only while PENDING, so
a second run is a no-op and an interrupted run resumes. Everything commits in one
transaction, so a crash leaves no half-split objective.

Usage (from backend/):
    python -m scripts.split_spanning_objectives --dry-run
    python -m scripts.split_spanning_objectives
"""

import argparse
import asyncio
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import structlog
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.services.lo_review_service import ITEM_TYPE_GRADE_SPLIT, upsert_review_item  # noqa: E402

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
# A different number means the curriculum has moved and this split needs re-verifying.
DEFAULT_EXPECTED_SPANNING = 12


@dataclass
class Placement:
    """One grade an objective is taught at, and the subtopics that place it there."""

    grade_id: uuid.UUID
    level: int
    subtopic_ids: list[uuid.UUID] = field(default_factory=list)


@dataclass
class Spanning:
    """An objective reachable from more than one grade."""

    objective_id: uuid.UUID
    canonical_code: str
    name: str
    learning_objective: str
    subject_code: str | None
    placements: list[Placement]

    @property
    def lowest(self) -> Placement:
        return self.placements[0]

    @property
    def higher(self) -> list[Placement]:
        return self.placements[1:]


async def find_spanning(db: AsyncSession) -> list[Spanning]:
    """Every objective without a grade that is placed at more than one grade.

    Objectives placed at NO grade are excluded — they are unplaced, not spanning, and
    splitting them is meaningless. T4 has to deal with those separately.
    """
    rows = (
        await db.execute(
            text("""
                SELECT so.learning_objective_id AS objective_id,
                       lo.canonical_code,
                       lo.name,
                       lo.learning_objective,
                       ct.grade_id,
                       g.level,
                       s.code AS subject_code,
                       so.subtopic_id
                FROM subtopic_objectives so
                JOIN learning_objectives lo ON lo.id = so.learning_objective_id
                JOIN subtopics st ON st.id = so.subtopic_id
                JOIN curriculum_topics ct ON ct.id = st.curriculum_topic_id
                JOIN grades g ON g.id = ct.grade_id
                JOIN subjects s ON s.id = ct.subject_id
                WHERE lo.grade_id IS NULL
                ORDER BY lo.canonical_code, g.level
            """)
        )
    ).all()

    grouped: dict[uuid.UUID, Spanning] = {}
    for row in rows:
        spanning = grouped.get(row.objective_id)
        if spanning is None:
            spanning = Spanning(
                objective_id=row.objective_id,
                canonical_code=row.canonical_code,
                name=row.name,
                learning_objective=row.learning_objective,
                subject_code=row.subject_code,
                placements=[],
            )
            grouped[row.objective_id] = spanning
        placement = next((p for p in spanning.placements if p.grade_id == row.grade_id), None)
        if placement is None:
            placement = Placement(grade_id=row.grade_id, level=row.level)
            spanning.placements.append(placement)
        placement.subtopic_ids.append(row.subtopic_id)

    return [s for s in grouped.values() if len(s.placements) > 1]


async def create_grade_copy(db: AsyncSession, source: Spanning, placement: Placement) -> uuid.UUID:
    """Clone the objective at one grade, or return the existing clone.

    INSERT ... SELECT rather than reading the row into Python: embedding is a pgvector
    column and round-tripping it through a bind parameter is both lossy-looking and
    pointless when Postgres can copy it in place.
    """
    new_code = f"{source.canonical_code}-G{placement.level}"
    result = (
        await db.execute(
            text("""
                INSERT INTO learning_objectives (
                    id, canonical_code, name, learning_objective, topic_id, grade_id,
                    normalised_objective, bloom_taxonomy_level, embedding, is_active
                )
                SELECT gen_random_uuid(), :new_code, lo.name, lo.learning_objective, lo.topic_id,
                       CAST(:grade_id AS uuid), lo.normalised_objective, lo.bloom_taxonomy_level,
                       lo.embedding, lo.is_active
                FROM learning_objectives lo
                WHERE lo.id = CAST(:source_id AS uuid)
                ON CONFLICT (canonical_code) DO NOTHING
                RETURNING id
            """),
            {"new_code": new_code, "grade_id": str(placement.grade_id), "source_id": str(source.objective_id)},
        )
    ).scalar_one_or_none()

    if result is not None:
        return cast("uuid.UUID", result)

    # Conflict: a previous interrupted run already created it. Resume against that row.
    existing = (
        await db.execute(
            text("SELECT id FROM learning_objectives WHERE canonical_code = :code"),
            {"code": new_code},
        )
    ).scalar_one()
    return cast("uuid.UUID", existing)


async def repoint(db: AsyncSession, source: Spanning, placement: Placement, target_id: uuid.UUID) -> tuple[int, int]:
    """Move one grade's bridge links and provenanced questions onto the grade's copy.

    Returns (links moved, questions moved). Both statements are scoped to the source
    objective, so re-running after a partial run moves nothing a second time.
    """
    subtopic_ids = [str(sid) for sid in placement.subtopic_ids]

    questions = await db.execute(
        text("""
            UPDATE question_bank
            SET learning_objective_id = CAST(:target_id AS uuid)
            WHERE learning_objective_id = CAST(:source_id AS uuid)
              AND subtopic_id = ANY(CAST(:subtopic_ids AS uuid[]))
        """),
        {"target_id": str(target_id), "source_id": str(source.objective_id), "subtopic_ids": subtopic_ids},
    )
    links = await db.execute(
        text("""
            UPDATE subtopic_objectives
            SET learning_objective_id = CAST(:target_id AS uuid)
            WHERE learning_objective_id = CAST(:source_id AS uuid)
              AND subtopic_id = ANY(CAST(:subtopic_ids AS uuid[]))
        """),
        {"target_id": str(target_id), "source_id": str(source.objective_id), "subtopic_ids": subtopic_ids},
    )
    return (
        cast("CursorResult[Any]", links).rowcount or 0,
        cast("CursorResult[Any]", questions).rowcount or 0,
    )


async def park_unprovenanced(
    db: AsyncSession,
    source: Spanning,
    copies: dict[int, uuid.UUID],
) -> int:
    """Queue the questions whose grade cannot be inferred. Returns how many.

    They keep their binding to the lowest-grade objective — the split has to leave them
    bound to something, and the lowest grade is a placeholder, not a ruling. The review
    item is what makes that visible: until it is resolved these questions are flagged,
    and approving it re-binds every one of them in a single action.
    """
    question_ids = [
        str(row.id)
        for row in (
            await db.execute(
                text("""
                    SELECT id FROM question_bank
                    WHERE learning_objective_id = CAST(:source_id AS uuid)
                      AND subtopic_id IS NULL
                    ORDER BY id
                """),
                {"source_id": str(source.objective_id)},
            )
        ).all()
    ]
    if not question_ids:
        return 0

    candidates = [
        {
            "objective_id": str(copies[placement.level]),
            "canonical_code": (
                source.canonical_code
                if placement.level == source.lowest.level
                else f"{source.canonical_code}-G{placement.level}"
            ),
            "learning_objective": source.learning_objective,
            "grade_level": placement.level,
        }
        for placement in source.placements
    ]

    await upsert_review_item(
        db,
        item_type=ITEM_TYPE_GRADE_SPLIT,
        source_code=source.canonical_code,
        source_name=f"{source.name} — taught at grades {', '.join(str(p.level) for p in source.placements)}",
        source_learning_objective=source.learning_objective,
        subject_code=source.subject_code,
        # No single grade — that is the whole question being asked. The per-grade
        # options live in candidates.
        grade_level=None,
        question_ids=question_ids,
        candidates=candidates,
        llm_reason=(
            "This question lost its subtopic in a curriculum remap, so its grade cannot be "
            "inferred. It is currently bound to the lowest grade as a placeholder."
        ),
    )
    return len(question_ids)


async def split_objective(db: AsyncSession, source: Spanning) -> dict[str, Any]:
    """Split one objective across its grades. Returns a per-objective report."""
    copies: dict[int, uuid.UUID] = {source.lowest.level: source.objective_id}
    links_moved = 0
    questions_moved = 0

    for placement in source.higher:
        target_id = await create_grade_copy(db, source, placement)
        copies[placement.level] = target_id
        links, questions = await repoint(db, source, placement, target_id)
        links_moved += links
        questions_moved += questions

    # Last, so an interrupted run still looks unresolved and re-runs cleanly.
    await db.execute(
        text("UPDATE learning_objectives SET grade_id = CAST(:grade_id AS uuid) WHERE id = CAST(:id AS uuid)"),
        {"grade_id": str(source.lowest.grade_id), "id": str(source.objective_id)},
    )

    parked = await park_unprovenanced(db, source, copies)

    empty: list[int] = []
    for level, objective_id in sorted(copies.items()):
        has_questions = (
            await db.execute(
                text("SELECT 1 FROM question_bank WHERE learning_objective_id = CAST(:id AS uuid) LIMIT 1"),
                {"id": str(objective_id)},
            )
        ).scalar()
        if not has_questions:
            empty.append(level)

    return {
        "canonical_code": source.canonical_code,
        "grades": [p.level for p in source.placements],
        "objectives_created": len(source.higher),
        "links_moved": links_moved,
        "questions_moved": questions_moved,
        "questions_parked": parked,
        "grades_without_questions": empty,
    }


async def verify(db: AsyncSession) -> list[str]:
    """Assert the full postcondition, not merely that something happened.

    Three separate things have to hold, and checking only the first would pass a run
    that split the objectives but left the links or the questions pointing at the wrong
    grade — which is worse than not splitting at all, because it looks finished.
    """
    problems: list[str] = []

    still_spanning = len(await find_spanning(db))
    if still_spanning:
        problems.append(f"{still_spanning} objectives still resolve to more than one grade")

    mismatched_links = (
        await db.execute(
            text("""
                SELECT count(*)
                FROM subtopic_objectives so
                JOIN learning_objectives lo ON lo.id = so.learning_objective_id
                JOIN subtopics st ON st.id = so.subtopic_id
                JOIN curriculum_topics ct ON ct.id = st.curriculum_topic_id
                WHERE lo.grade_id IS NOT NULL AND lo.grade_id <> ct.grade_id
            """)
        )
    ).scalar_one()
    if mismatched_links:
        problems.append(f"{mismatched_links} subtopic links point at an objective from a different grade")

    mismatched_questions = (
        await db.execute(
            text("""
                SELECT count(*)
                FROM question_bank qb
                JOIN learning_objectives lo ON lo.id = qb.learning_objective_id
                JOIN subtopics st ON st.id = qb.subtopic_id
                JOIN curriculum_topics ct ON ct.id = st.curriculum_topic_id
                WHERE lo.grade_id IS NOT NULL AND lo.grade_id <> ct.grade_id
            """)
        )
    ).scalar_one()
    if mismatched_questions:
        problems.append(f"{mismatched_questions} questions are bound to an objective from a different grade")

    return problems


async def main(dry_run: bool, expected_spanning: int) -> int:
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with async_session() as db:
            spanning = await find_spanning(db)
            log.info("spanning_objectives_found", count=len(spanning), expected=expected_spanning, dry_run=dry_run)

            if spanning and len(spanning) != expected_spanning:
                log.error(
                    "spanning_count_mismatch",
                    found=len(spanning),
                    expected=expected_spanning,
                    codes=[s.canonical_code for s in spanning],
                    hint="curriculum has moved since ADR-003 was measured — re-verify T3 before running it",
                )
                await db.rollback()
                return 1

            if not spanning:
                log.info("nothing_to_split", hint="already split, or T1 resolved every objective")
                await db.rollback()
                return 0

            reports = [await split_objective(db, source) for source in spanning]
            for report in reports:
                log.info("objective_split", **report)

            authoring_backlog = [
                f"{r['canonical_code']}-G{level}" for r in reports for level in r["grades_without_questions"]
            ]
            log.info(
                "split_complete",
                objectives_split=len(reports),
                objectives_created=sum(r["objectives_created"] for r in reports),
                links_moved=sum(r["links_moved"] for r in reports),
                questions_moved=sum(r["questions_moved"] for r in reports),
                questions_parked_for_review=sum(r["questions_parked"] for r in reports),
                review_items=sum(1 for r in reports if r["questions_parked"]),
            )
            if authoring_backlog:
                # Expected, not a failure: those grades' provenance is gone, so the copy
                # is real curriculum with no questions yet. Someone has to author them.
                log.warning("objectives_without_questions", codes=authoring_backlog, hint="authoring backlog")

            problems = await verify(db)
            if problems:
                for problem in problems:
                    log.error("postcondition_failed", detail=problem)
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
    parser.add_argument("--dry-run", action="store_true", help="Do the whole split, verify it, then roll back")
    parser.add_argument(
        "--expected-spanning",
        type=int,
        default=DEFAULT_EXPECTED_SPANNING,
        help=(
            f"Grade-spanning objectives expected (default {DEFAULT_EXPECTED_SPANNING}). "
            "Exits non-zero on mismatch, unless there are none left to split."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(asyncio.run(main(dry_run=args.dry_run, expected_spanning=args.expected_spanning)))
