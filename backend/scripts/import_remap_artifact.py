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

Artifact versions: v2 carries grade_level and normalised_objective per objective, both of
which ADR-003 T4 makes NOT NULL. v1 predates that and carries neither, so it is still
readable but only where grade can be recovered unambiguously from its own placements — an
objective placed at several grades is rejected rather than guessed at, because choosing
its grade is exactly what T3's review queue exists to decide. See resolve_grades().

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

from app.ai.similarity import normalise_text  # noqa: E402
from app.core.config import settings  # noqa: E402

structlog.configure(
    processors=[structlog.stdlib.add_log_level, structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

# v2 carries grade_level and normalised_objective per objective; v1 predates ADR-003 and
# carries neither. Both are readable — see resolve_grades() for how v1 recovers grade.
SUPPORTED_ARTIFACT_VERSIONS = (1, 2)


class ImportError_(Exception):
    """Raised when the artifact cannot be applied to this environment."""


async def resolve_grades(
    db: AsyncSession,
    artifact: dict[str, Any],
) -> dict[str, uuid.UUID]:
    """objective canonical_code -> this environment's grades.id.

    v2 states the grade outright as a level, which resolves against the local grades
    table. v1 predates ADR-003 and does not carry grade at all, so it is recovered from
    the artifact's own placements: each placement names a subtopic, and a subtopic sits
    at exactly one grade. That is the same derivation T1's backfill performs.

    A v1 objective whose placements span several grades cannot be recovered — recording
    which grade each of its questions belongs to is precisely what T3 exists to decide,
    and inferring it here would make that decision a second time, in a second place,
    with no reviewer. Such an artifact is rejected with instructions to re-export as v2
    from an environment where the split has run.
    """
    objectives = artifact["learning_objectives"]

    if artifact["artifact_version"] >= 2:
        resolved: dict[str, uuid.UUID] = {}
        for objective in objectives:
            row = await db.execute(
                text("SELECT id FROM grades WHERE level = :level"),
                {"level": objective["grade_level"]},
            )
            grade_id = row.scalar_one_or_none()
            if grade_id is None:
                raise ImportError_(
                    f"Objective {objective['canonical_code']!r} is at grade level "
                    f"{objective['grade_level']}, which this environment has no grades row for."
                )
            resolved[objective["canonical_code"]] = cast("uuid.UUID", grade_id)
        return resolved

    # v1: derive from placements.
    subtopic_codes_by_objective: dict[str, set[str]] = defaultdict(set)
    for placement in artifact["placements"]:
        subtopic_codes_by_objective[placement["objective_code"]].add(placement["subtopic_code"])

    resolved = {}
    spanning: list[str] = []
    unplaced: list[str] = []
    for objective in objectives:
        code = objective["canonical_code"]
        subtopic_codes = sorted(subtopic_codes_by_objective.get(code, set()))
        if not subtopic_codes:
            unplaced.append(code)
            continue

        rows = await db.execute(
            text("""
                SELECT DISTINCT ct.grade_id
                FROM subtopics st
                JOIN curriculum_topics ct ON ct.id = st.curriculum_topic_id
                WHERE st.canonical_code = ANY(:codes)
            """),
            {"codes": subtopic_codes},
        )
        grade_ids = [r[0] for r in rows.all()]
        if len(grade_ids) == 1:
            resolved[code] = cast("uuid.UUID", grade_ids[0])
        elif len(grade_ids) > 1:
            spanning.append(code)
        else:
            unplaced.append(code)

    if spanning or unplaced:
        raise ImportError_(
            f"This v1 artifact carries {len(spanning)} grade-spanning and {len(unplaced)} unplaced "
            f"objectives, and v1 does not record grade. Re-export as v{SUPPORTED_ARTIFACT_VERSIONS[-1]} "
            f"from an environment where ADR-003 T3 has run. "
            f"Spanning: {', '.join(spanning[:5])}{' ...' if len(spanning) > 5 else ''}. "
            f"Unplaced: {', '.join(unplaced[:5])}{' ...' if len(unplaced) > 5 else ''}."
        )
    return resolved


async def import_objectives(
    db: AsyncSession,
    objectives: list[dict[str, Any]],
    grade_by_code: dict[str, uuid.UUID],
    dry_run: bool,
) -> dict[str, int]:
    """Upsert objectives, resolving topics by canonical_code.

    A missing topic aborts the run rather than skipping: it means the curriculum seed
    did not complete, and continuing would produce a partial curriculum that still
    reports success.

    grade_id and normalised_objective are both NOT NULL since ADR-003 T4. Grade comes
    from resolve_grades(); normalised_objective is recomputed with the same helper the
    de-duplicator uses rather than trusted from a v1 artifact that never had it, so the
    stored key can never disagree with what the de-duplicator considers a duplicate.
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
                        (id, canonical_code, name, learning_objective, topic_id, grade_id,
                         normalised_objective, bloom_taxonomy_level, embedding, is_active, created_at)
                    VALUES (:id, :code, :name, :lo, :topic_id, :grade_id, :norm,
                            :bloom, :embedding, TRUE, now())
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "code": objective["canonical_code"],
                    "name": objective["name"],
                    "lo": objective["learning_objective"],
                    "topic_id": topic_id,
                    "grade_id": grade_by_code[objective["canonical_code"]],
                    "norm": normalise_text(objective["learning_objective"]),
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
    if version not in SUPPORTED_ARTIFACT_VERSIONS:
        log.error("unsupported_artifact_version", found=version, supported=list(SUPPORTED_ARTIFACT_VERSIONS))
        return 1

    log.info(
        "artifact_loaded",
        version=version,
        scope=artifact["scope"],
        generated_at=artifact.get("generated_at"),
        grade_source="artifact" if version >= 2 else "derived from placements (v1)",
    )

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
                # Before anything is written: a v1 artifact that cannot yield a grade for
                # every objective must abort here, not part-way through the insert loop.
                grade_by_code = await resolve_grades(db, artifact)
                objectives = await import_objectives(db, artifact["learning_objectives"], grade_by_code, dry_run)
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
