"""Scoped curriculum wipe — removes one (curriculum x subjects x grades) slice.

This is INCREMENTAL replacement, never a global wipe. Only the scope passed on the
command line is touched; every other curriculum slice stays live. That matters
because new curriculum data arrives per-subject: MATH/SCI grades 6-8 first, then
ENG grades 6-8, then IGCSE grades 9-10, each re-running this same script.

Questions are never deleted. In-scope questions have subtopic_id set to NULL and are
re-bound to learning objectives afterwards. The mapping needed to do that is written
out first (see --archive-dir below), because once subtopic_id is nulled the link
between a question and the concept it tested is gone.

Safety model:
  - Refuses to do anything without --confirm; the default is a read-only preview.
  - Aborts if any RESTRICT dependent exists in scope. Those tables (class_topics,
    assessment_topic_config, study_plans) hold TEACHER-AUTHORED work, not curriculum.
    Destroying them silently is never correct — a human decides what happens to them.
    class_topics and assessment_topic_config can be waived per-run with
    --delete-topic-bindings, since they store topic UUIDs that cannot survive a remap;
    they must then be re-seeded against the new tree. The waiver is never the default.
  - Runs as a single transaction. Any error rolls the whole thing back.
  - Deletes topics only when no curriculum_topics row anywhere still references them,
    since topics are shared across grades and curricula.

Usage (from backend/):
    # Preview only — no writes:
    python -m scripts.wipe_curriculum --curriculum cambridge_lower \
        --subjects MATH,SCI --grades 6,7,8

    # Apply:
    python -m scripts.wipe_curriculum --curriculum cambridge_lower \
        --subjects MATH,SCI --grades 6,7,8 --confirm

Archives written to --archive-dir (default: ../backups):
  - subtopic_content_archive_<ts>.json — curated videos/explanations, keyed by
    subtopic name + canonical_code + LO text so they can be re-attached later.
  - question_subtopic_snapshot_<ts>.json — question_id -> old subtopic identity.
    REQUIRED by the Phase 5 question remap. Do not delete.
  - wiped_subtopics_<ts>.json — the full subtopic rows removed, for audit.
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
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
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()


class WipeScopeError(Exception):
    """Raised when the requested scope is unusable or unsafe to wipe."""


# Selects the curriculum_topics rows in scope. Every other statement derives from
# this CTE, which is what keeps the wipe scoped rather than global.
_SCOPE_CTE = """
WITH scope AS (
    SELECT ct.id AS ct_id
    FROM curriculum_topics ct
    JOIN curricula c ON c.id = ct.curriculum_id AND c.code = :curriculum
    JOIN subjects  s ON s.id = ct.subject_id    AND s.code = ANY(:subjects)
    JOIN grades    g ON g.id = ct.grade_id      AND g.level = ANY(:grades)
),
st AS (
    SELECT sub.id
    FROM subtopics sub
    JOIN scope ON sub.curriculum_topic_id = scope.ct_id
)
"""

# Tables whose rows are TEACHER-AUTHORED and FK-RESTRICT the wipe. Non-zero counts
# abort rather than delete — see module docstring.
_BLOCKING_TABLES: list[tuple[str, str]] = [
    ("class_topics", "SELECT count(*) FROM class_topics x JOIN scope ON x.curriculum_topic_id = scope.ct_id"),
    (
        "assessment_topic_config",
        "SELECT count(*) FROM assessment_topic_config x JOIN scope ON x.curriculum_topic_id = scope.ct_id",
    ),
    ("study_plans", "SELECT count(*) FROM study_plans x JOIN st ON x.subtopic_id = st.id"),
]

# Everything else that references the scope. Counted for the preview so the operator
# sees the true blast radius, not just the five tables the original plan listed.
_IMPACT_TABLES: list[tuple[str, str]] = [
    ("curriculum_topics", "SELECT count(*) FROM scope"),
    ("subtopics", "SELECT count(*) FROM st"),
    ("question_bank (unbound, kept)", "SELECT count(*) FROM question_bank x JOIN st ON x.subtopic_id = st.id"),
    ("subtopic_content", "SELECT count(*) FROM subtopic_content x JOIN st ON x.subtopic_id = st.id"),
    ("subtopic_prerequisites", "SELECT count(*) FROM subtopic_prerequisites x JOIN st ON x.subtopic_id = st.id"),
    ("curriculum_chunks", "SELECT count(*) FROM curriculum_chunks x JOIN st ON x.subtopic_id = st.id"),
    ("gap_states", "SELECT count(*) FROM gap_states x JOIN st ON x.subtopic_id = st.id"),
    ("subtopic_objectives", "SELECT count(*) FROM subtopic_objectives x JOIN st ON x.subtopic_id = st.id"),
    (
        "student_attempt_subtopic_scores",
        "SELECT count(*) FROM student_attempt_subtopic_scores x JOIN st ON x.subtopic_id = st.id",
    ),
    ("subtopic_course_progress", "SELECT count(*) FROM subtopic_course_progress x JOIN st ON x.subtopic_id = st.id"),
    ("mini_course_chat_messages", "SELECT count(*) FROM mini_course_chat_messages x JOIN st ON x.subtopic_id = st.id"),
    (
        "mini_course_quiz_responses",
        "SELECT count(*) FROM mini_course_quiz_responses x JOIN st ON x.subtopic_id = st.id",
    ),
]


def _params(curriculum: str, subjects: list[str], grades: list[int]) -> dict[str, Any]:
    return {"curriculum": curriculum, "subjects": subjects, "grades": grades}


async def _scalar(db: AsyncSession, body: str, params: dict[str, Any]) -> int:
    result = await db.execute(text(_SCOPE_CTE + body), params)
    return int(result.scalar_one())


async def _execute_dml(db: AsyncSession, statement: str, params: dict[str, Any] | None = None) -> int:
    """Run a DML statement and return the affected row count.

    AsyncSession.execute is typed as returning Result, which has no rowcount; DML
    actually yields a CursorResult. The cast keeps the row counts (which are what the
    operator reads to sanity-check the blast radius) without a type: ignore.
    """
    result = await db.execute(text(statement), params or {})
    return cast("CursorResult[Any]", result).rowcount


async def verify_scope_exists(db: AsyncSession, params: dict[str, Any]) -> None:
    """Fail loudly on a scope that matches nothing — almost always a typo in the args.

    Without this a mistyped subject code silently reports "0 rows affected" and looks
    like a successful no-op wipe.
    """
    curricula = await db.execute(text("SELECT count(*) FROM curricula WHERE code = :curriculum"), params)
    if curricula.scalar_one() == 0:
        raise WipeScopeError(f"No curriculum with code '{params['curriculum']}'")

    found = await db.execute(text("SELECT code FROM subjects WHERE code = ANY(:subjects)"), params)
    known = {row[0] for row in found}
    if unknown := set(params["subjects"]) - known:
        raise WipeScopeError(f"Unknown subject code(s): {sorted(unknown)}")

    if await _scalar(db, "SELECT count(*) FROM scope", params) == 0:
        raise WipeScopeError(
            f"Scope matched 0 curriculum_topics "
            f"(curriculum={params['curriculum']}, subjects={params['subjects']}, grades={params['grades']}). "
            "Nothing to wipe — check the arguments."
        )


async def preview(db: AsyncSession, params: dict[str, Any]) -> dict[str, int]:
    """Read-only impact report for the scope."""
    counts: dict[str, int] = {}
    for label, body in _IMPACT_TABLES:
        counts[label] = await _scalar(db, body, params)
    for label, body in _BLOCKING_TABLES:
        counts[f"{label} (BLOCKING)"] = await _scalar(db, body, params)

    log.info("wipe_preview", scope=params)
    for label, count in counts.items():
        log.info("wipe_preview_row", table=label, rows=count)
    return counts


async def assert_no_blocking_rows(db: AsyncSession, params: dict[str, Any], delete_topic_bindings: bool) -> None:
    """Refuse to proceed while teacher-authored data depends on the scope.

    class_topics and assessment_topic_config can be waived with --delete-topic-bindings,
    because they store topic UUIDs that cannot survive a remap in any form. The waiver
    is opt-in per run so a future increment against real school data still stops here.
    """
    waived = {"class_topics", "assessment_topic_config"} if delete_topic_bindings else set()
    blocked = {label: await _scalar(db, body, params) for label, body in _BLOCKING_TABLES if label not in waived}
    offending = {label: n for label, n in blocked.items() if n > 0}
    if offending:
        raise WipeScopeError(
            f"Refusing to wipe: teacher-authored rows still reference this scope: {offending}. "
            "These are not curriculum data — reassign or remove them deliberately first, "
            "or pass --delete-topic-bindings if they are class/assessment topic bindings "
            "you intend to re-seed."
        )


async def archive(db: AsyncSession, params: dict[str, Any], archive_dir: Path, stamp: str) -> dict[str, Path]:
    """Write the three archives. Must run BEFORE any mutation."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    # 1. question -> old subtopic identity. Required by the Phase 5 remap: once
    #    subtopic_id is nulled there is no other record of what a question tested.
    result = await db.execute(
        text(
            _SCOPE_CTE
            + """
            SELECT q.id AS question_id,
                   sub.canonical_code,
                   sub.name AS subtopic_name,
                   sub.learning_objective,
                   t.canonical_code AS topic_code,
                   s.code AS subject_code,
                   g.level AS grade_level
            FROM question_bank q
            JOIN subtopics sub ON sub.id = q.subtopic_id
            JOIN st ON st.id = sub.id
            JOIN curriculum_topics ct ON ct.id = sub.curriculum_topic_id
            JOIN topics   t ON t.id = ct.topic_id
            JOIN subjects s ON s.id = ct.subject_id
            JOIN grades   g ON g.id = ct.grade_id
            """
        ),
        params,
    )
    snapshot = [dict(row) for row in result.mappings()]
    path = archive_dir / f"question_subtopic_snapshot_{stamp}.json"
    path.write_text(json.dumps(snapshot, indent=2, default=str))
    written["question_snapshot"] = path
    log.info("archived", file=str(path), rows=len(snapshot))

    # 2. subtopic_content — curated videos/explanations are the only content worth
    #    salvaging. Keyed by subtopic identity so it can be re-attached by LO match
    #    later, with human approval. Not migrated automatically.
    result = await db.execute(
        text(
            _SCOPE_CTE
            + """
            SELECT sc.*, sub.canonical_code, sub.name AS subtopic_name, sub.learning_objective
            FROM subtopic_content sc
            JOIN subtopics sub ON sub.id = sc.subtopic_id
            JOIN st ON st.id = sub.id
            """
        ),
        params,
    )
    content = [dict(row) for row in result.mappings()]
    path = archive_dir / f"subtopic_content_archive_{stamp}.json"
    path.write_text(json.dumps(content, indent=2, default=str))
    written["subtopic_content"] = path
    log.info("archived", file=str(path), rows=len(content))

    # 3. Full subtopic rows, for audit.
    result = await db.execute(
        text(_SCOPE_CTE + "SELECT sub.* FROM subtopics sub JOIN st ON st.id = sub.id"),
        params,
    )
    subtopics = [{k: v for k, v in row.items() if k != "embedding"} for row in result.mappings()]
    path = archive_dir / f"wiped_subtopics_{stamp}.json"
    path.write_text(json.dumps(subtopics, indent=2, default=str))
    written["subtopics"] = path
    log.info("archived", file=str(path), rows=len(subtopics))

    return written


