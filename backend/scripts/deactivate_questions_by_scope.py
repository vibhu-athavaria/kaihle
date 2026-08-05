"""Soft-deactivate every active question in a curriculum scope, reversibly.

Written for question REGENERATION: when a scope's questions are being replaced
wholesale, the old ones must go inactive first. That is not merely tidiness —
generate_gap_questions.py targets subtopics with NO active questions, so leaving the
old set active makes the scope invisible to the generator and nothing is produced.

Scope is resolved through the objective bridge, never through question_bank.subtopic_id.
That column is NULL for any question whose placement was replaced by a remap, so a
subtopic_id-based scope query silently matches nothing for exactly the grades most
likely to need regenerating.

Soft-deactivation only. Hard DELETE is blocked by ON DELETE RESTRICT from
student_responses and assessment_selected_questions, and would destroy attempt history
besides. Deactivated questions stay readable for past attempts; they simply stop being
selected for new assessments.

Runs as a single transaction. The row counts here are small (hundreds to low
thousands) and a partially-deactivated bank is a worse state than either endpoint,
so there is nothing to gain by chunking.

Idempotent: already-inactive rows are not matched, so re-running is a no-op.

Usage:
    # 1. Preview — this is the default, nothing is written
    python -m scripts.deactivate_questions_by_scope --subject MATH,SCI --grade 6,7

    # 2. Apply, recording affected ids so the change can be undone
    python -m scripts.deactivate_questions_by_scope --subject MATH,SCI --grade 6,7 \\
        --apply --out backups/deactivated_math_sci_g6_g7.json

    # 3. Undo, if the regeneration is abandoned
    python -m scripts.deactivate_questions_by_scope \\
        --reactivate backups/deactivated_math_sci_g6_g7.json --apply
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import structlog
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal

logger = structlog.get_logger("deactivate_questions_by_scope")

# Selection resolves curriculum through subtopic_objectives; see module docstring.
_SCOPE_SQL = """
SELECT DISTINCT q.id::text AS id, s.code AS subject_code, g.level AS grade_level
FROM question_bank q
JOIN subtopic_objectives so ON so.learning_objective_id = q.learning_objective_id
JOIN subtopics sub         ON sub.id = so.subtopic_id
JOIN curriculum_topics ct  ON ct.id = sub.curriculum_topic_id
JOIN subjects s            ON s.id = ct.subject_id
JOIN grades   g            ON g.id = ct.grade_id
WHERE s.code = ANY(CAST(:subjects AS varchar[]))
  AND g.level = ANY(CAST(:grades AS integer[]))
  AND q.is_active IS TRUE
"""

# Questions orphaned by a remap have neither a learning objective nor a subtopic, so
# no join reaches their curriculum scope. The review queue is the only remaining record
# of where they came from — lo_review_items carries the subject and grade of the old
# placement, and question_ids lists the questions it governs.
#
# Needed when a scope has been regenerated: the fresh questions supersede these, and
# leaving them active keeps unreachable rows in the bank forever.
_ORPHANED_SCOPE_SQL = """
SELECT DISTINCT q.id::text AS id, i.subject_code, i.grade_level
FROM question_bank q
JOIN lo_review_items i ON i.question_ids ? q.id::text
WHERE q.is_active IS TRUE
  AND q.learning_objective_id IS NULL
  AND i.subject_code = ANY(CAST(:subjects AS varchar[]))
  AND i.grade_level  = ANY(CAST(:grades AS integer[]))
"""

_USAGE_SQL = """
SELECT
  (SELECT count(*) FROM student_responses            WHERE question_id = ANY(CAST(:ids AS uuid[]))) AS responses,
  (SELECT count(*) FROM assessment_selected_questions WHERE question_id = ANY(CAST(:ids AS uuid[]))) AS selected
