"""Deactivates English Language questions that test factual history or science knowledge
instead of language skills.

Root cause: LLM question generation used WWI/WWII/French Revolution as reading
passage *context*, but generated questions that test historical recall (e.g.
"Which event marked the beginning of WWII?") rather than English language skills
(inference, author intent, text analysis). These produce false-positives for
history-literate students on ENG diagnostics.

Discovery strategy:
  Primary   — match by UUID (fast, exact). Works on the database where questions
               were originally generated (typically dev/staging).
  Fallback   — match by keyword pattern in question_text (works on any DB, including
               prod where UUIDs differ). Requires human review via --dry-run first.

Action: soft-deactivation (is_active = false). Hard DELETE is blocked by the
ON DELETE RESTRICT FK on student_responses / assessment_selected_questions.

Safe to run multiple times — idempotent. Already-deactivated rows are a no-op.
Verified: zero student_responses reference these questions as of 2026-05-16.

Usage:
    # Dry run first — ALWAYS review before writing to prod
    python -m scripts.deactivate_misclassified_eng_questions --dry-run

    # Run for real once you've confirmed the dry-run matches look correct
    python -m scripts.deactivate_misclassified_eng_questions

    # On prod (UUIDs differ from dev — uses keyword fallback automatically)
    python -m scripts.deactivate_misclassified_eng_questions --dry-run
    python -m scripts.deactivate_misclassified_eng_questions
"""

import argparse
import asyncio
import sys
from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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

# ── Primary: UUIDs from the dev/staging database (2026-05-16 audit) ──────────
# These only match on the DB where questions were originally generated.
# On prod, the fallback keyword query is used instead.
MISCLASSIFIED_QUESTION_IDS: list[str] = [
    # Argumentative and Persuasive Writing
    "1ee4db7d-d682-4b3f-a6e2-19d1502584bd",
    # Comprehension and Inference (7 questions)
    "c54f0bc3-87a3-42a5-80b7-b561a1a3fa99",
    "64d748d3-4970-48f6-96b9-0f16f959234e",
    "15bef4d3-0760-419a-902f-dca9b057fdc2",
    "14268e95-3ffd-4747-a7ad-0caaff84b1de",
    "3a449761-484d-4e1a-a384-09055b335018",
    "d1252c4b-57f6-4325-af5e-ffaf772f17b6",
    "1ba50036-f327-4edd-a806-c347bf4e7007",
    # Critical Textual Analysis (9 questions)
    "0eda1b95-f76a-47bf-ae2f-efc819e66709",
    "03698271-a7ef-42d1-b7cf-80dfdf5cab32",
    "b1803adf-a836-4b1a-bf86-7748abbd338b",
    "3549f379-898e-4f95-9342-91aecf05e28c",
    "83987dc7-9ff4-4823-9097-1f9a200c5e41",
    "b4b8a104-9735-4eb1-9720-14122b6aef3c",
    "523bd4da-f84e-4aed-8cbf-a6f17414c967",
    "5fd71338-7bb2-4367-b50e-163344c0734c",
    "b10da246-99ec-40b3-abdc-5f253843f077",
    "7813a203-c9b6-42e2-a65b-c6840b981a89",
    # Cross-Text Synthesis (2 questions)
    "738a1d57-f028-4a74-a0a3-d329425208cd",
    "b06f5956-6eaf-4cb5-959b-85493f6c66be",
    # Inference and Interpretation (4 questions)
    "d96281a5-776e-4688-8d17-1c5f83eac358",
    "8ac8e484-28b9-4684-9bb6-a7df5ef9f0f5",
    "0b4ebb96-0ba5-4131-92f7-79fe0f422a1e",
    "1d6eb514-66df-4aa7-b2e2-a3439f12084d",
    # Reading for Explicit Meaning (8 questions)
    "430ced3a-1c86-4933-8989-758df64c7b32",
    "8d9acc10-815f-4b99-a4ff-a77503527e9b",
    "412c7fcb-4f52-41ab-9481-329c5350f74e",
    "2a665c59-0204-42d4-a4c2-b960c07a9e01",
    "d16ce3a8-564e-4928-baaa-43dda62fec5a",
    "10a9c7ac-6ac8-4cd1-ab65-517e2000a955",
    "7f9146ff-34e6-4ece-9a26-c43e073f74ae",
    "47deb376-5934-4b1d-917a-b606eefe9f4a",
]

# ── Fallback: keyword patterns that identify misclassified ENG questions ──────
# Used when zero UUIDs match (i.e. on prod or any DB with different UUIDs).
# Matches active ENG questions whose question_text contains any of these phrases.
# Scoped to ENG subject only to avoid false positives in history/science subjects.
HISTORY_KEYWORDS: list[str] = [
    "world war",
    "french revolution",
    "treaty of versailles",
    "league of nations",
    "marshall plan",
    "magna carta",
    "the enlightenment",
    "cold war",
    "allied powers",
    "yalta conference",
    "nazi",
    "renaissance",
    "roman empire",
    "black death",
    "declaration of independence",
    "industrial revolution",
]

SCIENCE_KEYWORDS: list[str] = [
    "photosynthesis",
    "mitosis",
    "meiosis",
    "periodic table",
    "newton's law",
    "chemical equation",
    "atomic number",
    "dna strand",
    "rna strand",
]