async def execute_wipe(db: AsyncSession, params: dict[str, Any], delete_topic_bindings: bool) -> dict[str, int]:
    """Perform the wipe. Caller owns the transaction."""
    affected: dict[str, int] = {}

    if delete_topic_bindings:
        # These FK-RESTRICT the curriculum_topics delete below. They hold topic UUIDs
        # that will not exist afterwards, so they must be re-seeded against the new
        # tree rather than migrated.
        for label, table in [
            ("assessment_topic_config", "assessment_topic_config"),
            ("class_topics", "class_topics"),
        ]:
            affected[label] = await _execute_dml(
                db,
                _SCOPE_CTE + f"DELETE FROM {table} WHERE curriculum_topic_id IN (SELECT ct_id FROM scope)",  # noqa: S608
                params,
            )

    # Unbind questions FIRST — question_bank.subtopic_id is RESTRICT, so the subtopic
    # delete below cannot proceed until these are NULL. Questions themselves are kept.
    affected["question_bank_unbound"] = await _execute_dml(
        db,
        _SCOPE_CTE + "UPDATE question_bank SET subtopic_id = NULL WHERE subtopic_id IN (SELECT id FROM st)",
        params,
    )

    # Explicitly clear the CASCADE dependents rather than relying on the cascade, so
    # the counts are reported and an unexpected volume is visible in the output.
    # subtopic_prerequisites: graph edges are meaningless against new codes, no reuse.
    # curriculum_chunks: deprecated RAG store, no reuse.
    # gap_states: derived from attempts on subtopics that will not exist.
    for label, table in [
        ("subtopic_objectives", "subtopic_objectives"),
        ("subtopic_content", "subtopic_content"),
        ("curriculum_chunks", "curriculum_chunks"),
        ("gap_states", "gap_states"),
        ("subtopic_course_progress", "subtopic_course_progress"),
        ("student_attempt_subtopic_scores", "student_attempt_subtopic_scores"),
        ("mini_course_chat_messages", "mini_course_chat_messages"),
        ("mini_course_quiz_responses", "mini_course_quiz_responses"),
    ]:
        affected[label] = await _execute_dml(
            db,
            _SCOPE_CTE + f"DELETE FROM {table} WHERE subtopic_id IN (SELECT id FROM st)",  # noqa: S608
            params,
        )

    # Prerequisites reference subtopics from BOTH sides; an in-scope subtopic may be
    # the prerequisite of an out-of-scope one, so both columns must be cleared.
    affected["subtopic_prerequisites"] = await _execute_dml(
        db,
        _SCOPE_CTE
        + """
        DELETE FROM subtopic_prerequisites
        WHERE subtopic_id IN (SELECT id FROM st)
           OR prerequisite_subtopic_id IN (SELECT id FROM st)
        """,
        params,
    )

    affected["subtopics"] = await _execute_dml(
        db, _SCOPE_CTE + "DELETE FROM subtopics WHERE id IN (SELECT id FROM st)", params
    )

    affected["curriculum_topics"] = await _execute_dml(
        db, _SCOPE_CTE + "DELETE FROM curriculum_topics WHERE id IN (SELECT ct_id FROM scope)", params
    )

    # Topics are shared across grades and curricula — e.g. MATH-NUM may still be used
    # by IGCSE G9 and must survive. Delete only those with no remaining reference from
    # anywhere. learning_objectives.topic_id is RESTRICT, so a topic that already owns
    # objectives is left alone by the FK regardless.
    affected["orphaned_topics"] = await _execute_dml(
        db,
        """
        DELETE FROM topics t
        WHERE NOT EXISTS (SELECT 1 FROM curriculum_topics ct WHERE ct.topic_id = t.id)
          AND NOT EXISTS (SELECT 1 FROM learning_objectives lo WHERE lo.topic_id = t.id)
          AND NOT EXISTS (SELECT 1 FROM mini_course_student_overrides m WHERE m.topic_id = t.id)
        """,
    )

    return affected


