"""Replay a curriculum remap artifact in another environment. Deterministic.

Makes no embedding or LLM calls. Everything it needs was decided, reviewed and frozen
in the artifact produced by export_remap_artifact.py.

Run order for a target environment (production):

    1. pg_dump, and verify the dump restores into a scratch database
    2. alembic upgrade head
    3. python -m scripts.wipe_curriculum --curriculum ... --confirm
       (writes the TARGET environment's own question snapshot)
    4. python -m scripts.seed_curriculum_graph --data-file cambridge_v2.json
    5. python -m scripts.import_remap_artifact --artifact ... --snapshot <from step 3>
    6. python -m scripts.create_learning_objectives --mode legacy-backfill
    7. python -m scripts.validate_curriculum_remap        (non-zero exit = stop)

Step 5 must precede step 6: the artifact's canonical codes are fixed, and the backfill
generates its own with collision suffixes. Running the backfill first would let it
claim a code the artifact needs.

Idempotent throughout — objectives upsert on canonical_code, placements do nothing on
conflict, and question binding only ever fills a NULL. Re-running changes nothing.

Coverage is reported rather than assumed. Anything in the artifact that this
environment does not have (or vice versa) is listed explicitly, because a silent
partial application would look identical to a successful one.

Usage (from backend/):
    python -m scripts.import_remap_artifact \
        --artifact data/curriculum/remap_artifact_cambridge_v2.json \
        --snapshot ../backups/question_subtopic_snapshot_<ts>.json --dry-run
"""

import argparse
import asyncio
import json
import sys
import uuid
from collections import defaultdict
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

