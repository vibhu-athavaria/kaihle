"""Create learning objectives (LOs) and bind subtopics to them.

The LO layer is what makes the question bank curriculum-agnostic. Subtopics are
curriculum PLACEMENT and are replaced whenever a curriculum is remapped; learning
objectives are the underlying CONCEPT and survive that. Questions bind to the
objective, so a remap rewrites placement without touching the bank.

Two modes, both idempotent:

--mode new-tree
    For freshly seeded subtopics in a given scope. Runs staged de-duplication so the
    same concept appearing at several placements (e.g. "Ordering decimals" in both
    grade 6 and grade 7) resolves to ONE objective rather than two:
      1. exact normalised objective text within the topic -> link
      2. cosine similarity within the same topic:
           >= 0.90   -> link automatically
           0.80-0.89 -> create a new LO and record the pair for human review
           <  0.80   -> create a new LO
    Both thresholds are calibrated to this embedding model (see the constants below)
    and overridable with --auto-link-threshold / --review-threshold.

    (Curriculum data supplies subtopic codes, not objective codes, so objective
    canonical codes are generated here and de-duplication never keys on them.)
    Semantic comparison is scoped to a single topic. Across topics, near-identical
    wording routinely means genuinely different concepts.

--mode legacy-backfill
    For scopes that were NOT remapped (ENG grades 6-8, all of grades 9-12). Purely
    deterministic: mirror each existing subtopic 1:1 into an objective using its own
    learning_objective text, link it, then set question_bank.learning_objective_id
    through the still-valid subtopic_id. No similarity, no review, no embeddings
    required for correctness.

    This mode is what lets Phase 7 use a SINGLE selection query for every scope. Skip
    it and the service layer needs an old-path/new-path branch forever.

Usage (from backend/):
    python -m scripts.create_learning_objectives --mode legacy-backfill
    python -m scripts.create_learning_objectives --mode new-tree \
        --curriculum cambridge_lower --subjects MATH,SCI --grades 6,7,8
    # add --dry-run to report without writing
"""

import argparse
import asyncio
import json
import re
import sys
import unicodedata
import uuid
from dataclasses import dataclass, field
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

from app.ai.providers.router import embed_batch  # noqa: E402
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

# Similarity bands, calibrated against this embedding model rather than inherited.
#
# Cosine scores are NOT comparable across embedding models — each has its own scale,
# so a threshold carried over from another model means nothing. Measured over
# cambridge_v2 objectives with text-embedding-3-small at 768 dimensions:
#
#   same-topic pairs:      median 0.436   p90 0.645   p99 0.884   max 0.974
#   different-topic pairs: median 0.159   p90 0.305   p99 0.482   max 0.922
#
# AUTO_LINK at 0.90 sits above p99 of same-topic pairs, and genuine restatements of
# one objective still reach it. It is deliberately conservative: a false merge
# silently collapses two distinct concepts, every question bound to either becomes
# mis-targeted, and no downstream check would catch it.
#
# REVIEW at 0.80 is roughly p95 of same-topic pairs. The original plan specified 0.60,
# which for this model is only ~p85 — ordinary same-topic objectives clear it, and it
# produced 161 review items for 451 subtopics, of which the 0.60-0.70 half were pairs
# merely sharing a subject area. 0.80 yields ~34 genuinely arguable pairs.
AUTO_LINK_THRESHOLD = 0.90
REVIEW_THRESHOLD = 0.80

CANONICAL_CODE_MAX_LEN = 50
EMBED_BATCH_SIZE = 96

# Dropped when building a canonical code. Not linguistic stop words — these are the
# scaffolding verbs and connectives that appear in nearly every objective and so
# carry no distinguishing signal.
_CODE_STOP_WORDS = frozenset(
    """
    a an the and or of to in on at for with from by as is are be been being
    use uses using used apply applies applying identify identifies identifying
    understand understands understanding describe describes describing
    recognise recognises recognising recognize recognizes explain explains
    explaining including include includes such that this these those their its
    them they it can will should must able
    """.split()
)


