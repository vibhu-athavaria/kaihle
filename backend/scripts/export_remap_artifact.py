"""Export a curriculum remap as a replayable artifact.

The remap pipeline is not reproducible: create_learning_objectives calls an embedding
provider, and map_questions_to_lo asks an LLM to adjudicate ambiguous matches. Running
it a second time in another environment would produce different objective UUIDs and
potentially different mapping decisions, leaving two divergent curricula.

So the decisions are promoted as DATA, not re-derived. This script exports them from
the environment where they were made and reviewed; import_remap_artifact.py replays
them elsewhere deterministically, with no LLM and no embedding calls.

Nothing is keyed on a UUID. Objectives key on canonical_code, placements on subtopic
canonical_code, and question bindings on the OLD subtopic canonical_code — so the
artifact applies even where the target environment's question rows differ entirely.
Verified against production: all 71 old subtopic codes present, subtopics.canonical_code
984/984 unique, topics.canonical_code 205/205 unique.

Only objectives for the remapped scope are exported. Untouched scopes are handled by
create_learning_objectives --mode legacy-backfill, which is deterministic by
construction and must run AFTER the import so its collision suffixes form around the
artifact's fixed codes rather than colliding with them.

Usage (from backend/):
    python -m scripts.export_remap_artifact \
        --curriculum cambridge_lower --subjects MATH,SCI --grades 6,7,8 \
        --snapshot ../backups/question_subtopic_snapshot_<ts>.json \
        --out ../backend/data/curriculum/remap_artifact_cambridge_v2.json

Commit the artifact: it is the reviewable, diffable record of every mapping decision.
"""

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
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

ARTIFACT_VERSION = 1


class ExportError(Exception):
    """Raised when the artifact cannot be exported safely."""