structlog.configure(
    processors=[structlog.stdlib.add_log_level, structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

SUPPORTED_ARTIFACT_VERSION = 1


class ImportError_(Exception):
    """Raised when the artifact cannot be applied to this environment."""


async def import_objectives(db: AsyncSession, objectives: list[dict[str, Any]], dry_run: bool) -> dict[str, int]:
    """Upsert objectives, resolving topics by canonical_code.

    A missing topic aborts the run rather than skipping: it means the curriculum seed
    did not complete, and continuing would produce a partial curriculum that still
    reports success.
    """
    created = 0
    existing = 0
    for objective in objectives:
        topic = await db.execute(
            text("SELECT id FROM topics WHERE canonical_code = :code"),
            {"code": objective["topic_code"]},
        )
        topic_id = topic.scalar_one_or_none()
        if topic_id is None:
            raise ImportError_(
                f"Topic {objective['topic_code']!r} not found for objective "
                f"{objective['canonical_code']!r}. Seed the curriculum first (step 4)."
            )

        present = await db.execute(
            text("SELECT id FROM learning_objectives WHERE canonical_code = :code"),
            {"code": objective["canonical_code"]},
        )
        if present.scalar_one_or_none() is not None:
            existing += 1
            continue

        created += 1
        if not dry_run:
            await db.execute(
                text(
                    """
                    INSERT INTO learning_objectives
                        (id, canonical_code, name, learning_objective, topic_id,
                         bloom_taxonomy_level, embedding, is_active, created_at)
                    VALUES (:id, :code, :name, :lo, :topic_id, :bloom, :embedding, TRUE, now())
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "code": objective["canonical_code"],
                    "name": objective["name"],
                    "lo": objective["learning_objective"],
                    "topic_id": topic_id,
                    "bloom": objective["bloom_taxonomy_level"],
                    "embedding": objective["embedding"],
                },
            )
    return {"created": created, "already_present": existing}


async def import_placements(db: AsyncSession, placements: list[dict[str, str]], dry_run: bool) -> dict[str, int]:
    """Link subtopics to objectives, both resolved by canonical_code."""
    linked = 0
    missing_subtopic: list[str] = []
    missing_objective: list[str] = []

    for placement in placements:
        row = await db.execute(
            text(
                """
                SELECT (SELECT id FROM subtopics WHERE canonical_code = :sub) AS subtopic_id,
                       (SELECT id FROM learning_objectives WHERE canonical_code = :obj) AS objective_id
                """
            ),
            {"sub": placement["subtopic_code"], "obj": placement["objective_code"]},
        )
        subtopic_id, objective_id = row.one()
        if subtopic_id is None:
            missing_subtopic.append(placement["subtopic_code"])
            continue
        if objective_id is None:
            missing_objective.append(placement["objective_code"])
            continue

        linked += 1
        if not dry_run:
            await db.execute(
                text(
                    """
                    INSERT INTO subtopic_objectives (subtopic_id, learning_objective_id)
                    VALUES (:sub, :obj) ON CONFLICT DO NOTHING
                    """
                ),
                {"sub": subtopic_id, "obj": objective_id},
            )

    if missing_subtopic:
        log.warning("placements_skipped_missing_subtopic", count=len(missing_subtopic), sample=missing_subtopic[:5])
    if missing_objective:
        log.warning("placements_skipped_missing_objective", count=len(missing_objective), sample=missing_objective[:5])
    return {"linked": linked, "skipped": len(missing_subtopic) + len(missing_objective)}


async def apply_question_mapping(
    db: AsyncSession,
    mapping: list[dict[str, Any]],
    snapshot_path: Path,
    dry_run: bool,
) -> dict[str, int]:
    """Bind this environment's questions using its OWN snapshot and the artifact's decisions.

    The snapshot supplies which local questions belonged to which old subtopic; the
    artifact supplies which objective that old subtopic maps to. Question UUIDs are
    never taken from the artifact, so environments with different question rows still
    work.
    """
    snapshot = json.loads(snapshot_path.read_text())
    local_by_old_code: dict[str, list[str]] = defaultdict(list)
    for row in snapshot:
        local_by_old_code[row["canonical_code"]].append(row["question_id"])

    by_old_code = {m["old_subtopic_code"]: m["objective_code"] for m in mapping}

    bound = 0
    unresolved_groups = 0
    not_in_artifact = [code for code in local_by_old_code if code not in by_old_code]

    for old_code, question_ids in local_by_old_code.items():
        objective_code = by_old_code.get(old_code)
        if objective_code is None:
            # Either the artifact recorded no decision, or this environment has an old
            # subtopic the artifact never saw. Both need a human; neither is an error.
            unresolved_groups += 1
            continue

        objective = await db.execute(
            text("SELECT id FROM learning_objectives WHERE canonical_code = :code"),
            {"code": objective_code},
        )
        objective_id = objective.scalar_one_or_none()
        if objective_id is None:
            raise ImportError_(f"Artifact maps {old_code!r} to unknown objective {objective_code!r}")

        if dry_run:
            count = await db.execute(
                text("SELECT count(*) FROM question_bank WHERE id = ANY(:ids) AND learning_objective_id IS NULL"),
                {"ids": [uuid.UUID(q) for q in question_ids]},
            )
            bound += int(count.scalar_one())
        else:
            result = await db.execute(
                text(
                    """
                    UPDATE question_bank SET learning_objective_id = :obj
                    WHERE id = ANY(:ids) AND learning_objective_id IS NULL
                    """
                ),
                {"obj": objective_id, "ids": [uuid.UUID(q) for q in question_ids]},
            )
            bound += cast("CursorResult[Any]", result).rowcount

    if not_in_artifact:
        log.warning(
            "old_subtopics_absent_from_artifact",
            count=len(not_in_artifact),
            sample=not_in_artifact[:5],
            note="this environment had old subtopics the artifact does not cover — needs review",
        )

    return {
        "questions_bound": bound,
        "unresolved_groups": unresolved_groups,
        "groups_absent_from_artifact": len(not_in_artifact),
    }


async def already_applied(db: AsyncSession, artifact_name: str) -> dict[str, Any] | None:
    """Return the prior application record for this artifact, if any."""
    result = await db.execute(
        text(
            "SELECT artifact_name, applied_at, objectives_created, placements_linked, "
            "questions_bound FROM curriculum_migrations WHERE artifact_name = :name"
        ),
        {"name": artifact_name},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def record_application(
    db: AsyncSession,
    artifact: dict[str, Any],
    artifact_name: str,
    counts: dict[str, int],
) -> None:
    """Record that this artifact was applied, with the counts observed.

    Storing the counts lets a later audit distinguish a full application from a partial
    one — the failure mode that let production drift go unnoticed for so long.
    """
    await db.execute(
        text(
            """
            INSERT INTO curriculum_migrations (
                id, artifact_name, artifact_version, scope, objectives_created,
                placements_linked, questions_bound, groups_unresolved, applied_at
            ) VALUES (
                gen_random_uuid(), :name, :version, CAST(:scope AS jsonb), :created,
                :linked, :bound, :unresolved, now()
            )
            """
        ),
        {
            "name": artifact_name,
            "version": artifact["artifact_version"],
            "scope": json.dumps(artifact["scope"]),
            "created": counts.get("created", 0),
            "linked": counts.get("linked", 0),
            "bound": counts.get("questions_bound", 0),
            "unresolved": counts.get("unresolved_groups", 0),
        },
    )


async def main(artifact_path: Path, snapshot_path: Path, dry_run: bool, force: bool = False) -> int:
    if not artifact_path.exists():
        log.error("artifact_not_found", path=str(artifact_path))
        return 1
    if not snapshot_path.exists():
        log.error("snapshot_not_found", path=str(snapshot_path))
        return 1

    artifact = json.loads(artifact_path.read_text())
    version = artifact.get("artifact_version")
    if version != SUPPORTED_ARTIFACT_VERSION:
        log.error("unsupported_artifact_version", found=version, supported=SUPPORTED_ARTIFACT_VERSION)
        return 1

    log.info("artifact_loaded", scope=artifact["scope"], generated_at=artifact.get("generated_at"))

    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with async_session() as db:
            prior = await already_applied(db, artifact_path.name)
            if prior and not force:
                log.error(
                    "artifact_already_applied",
                    artifact=artifact_path.name,
                    applied_at=str(prior["applied_at"]),
                    previously=dict(prior),
                    hint="pass --force to apply again; the import is idempotent either way",
                )
                return 1

            try:
                objectives = await import_objectives(db, artifact["learning_objectives"], dry_run)
                placements = await import_placements(db, artifact["placements"], dry_run)
                questions = await apply_question_mapping(db, artifact["question_mapping"], snapshot_path, dry_run)

                if dry_run:
                    await db.rollback()
                    log.warning("dry_run_no_changes_made", hint="re-run without --dry-run to apply")
                else:
                    if prior is None:
                        await record_application(
                            db, artifact, artifact_path.name, {**objectives, **placements, **questions}
                        )
                    await db.commit()
            except Exception:
                await db.rollback()
                raise

        log.info("artifact_applied", **objectives, **placements, **questions)
        log.info("next_step", command="python -m scripts.create_learning_objectives --mode legacy-backfill")
        return 0

    except ImportError_ as exc:
        log.error("import_aborted", reason=str(exc))
        return 1
    except Exception as exc:
        log.error("import_failed_rolled_back", error=str(exc), exc_info=True)
        return 1
    finally:
        await engine.dispose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True, help="This environment's own wipe snapshot")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Apply even if curriculum_migrations already records this artifact.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(asyncio.run(main(args.artifact, args.snapshot, args.dry_run, args.force)))