class LearningObjectiveError(Exception):
    """Raised when objectives cannot be created for the requested scope."""


@dataclass
class Stats:
    subtopics_seen: int = 0
    created: int = 0
    linked_by_text: int = 0
    linked_by_similarity: int = 0
    already_linked: int = 0
    questions_bound: int = 0
    review_items: list[dict[str, Any]] = field(default_factory=list)

    def report(self) -> None:
        log.info(
            "learning_objectives_summary",
            subtopics_seen=self.subtopics_seen,
            created=self.created,
            linked_by_text=self.linked_by_text,
            linked_by_similarity=self.linked_by_similarity,
            already_linked=self.already_linked,
            questions_bound=self.questions_bound,
            needs_review=len(self.review_items),
        )


def normalise_text(value: str) -> str:
    """Fold an objective to a comparison key: casing, accents, punctuation, spacing.

    Used for the exact-text de-duplication stage, which catches the common case of
    the same objective being restated verbatim at a different grade.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = stripped.lower()
    without_punct = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", without_punct).strip()


def build_canonical_code(subject_code: str, objective_text: str, taken: set[str]) -> str:
    """Build a human-readable, unique code such as MATH-NEGATIVE-NUMBERS.

    Codes are for humans reading the database and review files; uniqueness is what
    the schema enforces, so collisions get a numeric suffix rather than a hash.
    """
    words = [w for w in normalise_text(objective_text).split() if w not in _CODE_STOP_WORDS and len(w) > 2]
    if not words:
        # Objective was nothing but stop words — fall back to whatever is there so a
        # code is still produced rather than raising.
        words = normalise_text(objective_text).split() or ["objective"]

    prefix = subject_code.upper()
    base = f"{prefix}-{'-'.join(w.upper() for w in words[:3])}"[:CANONICAL_CODE_MAX_LEN].rstrip("-")

    if base not in taken:
        taken.add(base)
        return base

    for suffix in range(2, 1000):
        tail = f"-{suffix}"
        candidate = f"{base[: CANONICAL_CODE_MAX_LEN - len(tail)].rstrip('-')}{tail}"
        if candidate not in taken:
            taken.add(candidate)
            return candidate

    raise LearningObjectiveError(f"Could not generate a unique canonical code from {base!r}")


def parse_vector(raw: object) -> list[float] | None:
    """Coerce a pgvector value to a plain list of floats.

    Read through raw SQL, pgvector comes back as its text form ('[0.1,0.2,...]'),
    not a sequence — list() on it would yield single characters and every similarity
    would silently be garbage. The ORM path returns a real sequence, so both are
    handled here.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        return [float(x) for x in raw.strip().lstrip("[").rstrip("]").split(",") if x.strip()]
    return [float(x) for x in cast("list[Any]", raw)]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity without a numpy dependency in the hot path."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


_SCOPE_FILTER = """
    JOIN curricula c ON c.id = ct.curriculum_id
    JOIN subjects  s ON s.id = ct.subject_id
    JOIN grades    g ON g.id = ct.grade_id
"""


async def fetch_subtopics(
    db: AsyncSession,
    curriculum: str | None,
    subjects: list[str] | None,
    grades: list[int] | None,
) -> list[dict[str, Any]]:
    """Load subtopics that have no objective yet, optionally narrowed to a scope."""
    conditions = ["NOT EXISTS (SELECT 1 FROM subtopic_objectives so WHERE so.subtopic_id = sub.id)"]
    params: dict[str, Any] = {}
    if curriculum:
        conditions.append("c.code = :curriculum")
        params["curriculum"] = curriculum
    if subjects:
        conditions.append("s.code = ANY(:subjects)")
        params["subjects"] = subjects
    if grades:
        conditions.append("g.level = ANY(:grades)")
        params["grades"] = grades

    result = await db.execute(
        text(
            f"""
            SELECT sub.id, sub.name, sub.learning_objective, sub.bloom_taxonomy_level,
                   ct.topic_id, s.code AS subject_code, g.level AS grade_level
            FROM subtopics sub
            JOIN curriculum_topics ct ON ct.id = sub.curriculum_topic_id
            {_SCOPE_FILTER}
            WHERE {" AND ".join(conditions)}
            ORDER BY s.code, g.level, sub.sequence_order NULLS LAST, sub.name
            """  # noqa: S608 — conditions are literals, values are always bound
        ),
        params,
    )
    return [dict(row) for row in result.mappings()]


