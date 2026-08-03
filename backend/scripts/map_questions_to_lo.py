"""Re-bind questions orphaned by a scoped curriculum wipe to learning objectives.

The wipe sets question_bank.subtopic_id to NULL rather than deleting questions, and
writes question_subtopic_snapshot_<ts>.json recording what each question was attached
to. This script reads that snapshot and re-binds the questions to objectives in the
new tree.

Matching is per OLD SUBTOPIC, not per question. Every question that shared an old
subtopic shared a concept, so one decision covers all of them: the 2278 questions
orphaned from cambridge_lower MATH/SCI came from just 71 distinct subtopics. That is
71 judgements instead of 2278, and the subtopic's own objective text is a far cleaner
matching signal than an individual question stem, which is often a bare numeric
prompt with no topical content at all.

The tradeoff is explicit: a question already mis-filed under an otherwise correct
subtopic stays mis-filed. That is already true of the data today, and per-question
matching would not reliably fix it.

Candidates are scoped to the same subject. Bands:
    >= --auto-threshold          bind automatically
    review band                  write to a review file, leave unbound
    <  --review-threshold        report as unmatched, leave unbound

Idempotent: only ever fills a NULL learning_objective_id.

Usage (from backend/):
    python -m scripts.map_questions_to_lo --snapshot ../backups/question_subtopic_snapshot_<ts>.json --dry-run
    python -m scripts.map_questions_to_lo --snapshot ../backups/question_subtopic_snapshot_<ts>.json
"""

import argparse
import asyncio
import json
import sys
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.ai.providers.router import complete  # noqa: E402
from app.core.config import settings  # noqa: E402
from scripts.create_learning_objectives import cosine_similarity, embed_all, parse_vector  # noqa: E402

_PROMPTS_DIR = _BACKEND_ROOT / "app" / "ai" / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), autoescape=False)  # noqa: S701