"""


async def preview(subjects: list[str], grades: list[int], orphaned_only: bool = False) -> list[dict[str, object]]:
    """Questions in scope. orphaned_only restricts to those with no objective.

    The two modes are mutually exclusive by design. The scope query matches every
    active question in the subject and grade, which after a regeneration includes the
    freshly imported ones — combining the modes would deactivate the new bank along
    with the orphans it was meant to clean up.
    """
    params = {"subjects": subjects, "grades": grades}
    sql = _ORPHANED_SCOPE_SQL if orphaned_only else _SCOPE_SQL
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text(sql), params)).mappings().all()
        found = [dict(r) for r in rows]

        if not found:
            return found

        usage = (await db.execute(text(_USAGE_SQL), {"ids": [r["id"] for r in found]})).mappings().one()

    breakdown: dict[str, int] = {}
    for r in found:
        key = f"{r['subject_code']} G{r['grade_level']}"
        breakdown[key] = breakdown.get(key, 0) + 1

    # One row per (question, subject, grade): an objective taught in several grades
    # yields the same question more than once, so the per-grade figures sum to more
    # than the number of questions. Report both rather than a misleading single total.
    distinct = len({r["id"] for r in found})
    label = "orphaned (no learning objective)" if orphaned_only else "active"
    print(f"\n{distinct} distinct {label} questions in scope, by placement:")
    for key in sorted(breakdown):
        print(f"  {key:12} {breakdown[key]:5}")
    if sum(breakdown.values()) != distinct:
        print(f"  ({sum(breakdown.values()) - distinct} taught in more than one grade in scope)")
    print("\nExisting references (preserved by soft-deactivation):")
    print(f"  student_responses            {usage['responses']:5}")
    print(f"  assessment_selected_questions {usage['selected']:5}")
    return found


async def deactivate(found: list[dict[str, object]], out_path: Path) -> int:
    # Deduplicate: a question placed in two in-scope grades appears once per placement,
    # and the undo record must not carry it twice.
    ids = sorted({str(r["id"]) for r in found})
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("UPDATE question_bank SET is_active = FALSE WHERE id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": ids},
        )
        # Record before committing: an unrecorded deactivation is not reversible, so
        # a failed write here must abort the transaction rather than orphan the rows.
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "deactivated_at": datetime.now(UTC).isoformat(),
                    "count": len(ids),
                    "question_ids": ids,
                },
                indent=2,
            )
        )
        await db.commit()

    rowcount = result.rowcount or 0
    logger.info("questions_deactivated", count=rowcount, record=str(out_path))
    return rowcount


async def reactivate(record_path: Path) -> int:
    payload = json.loads(record_path.read_text())
    ids = payload["question_ids"]
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("UPDATE question_bank SET is_active = TRUE WHERE id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": ids},
        )
        await db.commit()
    rowcount = result.rowcount or 0
    logger.info("questions_reactivated", count=rowcount, record=str(record_path))
    return rowcount


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--subject", help="Comma-separated subject codes, e.g. MATH,SCI")
    parser.add_argument("--grade", help="Comma-separated grade levels, e.g. 6,7")
    parser.add_argument("--reactivate", type=Path, help="Undo using a record file written by --apply")
    parser.add_argument(
        "--orphaned-only",
        action="store_true",
        help=(
            "Deactivate ONLY questions with no learning objective, located via the\n"
            "review queue. Use AFTER regenerating a scope — the default mode would\n"
            "match the freshly imported questions too and deactivate them."
        ),
    )
    parser.add_argument("--apply", action="store_true", help="Write. Without this, previews only.")
    parser.add_argument("--out", type=Path, help="Where to record affected ids (required with --apply)")
    args = parser.parse_args()

    if args.reactivate:
        if not args.apply:
            payload = json.loads(args.reactivate.read_text())
            print(f"Would reactivate {payload['count']} questions from {args.reactivate}")
            print("Re-run with --apply to write.")
            return
        print(f"Reactivated {await reactivate(args.reactivate)} questions.")
        return

    if not args.subject or not args.grade:
        parser.error("--subject and --grade are required unless using --reactivate")

    subjects = [s.strip().upper() for s in args.subject.split(",") if s.strip()]
    grades = [int(g.strip()) for g in args.grade.split(",") if g.strip()]

    found = await preview(subjects, grades, orphaned_only=args.orphaned_only)
    if not found:
        print("Nothing to do — no active questions in this scope.")
        return

    if not args.apply:
        print("\nPreview only. Re-run with --apply --out <file> to deactivate.")
        return

    if not args.out:
        parser.error("--out is required with --apply so the change can be undone")

    count = await deactivate(found, args.out)
    print(f"\nDeactivated {count} questions. Record written to {args.out}")
    print(f"Undo with: python -m scripts.deactivate_questions_by_scope --reactivate {args.out} --apply")


if __name__ == "__main__":
    asyncio.run(main())