async def export_objectives(db: AsyncSession, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Objectives reachable from the scope, keyed by canonical_code.

    The embedding is exported too, so the target environment does not need to call an
    embedding provider — and gets byte-identical vectors rather than ones that merely
    resemble the originals.
    """
    result = await db.execute(
        text(
            """
            SELECT DISTINCT lo.canonical_code, lo.name, lo.learning_objective,
                            lo.bloom_taxonomy_level, lo.embedding, t.canonical_code AS topic_code
            FROM learning_objectives lo
            JOIN topics t                ON t.id = lo.topic_id
            JOIN subtopic_objectives so  ON so.learning_objective_id = lo.id
            JOIN subtopics sub           ON sub.id = so.subtopic_id
            JOIN curriculum_topics ct    ON ct.id = sub.curriculum_topic_id
            JOIN curricula c ON c.id = ct.curriculum_id AND c.code = :curriculum
            JOIN subjects  s ON s.id = ct.subject_id    AND s.code = ANY(:subjects)
            JOIN grades    g ON g.id = ct.grade_id      AND g.level = ANY(:grades)
            WHERE lo.is_active
            ORDER BY lo.canonical_code
            """
        ),
        params,
    )
    rows = [dict(r) for r in result.mappings()]
    for row in rows:
        if row["topic_code"] is None:
            raise ExportError(f"Objective {row['canonical_code']!r} has a topic with no canonical_code")
        row["embedding"] = str(row["embedding"]) if row["embedding"] is not None else None
    return rows


async def export_placements(db: AsyncSession, params: dict[str, Any]) -> list[dict[str, str]]:
    """subtopic canonical_code -> objective canonical_code, for the scope."""
    result = await db.execute(
        text(
            """
            SELECT sub.canonical_code AS subtopic_code, lo.canonical_code AS objective_code
            FROM subtopic_objectives so
            JOIN subtopics sub        ON sub.id = so.subtopic_id
            JOIN learning_objectives lo ON lo.id = so.learning_objective_id
            JOIN curriculum_topics ct ON ct.id = sub.curriculum_topic_id
            JOIN curricula c ON c.id = ct.curriculum_id AND c.code = :curriculum
            JOIN subjects  s ON s.id = ct.subject_id    AND s.code = ANY(:subjects)
            JOIN grades    g ON g.id = ct.grade_id      AND g.level = ANY(:grades)
            ORDER BY sub.canonical_code, lo.canonical_code
            """
        ),
        params,
    )
    rows = [dict(r) for r in result.mappings()]
    missing = [r for r in rows if not r["subtopic_code"]]
    if missing:
        raise ExportError(f"{len(missing)} placements reference a subtopic with no canonical_code")
    return rows


async def export_question_mapping(db: AsyncSession, snapshot_path: Path) -> list[dict[str, Any]]:
    """OLD subtopic canonical_code -> objective canonical_code.

    Derived by reading back where the questions of each old subtopic actually landed,
    so what is exported is the applied result — including any human corrections made
    after the automated run — rather than the script's original proposal.
    """
    snapshot = json.loads(snapshot_path.read_text())
    by_old_code: dict[str, list[str]] = defaultdict(list)
    for row in snapshot:
        by_old_code[row["canonical_code"]].append(row["question_id"])

    mapping: list[dict[str, Any]] = []
    for old_code, question_ids in sorted(by_old_code.items()):
        result = await db.execute(
            text(
                """
                SELECT lo.canonical_code, count(*) AS n
                FROM question_bank q
                JOIN learning_objectives lo ON lo.id = q.learning_objective_id
                WHERE q.id = ANY(:ids)
                GROUP BY lo.canonical_code
                ORDER BY n DESC
                """
            ),
            {"ids": question_ids},
        )
        bound = [dict(r) for r in result.mappings()]
        if not bound:
            # Left for human review, or deliberately declined. Recorded so the target
            # environment reports the same gap instead of appearing complete.
            mapping.append({"old_subtopic_code": old_code, "objective_code": None, "question_count": len(question_ids)})
            continue
        if len(bound) > 1:
            log.warning(
                "old_subtopic_split_across_objectives",
                old_subtopic_code=old_code,
                objectives=[b["canonical_code"] for b in bound],
                note="exporting the majority binding; review if this was unintended",
            )
        mapping.append(
            {
                "old_subtopic_code": old_code,
                "objective_code": bound[0]["canonical_code"],
                "question_count": len(question_ids),
            }
        )
    return mapping


async def main(
    curriculum: str,
    subjects: list[str],
    grades: list[int],
    snapshot_path: Path,
    out_path: Path,
) -> int:
    if not snapshot_path.exists():
        log.error("snapshot_not_found", path=str(snapshot_path))
        return 1

    params = {"curriculum": curriculum, "subjects": subjects, "grades": grades}
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with async_session() as db:
            objectives = await export_objectives(db, params)
            placements = await export_placements(db, params)
            question_mapping = await export_question_mapping(db, snapshot_path)

        artifact = {
            "artifact_version": ARTIFACT_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "scope": {"curriculum": curriculum, "subjects": subjects, "grades": grades},
            "learning_objectives": objectives,
            "placements": placements,
            "question_mapping": question_mapping,
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(artifact, indent=2))

        unmapped = [m for m in question_mapping if m["objective_code"] is None]
        log.info(
            "artifact_exported",
            file=str(out_path),
            objectives=len(objectives),
            placements=len(placements),
            mapped_old_subtopics=len(question_mapping) - len(unmapped),
            unmapped_old_subtopics=len(unmapped),
            unmapped_questions=sum(m["question_count"] for m in unmapped),
        )
        return 0

    except ExportError as exc:
        log.error("export_aborted", reason=str(exc))
        return 1
    except Exception as exc:
        log.error("export_failed", error=str(exc), exc_info=True)
        return 1
    finally:
        await engine.dispose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--curriculum", required=True)
    parser.add_argument("--subjects", required=True)
    parser.add_argument("--grades", required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(
        asyncio.run(
            main(
                curriculum=args.curriculum,
                subjects=[s.strip().upper() for s in args.subjects.split(",") if s.strip()],
                grades=[int(g.strip()) for g in args.grades.split(",") if g.strip()],
                snapshot_path=args.snapshot,
                out_path=args.out,
            )
        )
    )