async def load_existing_objectives(db: AsyncSession, topic_ids: set[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
    """Load objectives for the given topics, indexed by topic.

    Re-runs must link to what already exists rather than duplicating it, so this
    covers objectives created by an earlier invocation as well as by this one.
    """
    if not topic_ids:
        return {}
    result = await db.execute(
        text(
            """
            SELECT id, canonical_code, learning_objective, topic_id, embedding
            FROM learning_objectives
            WHERE topic_id = ANY(:topic_ids) AND is_active = TRUE
            """
        ),
        {"topic_ids": list(topic_ids)},
    )
    by_topic: dict[uuid.UUID, list[dict]] = {}
    for row in result.mappings():
        item = dict(row)
        item["embedding"] = parse_vector(item.get("embedding"))
        by_topic.setdefault(item["topic_id"], []).append(item)
    return by_topic


async def embed_all(texts: list[str]) -> list[list[float]]:
    """Embed in provider-sized batches so one oversized request cannot fail the run."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        chunk = texts[start : start + EMBED_BATCH_SIZE]
        vectors.extend(await embed_batch(chunk))
        log.info("embedded_batch", done=min(start + EMBED_BATCH_SIZE, len(texts)), total=len(texts))
    return vectors


async def run_new_tree(
    db: AsyncSession,
    stats: Stats,
    curriculum: str,
    subjects: list[str],
    grades: list[int],
    dry_run: bool,
    auto_link_threshold: float = AUTO_LINK_THRESHOLD,
    review_threshold: float = REVIEW_THRESHOLD,
) -> None:
    """Create objectives for a freshly seeded scope, with staged de-duplication."""
    subtopics = await fetch_subtopics(db, curriculum, subjects, grades)
    stats.subtopics_seen = len(subtopics)
    if not subtopics:
        log.warning("no_unlinked_subtopics_in_scope", curriculum=curriculum, subjects=subjects, grades=grades)
        return

    log.info("embedding_objectives", count=len(subtopics))
    vectors = await embed_all([s["learning_objective"] for s in subtopics])

    taken_codes = {
        row[0]
        for row in await db.execute(text("SELECT canonical_code FROM learning_objectives"))  # noqa: RUF015
    }
    by_topic = await load_existing_objectives(db, {s["topic_id"] for s in subtopics})
    by_norm_text: dict[tuple[uuid.UUID, str], uuid.UUID] = {
        (lo["topic_id"], normalise_text(lo["learning_objective"])): lo["id"] for los in by_topic.values() for lo in los
    }

    for subtopic, vector in zip(subtopics, vectors, strict=True):
        topic_id = subtopic["topic_id"]
        objective_text = subtopic["learning_objective"]
        norm = normalise_text(objective_text)

        # Stage 2: exact normalised text within the same topic.
        matched_id = by_norm_text.get((topic_id, norm))
        if matched_id is not None:
            stats.linked_by_text += 1
            await link(db, subtopic["id"], matched_id, dry_run)
            continue

        # Stage 3: semantic, scoped to the topic.
        best_id: uuid.UUID | None = None
        best_score = 0.0
        for candidate in by_topic.get(topic_id, []):
            if candidate["embedding"] is None:
                continue
            score = cosine_similarity(vector, candidate["embedding"])
            if score > best_score:
                best_score, best_id = score, candidate["id"]

        if best_id is not None and best_score >= auto_link_threshold:
            stats.linked_by_similarity += 1
            await link(db, subtopic["id"], best_id, dry_run)
            continue

        code = build_canonical_code(subtopic["subject_code"], objective_text, taken_codes)
        new_id = uuid.uuid4()
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
                    "id": new_id,
                    "code": code,
                    "name": subtopic["name"],
                    "lo": objective_text,
                    "topic_id": topic_id,
                    "bloom": subtopic["bloom_taxonomy_level"],
                    "embedding": str(vector),
                },
            )
        stats.created += 1
        await link(db, subtopic["id"], new_id, dry_run)

        # Make it visible to later subtopics in this same run.
        by_topic.setdefault(topic_id, []).append(
            {"id": new_id, "learning_objective": objective_text, "topic_id": topic_id, "embedding": vector}
        )
        by_norm_text[(topic_id, norm)] = new_id

        # A near-miss is not an error — it is a judgement call, so record it for a
        # human instead of guessing in either direction.
        if best_id is not None and review_threshold <= best_score < auto_link_threshold:
            stats.review_items.append(
                {
                    "subtopic_id": str(subtopic["id"]),
                    "subtopic_name": subtopic["name"],
                    "created_objective_id": str(new_id),
                    "created_canonical_code": code,
                    "objective_text": objective_text,
                    "similar_objective_id": str(best_id),
                    "similarity": round(best_score, 4),
                }
            )


async def run_legacy_backfill(db: AsyncSession, stats: Stats, dry_run: bool) -> None:
    """Mirror untouched subtopics 1:1 into objectives. Deterministic, no embeddings."""
    subtopics = await fetch_subtopics(db, None, None, None)
    stats.subtopics_seen = len(subtopics)
    if not subtopics:
        log.info("no_unlinked_subtopics_remaining")
        return

    taken_codes = {
        row[0]
        for row in await db.execute(text("SELECT canonical_code FROM learning_objectives"))  # noqa: RUF015
    }

    for subtopic in subtopics:
        code = build_canonical_code(subtopic["subject_code"], subtopic["learning_objective"], taken_codes)
        new_id = uuid.uuid4()
        if not dry_run:
            await db.execute(
                text(
                    """
                    INSERT INTO learning_objectives
                        (id, canonical_code, name, learning_objective, topic_id,
                         bloom_taxonomy_level, embedding, is_active, created_at)
                    VALUES (:id, :code, :name, :lo, :topic_id, :bloom, NULL, TRUE, now())
                    """
                ),
                {
                    "id": new_id,
                    "code": code,
                    "name": subtopic["name"],
                    "lo": subtopic["learning_objective"],
                    "topic_id": subtopic["topic_id"],
                    "bloom": subtopic["bloom_taxonomy_level"],
                },
            )
        stats.created += 1
        await link(db, subtopic["id"], new_id, dry_run)


async def bind_questions_via_subtopic(db: AsyncSession, dry_run: bool) -> int:
    """Bind questions that still have a valid subtopic_id to that subtopic's objective.

    Deterministic and exact — no similarity involved. Only applies where the subtopic
    maps to exactly one objective, which is always true for legacy-backfill rows.
    Questions orphaned by the wipe have no subtopic_id and are handled in Phase 5.
    """
    if dry_run:
        result = await db.execute(
            text(
                """
                SELECT count(*) FROM question_bank q
                WHERE q.learning_objective_id IS NULL AND q.subtopic_id IS NOT NULL
                  AND (SELECT count(*) FROM subtopic_objectives so WHERE so.subtopic_id = q.subtopic_id) = 1
                """
            )
        )
        return int(result.scalar_one())

    result = await db.execute(
        text(
            """
            UPDATE question_bank q
            SET learning_objective_id = so.learning_objective_id
            FROM subtopic_objectives so
            WHERE so.subtopic_id = q.subtopic_id
              AND q.learning_objective_id IS NULL
              AND (SELECT count(*) FROM subtopic_objectives x WHERE x.subtopic_id = q.subtopic_id) = 1
            """
        )
    )
    return cast("CursorResult[Any]", result).rowcount


async def link(db: AsyncSession, subtopic_id: uuid.UUID, objective_id: uuid.UUID, dry_run: bool) -> None:
    """Bind a subtopic to an objective. ON CONFLICT keeps re-runs safe."""
    if dry_run:
        return
    await db.execute(
        text(
            """
            INSERT INTO subtopic_objectives (subtopic_id, learning_objective_id)
            VALUES (:subtopic_id, :objective_id)
            ON CONFLICT DO NOTHING
            """
        ),
        {"subtopic_id": subtopic_id, "objective_id": objective_id},
    )


async def main(
    mode: str,
    curriculum: str | None,
    subjects: list[str],
    grades: list[int],
    dry_run: bool,
    review_dir: Path,
    auto_link_threshold: float = AUTO_LINK_THRESHOLD,
    review_threshold: float = REVIEW_THRESHOLD,
) -> int:
    if not 0.0 < review_threshold <= auto_link_threshold <= 1.0:
        log.error(
            "invalid_thresholds",
            reason="require 0 < review_threshold <= auto_link_threshold <= 1",
            review_threshold=review_threshold,
            auto_link_threshold=auto_link_threshold,
        )
        return 1

    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    stats = Stats()

    try:
        async with async_session() as db:
            if mode == "new-tree":
                if not curriculum or not subjects or not grades:
                    raise LearningObjectiveError("--mode new-tree requires --curriculum, --subjects and --grades")
                await run_new_tree(
                    db, stats, curriculum, subjects, grades, dry_run, auto_link_threshold, review_threshold
                )
            else:
                await run_legacy_backfill(db, stats, dry_run)

            stats.questions_bound = await bind_questions_via_subtopic(db, dry_run)

            if dry_run:
                await db.rollback()
                log.warning("dry_run_no_changes_made", hint="re-run without --dry-run to apply")
            else:
                await db.commit()

        if stats.review_items:
            review_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M")
            path = review_dir / f"lo_review_{mode}_{stamp}.json"
            path.write_text(json.dumps(stats.review_items, indent=2))
            log.warning("review_file_written", file=str(path), items=len(stats.review_items))

        stats.report()
        return 0

    except LearningObjectiveError as exc:
        log.error("learning_objectives_aborted", reason=str(exc))
        return 1
    except Exception as exc:
        log.error("learning_objectives_failed", error=str(exc), exc_info=True)
        return 1
    finally:
        await engine.dispose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", required=True, choices=["new-tree", "legacy-backfill"])
    parser.add_argument("--curriculum", help="Curriculum code (new-tree only)")
    parser.add_argument("--subjects", default="", help="Comma-separated subject codes (new-tree only)")
    parser.add_argument("--grades", default="", help="Comma-separated grade levels (new-tree only)")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    parser.add_argument(
        "--auto-link-threshold",
        type=float,
        default=AUTO_LINK_THRESHOLD,
        help=(
            f"Cosine similarity at or above which two objectives are merged without review "
            f"(default {AUTO_LINK_THRESHOLD}). Re-calibrate if the embedding model changes."
        ),
    )
    parser.add_argument(
        "--review-threshold",
        type=float,
        default=REVIEW_THRESHOLD,
        help=f"Similarity at or above which a near-match is recorded for review (default {REVIEW_THRESHOLD}).",
    )
    parser.add_argument(
        "--review-dir",
        type=Path,
        default=_BACKEND_ROOT.parent / "backups",
        help="Where to write the similarity review file (default: <repo>/backups)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(
        asyncio.run(
            main(
                mode=args.mode,
                curriculum=args.curriculum,
                subjects=[s.strip().upper() for s in args.subjects.split(",") if s.strip()],
                grades=[int(g.strip()) for g in args.grades.split(",") if g.strip()],
                dry_run=args.dry_run,
                review_dir=args.review_dir,
                auto_link_threshold=args.auto_link_threshold,
                review_threshold=args.review_threshold,
            )
        )
    )