async def find_by_keywords(db) -> list:
    """Find active ENG questions that contain history or science keywords.

    Scoped to the ENG subject only. Returns rows for human review.
    """
    # Build ILIKE conditions for each keyword
    history_conditions = " OR ".join(
        f"qb.question_text ILIKE '%' || :hist_{i} || '%'" for i in range(len(HISTORY_KEYWORDS))
    )
    science_conditions = " OR ".join(
        f"qb.question_text ILIKE '%' || :sci_{i} || '%'" for i in range(len(SCIENCE_KEYWORDS))
    )

    params: dict = {}
    for i, kw in enumerate(HISTORY_KEYWORDS):
        params[f"hist_{i}"] = kw
    for i, kw in enumerate(SCIENCE_KEYWORDS):
        params[f"sci_{i}"] = kw

    rows = await db.execute(
        text(f"""
            SELECT qb.id, st.name AS subtopic, qb.is_active,
                   LEFT(qb.question_text, 120) AS preview
            FROM question_bank qb
            JOIN subtopics st       ON st.id = qb.subtopic_id
            JOIN curriculum_topics ct ON ct.id = st.curriculum_topic_id
            JOIN subjects s         ON s.id = ct.subject_id
            WHERE s.code = 'ENG'
              AND qb.is_active = true
              AND ({history_conditions} OR {science_conditions})
            ORDER BY st.name, qb.id
        """),
        params,
    )
    return rows.fetchall()


async def run(dry_run: bool) -> int:
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with async_session() as db:
            async with db.begin():
                log.info(
                    "deactivate_misclassified_eng_start",
                    total_uuid_candidates=len(MISCLASSIFIED_QUESTION_IDS),
                    dry_run=dry_run,
                )

                # ── Step 1: Try UUID match ────────────────────────────────────
                rows = await db.execute(
                    text("""
                        SELECT qb.id, st.name AS subtopic, qb.is_active,
                               LEFT(qb.question_text, 120) AS preview
                        FROM question_bank qb
                        JOIN subtopics st ON st.id = qb.subtopic_id
                        WHERE qb.id = ANY(:ids)
                        ORDER BY st.name, qb.id
                    """),
                    {"ids": MISCLASSIFIED_QUESTION_IDS},
                )
                found_rows = rows.fetchall()

                if found_rows:
                    strategy = "uuid"
                    log.info(
                        "uuid_match_succeeded",
                        found=len(found_rows),
                        missing=len(MISCLASSIFIED_QUESTION_IDS) - len(found_rows),
                    )
                else:
                    # ── Step 2: Fallback — keyword match ──────────────────────
                    log.info(
                        "uuid_match_found_nothing — falling back to keyword search",
                        hint="This is expected on prod (UUIDs differ from dev)",
                    )
                    strategy = "keyword"
                    found_rows = await find_by_keywords(db)
                    log.info("keyword_match_found", count=len(found_rows))

                already_inactive = [r for r in found_rows if not r.is_active]
                to_deactivate = [r for r in found_rows if r.is_active]

                log.info(
                    "pre_deactivation_summary",
                    strategy=strategy,
                    found=len(found_rows),
                    already_inactive=len(already_inactive),
                    will_deactivate=len(to_deactivate),
                )

                if not to_deactivate:
                    log.info("nothing_to_deactivate — all matching questions already inactive or none found")
                    return 0

                # ── Step 3: Verify no student responses reference these ────────
                target_ids = [str(r.id) for r in to_deactivate]
                result = await db.execute(
                    text("SELECT COUNT(*) FROM student_responses WHERE question_id = ANY(:ids)"),
                    {"ids": target_ids},
                )
                response_count = result.scalar()
                if response_count > 0:
                    log.warning(
                        "student_responses_found",
                        count=response_count,
                        action="proceeding_with_deactivation_only — student history preserved",
                    )

                # ── Step 4: Log each question that will be deactivated ────────
                for row in to_deactivate:
                    log.info(
                        "will_deactivate" if dry_run else "deactivating",
                        subtopic=row.subtopic,
                        question_id=str(row.id),
                        preview=row.preview,
                    )

                if dry_run:
                    log.info(
                        "dry_run_complete — no changes written",
                        strategy=strategy,
                        would_deactivate=len(to_deactivate),
                    )
                    if strategy == "keyword":
                        log.info(
                            "review_required",
                            message=(
                                "Keyword matches require human review. "
                                "Check each 'will_deactivate' entry above — confirm every question "
                                "tests historical/scientific facts rather than an English language skill. "
                                "Remove any false positives before running without --dry-run."
                            ),
                        )
                    return 0

                # ── Step 5: Deactivate ────────────────────────────────────────
                result = await db.execute(
                    text("""
                        UPDATE question_bank
                        SET is_active = false, updated_at = now()
                        WHERE id = ANY(:ids) AND is_active = true
                    """),
                    {"ids": target_ids},
                )
                deactivated = result.rowcount
                log.info("deactivated", count=deactivated, strategy=strategy)

                # ── Step 6: Verify ────────────────────────────────────────────
                verify = await db.execute(
                    text("SELECT COUNT(*) FROM question_bank WHERE id = ANY(:ids) AND is_active = true"),
                    {"ids": target_ids},
                )
                still_active = verify.scalar()
                if still_active > 0:
                    log.error("verification_failed", still_active=still_active)
                    raise RuntimeError(f"{still_active} questions still active after update — rolling back")

                log.info(
                    "deactivation_complete",
                    deactivated=deactivated,
                    already_were_inactive=len(already_inactive),
                    student_responses_affected=response_count,
                    strategy=strategy,
                )

    except Exception as exc:
        log.error("script_failed", error=str(exc), exc_info=True)
        await engine.dispose()
        return 1
    finally:
        await engine.dispose()

    return 0


async def main(dry_run: bool) -> int:
    return await run(dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Deactivate ENG questions that test historical or scientific facts rather than "
            "language skills.\n\n"
            "Automatically tries UUID match first (fast, exact — works on dev/staging).\n"
            "Falls back to keyword search if no UUIDs match (works on prod).\n\n"
            "Always run with --dry-run first and review the output before writing to prod."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deactivated without writing to the database.",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(dry_run=args.dry_run)))