structlog.configure(
    processors=[structlog.stdlib.add_log_level, structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

# Calibrated for text-embedding-3-small at 768 dims, same measurements as
# create_learning_objectives. This compares an OLD curriculum's objective text to a
# NEW one's, so wording differs more than between two objectives of a single
# curriculum version — but binding a question to the wrong concept is the expensive
# error, so the automatic band stays tight.
AUTO_BIND_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.60
TOP_CANDIDATES = 3
# Below this, the top candidate is wrong often enough that asking the model to choose
# invites a confident mistake. These go straight to the unmatched report.
LLM_FLOOR = 0.60


class QuestionRemapError(Exception):
    """Raised when the remap cannot proceed."""


async def load_candidate_objectives(db: AsyncSession) -> dict[str, list[dict[str, Any]]]:
    """Load active objectives that have an embedding, grouped by subject code.

    Only objectives reachable from a live subtopic are candidates — an objective with
    no placement cannot be what a question should target.
    """
    result = await db.execute(
        text(
            """
            SELECT DISTINCT lo.id, lo.canonical_code, lo.learning_objective,
                            lo.embedding, s.code AS subject_code
            FROM learning_objectives lo
            JOIN subtopic_objectives so ON so.learning_objective_id = lo.id
            JOIN subtopics sub          ON sub.id = so.subtopic_id
            JOIN curriculum_topics ct   ON ct.id = sub.curriculum_topic_id
            JOIN subjects s             ON s.id = ct.subject_id
            WHERE lo.is_active = TRUE AND lo.embedding IS NOT NULL
            """
        )
    )
    by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in result.mappings():
        item = dict(row)
        item["embedding"] = parse_vector(item["embedding"])
        by_subject[item["subject_code"]].append(item)
    return by_subject


def group_snapshot(snapshot: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Collapse the per-question snapshot into one entry per old subtopic."""
    groups: dict[str, dict[str, Any]] = {}
    for row in snapshot:
        code = row["canonical_code"]
        group = groups.setdefault(
            code,
            {
                "canonical_code": code,
                "subtopic_name": row["subtopic_name"],
                "learning_objective": row["learning_objective"],
                "subject_code": row["subject_code"],
                "grade_level": row["grade_level"],
                "question_ids": [],
            },
        )
        group["question_ids"].append(row["question_id"])
    return groups


async def bind_questions(db: AsyncSession, question_ids: list[str], objective_id: uuid.UUID) -> int:
    """Bind questions to an objective, filling only NULLs so re-runs are safe."""
    result = await db.execute(
        text(
            """
            UPDATE question_bank
            SET learning_objective_id = :objective_id
            WHERE id = ANY(:ids) AND learning_objective_id IS NULL
            """
        ),
        {"objective_id": objective_id, "ids": [uuid.UUID(q) for q in question_ids]},
    )
    return cast("CursorResult[Any]", result).rowcount


async def adjudicate(record: dict[str, Any]) -> dict[str, Any] | None:
    """Ask the LLM which candidate objective matches, or None if it declines.

    Used only where embedding similarity is inconclusive. Similarity measures wording
    overlap; whether two objectives assess the same skill is a question about meaning,
    which is what the model is for. A malformed or out-of-range reply is treated as a
    decline, never as a guess.
    """
    template = _jinja_env.get_template("lo_matching.jinja2")
    prompt = template.render(
        subject_code=record["subject_code"],
        grade_level=record["grade_level"],
        question_count=record["question_count"],
        old_subtopic_name=record["old_subtopic_name"],
        old_learning_objective=record["old_learning_objective"],
        candidates=record["candidates"],
    )

    try:
        raw = await complete(
            "lo_matching",
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=300,
        )
    except Exception as exc:
        log.warning("adjudication_call_failed", code=record["old_canonical_code"], error=str(exc))
        return None

    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        log.warning("adjudication_unparseable", code=record["old_canonical_code"], response=cleaned[:200])
        return None

    choice = parsed.get("choice")
    if choice is None:
        return None
    if not isinstance(choice, int) or not 1 <= choice <= len(record["candidates"]):
        log.warning("adjudication_out_of_range", code=record["old_canonical_code"], choice=choice)
        return None

    return {
        "candidate": record["candidates"][choice - 1],
        "confidence": parsed.get("confidence"),
        "reason": parsed.get("reason"),
    }


async def main(
    snapshot_path: Path,
    dry_run: bool,
    auto_threshold: float,
    review_threshold: float,
    report_dir: Path,
    use_llm: bool = True,
) -> int:
    if not 0.0 < review_threshold <= auto_threshold <= 1.0:
        log.error("invalid_thresholds", review=review_threshold, auto=auto_threshold)
        return 1
    if not snapshot_path.exists():
        log.error("snapshot_not_found", path=str(snapshot_path))
        return 1

    snapshot = json.loads(snapshot_path.read_text())
    groups = group_snapshot(snapshot)
    log.info("snapshot_loaded", questions=len(snapshot), old_subtopics=len(groups))

    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    bound_total = 0
    auto_matched = 0
    llm_matched = 0
    review_items: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []

    try:
        async with async_session() as db:
            candidates = await load_candidate_objectives(db)
            if not candidates:
                raise QuestionRemapError(
                    "No candidate objectives with embeddings found. Run create_learning_objectives first."
                )

            ordered = list(groups.values())
            log.info("embedding_old_objectives", count=len(ordered))
            vectors = await embed_all([g["learning_objective"] for g in ordered])

            for group, vector in zip(ordered, vectors, strict=True):
                pool = candidates.get(group["subject_code"], [])
                scored = sorted(
                    ((cosine_similarity(vector, c["embedding"]), c) for c in pool),
                    key=lambda pair: pair[0],
                    reverse=True,
                )
                top = [
                    {
                        "objective_id": str(c["id"]),
                        "canonical_code": c["canonical_code"],
                        "learning_objective": c["learning_objective"],
                        "similarity": round(score, 4),
                    }
                    for score, c in scored[:TOP_CANDIDATES]
                ]
                record = {
                    "old_canonical_code": group["canonical_code"],
                    "old_subtopic_name": group["subtopic_name"],
                    "old_learning_objective": group["learning_objective"],
                    "subject_code": group["subject_code"],
                    "grade_level": group["grade_level"],
                    "question_count": len(group["question_ids"]),
                    "candidates": top,
                }

                best_score = scored[0][0] if scored else 0.0

                if scored and best_score >= auto_threshold:
                    auto_matched += 1
                    chosen_id = scored[0][1]["id"]
                elif use_llm and scored and best_score >= LLM_FLOOR:
                    # Similarity is inconclusive here, and it measures wording overlap
                    # rather than whether the same skill is assessed. Ask the model.
                    verdict = await adjudicate(record)
                    if verdict is None:
                        record["llm_verdict"] = "declined"
                        review_items.append(record)
                        continue
                    llm_matched += 1
                    chosen_id = uuid.UUID(verdict["candidate"]["objective_id"])
                    decisions.append(
                        {
                            **record,
                            "chosen": verdict["candidate"]["canonical_code"],
                            "confidence": verdict["confidence"],
                            "reason": verdict["reason"],
                        }
                    )
                elif scored and best_score >= review_threshold:
                    review_items.append(record)
                    continue
                else:
                    unmatched.append(record)
                    continue

                if not dry_run:
                    bound_total += await bind_questions(db, group["question_ids"], chosen_id)
                else:
                    bound_total += len(group["question_ids"])

            if dry_run:
                await db.rollback()
                log.warning("dry_run_no_changes_made", hint="re-run without --dry-run to apply")
            else:
                await db.commit()

        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M")
        for name, items in (("review", review_items), ("unmatched", unmatched), ("llm_decisions", decisions)):
            if items:
                path = report_dir / f"question_remap_{name}_{stamp}.json"
                path.write_text(json.dumps(items, indent=2))
                log.warning(
                    f"{name}_file_written",
                    file=str(path),
                    groups=len(items),
                    questions=sum(i["question_count"] for i in items),
                )

        log.info(
            "question_remap_summary",
            old_subtopics=len(groups),
            auto_matched_groups=auto_matched,
            llm_matched_groups=llm_matched,
            review_groups=len(review_items),
            unmatched_groups=len(unmatched),
            questions_bound=bound_total,
        )
        return 0

    except QuestionRemapError as exc:
        log.error("question_remap_aborted", reason=str(exc))
        return 1
    except Exception as exc:
        log.error("question_remap_failed", error=str(exc), exc_info=True)
        return 1
    finally:
        await engine.dispose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--snapshot", type=Path, required=True, help="question_subtopic_snapshot_<ts>.json")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    parser.add_argument("--auto-threshold", type=float, default=AUTO_BIND_THRESHOLD)
    parser.add_argument("--review-threshold", type=float, default=REVIEW_THRESHOLD)
    parser.add_argument("--report-dir", type=Path, default=_BACKEND_ROOT.parent / "backups")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM adjudication of the ambiguous band; send those groups to the review file instead.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(
        asyncio.run(
            main(
                snapshot_path=args.snapshot,
                dry_run=args.dry_run,
                auto_threshold=args.auto_threshold,
                review_threshold=args.review_threshold,
                report_dir=args.report_dir,
                use_llm=not args.no_llm,
            )
        )
    )