async def verify_postconditions(db: AsyncSession, params: dict[str, Any]) -> None:
    """Assert the full invariant, not merely that something happened."""
    remaining_ct = await _scalar(db, "SELECT count(*) FROM scope", params)
    if remaining_ct != 0:
        raise WipeScopeError(f"Post-wipe check failed: {remaining_ct} curriculum_topics still in scope")

    remaining_st = await _scalar(db, "SELECT count(*) FROM st", params)
    if remaining_st != 0:
        raise WipeScopeError(f"Post-wipe check failed: {remaining_st} subtopics still in scope")

    dangling = await db.execute(
        text(
            """
            SELECT count(*) FROM question_bank q
            WHERE q.subtopic_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM subtopics s WHERE s.id = q.subtopic_id)
            """
        )
    )
    if (n := dangling.scalar_one()) != 0:
        raise WipeScopeError(f"Post-wipe check failed: {n} questions point at missing subtopics")

    log.info("postconditions_verified")


async def main(
    curriculum: str,
    subjects: list[str],
    grades: list[int],
    confirm: bool,
    archive_dir: Path,
    delete_topic_bindings: bool = False,
) -> int:
    params = _params(curriculum, subjects, grades)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M")

    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with async_session() as db:
            await verify_scope_exists(db, params)
            counts = await preview(db, params)

            if not confirm:
                log.warning(
                    "dry_run_no_changes_made",
                    hint="re-run with --confirm to apply",
                    questions_to_unbind=counts.get("question_bank (unbound, kept)", 0),
                )
                return 0

            await assert_no_blocking_rows(db, params, delete_topic_bindings)
            written = await archive(db, params, archive_dir, stamp)

            # The preview SELECTs above already opened the session's transaction, so
            # db.begin() here would raise. Commit explicitly instead: every statement
            # in this session — reads and writes — is in one transaction, and any
            # failure (including a postcondition breach) rolls all of it back.
            try:
                affected = await execute_wipe(db, params, delete_topic_bindings)
                await verify_postconditions(db, params)
                await db.commit()
            except Exception:
                await db.rollback()
                raise

            log.info("wipe_complete", scope=params, archives={k: str(v) for k, v in written.items()}, **affected)
            return 0

    except WipeScopeError as exc:
        log.error("wipe_aborted", reason=str(exc))
        return 1
    except Exception as exc:
        log.error("wipe_failed_rolled_back", error=str(exc), exc_info=True)
        return 1
    finally:
        await engine.dispose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--curriculum", required=True, help="Curriculum code, e.g. cambridge_lower")
    parser.add_argument("--subjects", required=True, help="Comma-separated subject codes, e.g. MATH,SCI")
    parser.add_argument("--grades", required=True, help="Comma-separated grade levels, e.g. 6,7,8")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually perform the wipe. Without this the script only previews.",
    )
    parser.add_argument(
        "--delete-topic-bindings",
        action="store_true",
        help=(
            "Also delete in-scope class_topics and assessment_topic_config rows. "
            "Required when classes or assessments are bound to the scope; they store "
            "topic UUIDs that cannot survive the remap and must be re-seeded after."
        ),
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=_BACKEND_ROOT.parent / "backups",
        help="Where to write archives (default: <repo>/backups)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(
        asyncio.run(
            main(
                curriculum=args.curriculum,
                subjects=[s.strip().upper() for s in args.subjects.split(",") if s.strip()],
                grades=[int(g.strip()) for g in args.grades.split(",") if g.strip()],
                confirm=args.confirm,
                archive_dir=args.archive_dir,
                delete_topic_bindings=args.delete_topic_bindings,
            )
        )
    )
