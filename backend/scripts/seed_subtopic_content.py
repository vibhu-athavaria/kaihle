"""
Seed script: populate subtopic_content table from the curriculum graph.

Architecture: subtopic_content resources come from THIS table (structured SQL),
NOT from pgvector/curriculum_chunks. No embedder, no retriever, no cosine similarity.

Usage:
    cd backend
    python -m scripts.seed_subtopic_content

Environment variables required:
    DATABASE_URL       — PostgreSQL connection string
    LITELLM_API_KEY     — API key for LLM calls (used directly via litellm.completion)
    OPENAI_API_KEY      — Alias for LITELLM_API_KEY

The seed script uses litellm.completion() directly (not router.complete())
per CLAUDE.md § Direct LLM Access.

Content types generated:
    - video:     structured metadata { video_url, video_provider, video_duration_seconds,
              video_thumbnail_url } for approved YouTube videos
    - explanation: { explanation_text } — markdown explainer written by the LLM

Each subtopic gets:
    1 approved video (content_type=video, review_status=approved, is_active=true)
    1 LLM-written explanation (content_type=explanation, review_status=approved, is_active=true)
    1 practice quiz (content_type=practice, review_status=pending, is_active=true)
      — quiz questions come from pre_generated_questions.json or are generated fresh

Applicable tiers are set to [1, 2, 3] for all content during seed.
Teachers/KAIHLE_ADMIN can update applicable_tiers after review.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from itertools import islice
from pathlib import Path
from typing import Any

import litellm
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Ensure app is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.models.curriculum import QuestionBank

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("seed_subtopic_content")

# ---------------------------------------------------------------------------
# Argument parsing — must happen before config constants so CLI flags win
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(description="Seed subtopic content to database")
parser.add_argument("--limit", type=int, default=None, help="Limit number of subtopics to process (for testing)")
parser.add_argument("--dry-run", action="store_true", help="Dry run: simulate full flow without DB writes")
parser.add_argument("--skip-videos", action="store_true", help="Skip video generation")
parser.add_argument("--skip-explanations", action="store_true", help="Skip explanation generation")
parser.add_argument("--skip-quizzes", action="store_true", help="Skip quiz generation")
args = parser.parse_args()

# ---------------------------------------------------------------------------
# Config — CLI flags take priority over env vars
# ---------------------------------------------------------------------------

BATCH_SIZE = int(os.environ.get("SEED_BATCH_SIZE", "10"))
MAX_WORKERS = int(os.environ.get("SEED_MAX_WORKERS", "4"))
LITELLM_MODEL = os.environ.get("LITELLM_SEED_MODEL", "gpt-4o-mini")

# CLI flags take priority; fall back to env vars so docker/API invocations still work
DRY_RUN: bool = args.dry_run or os.environ.get("DRY_RUN", "false").lower() in ("1", "true", "yes")
SKIP_VIDEOS: bool = args.skip_videos or os.environ.get("SKIP_VIDEOS", "false").lower() in ("1", "true", "yes")
SKIP_EXPLANATIONS: bool = args.skip_explanations or os.environ.get("SKIP_EXPLANATIONS", "false").lower() in (
    "1",
    "true",
    "yes",
)
SKIP_QUIZZES: bool = args.skip_quizzes or os.environ.get("SKIP_QUIZZES", "false").lower() in ("1", "true", "yes")

CURRICULUM_PATH = Path(__file__).parent.parent / "data" / "curriculum" / "cambridge_v1.json"

# ---------------------------------------------------------------------------
# Database setup — strip asyncpg driver; sync engine requires psycopg2/pg8000
# ---------------------------------------------------------------------------


def _make_sync_db_url(url: str) -> str:
    """Replace +asyncpg with +psycopg2 so sync SQLAlchemy can connect."""
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://").replace(
        "postgres+asyncpg://", "postgresql+psycopg2://"
    )


_engine: Any = None
_SessionLocal: Any = None


def _get_engine() -> Any:
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(_make_sync_db_url(settings.database_url), pool_pre_ping=True, echo=False)
        _SessionLocal = sessionmaker(bind=_engine)
    return _engine


def get_session() -> Session:
    _get_engine()
    session: Session = _SessionLocal()  # type: ignore[misc]
    return session


# ---------------------------------------------------------------------------
# Load reference data
# ---------------------------------------------------------------------------


def load_pre_generated_questions(session: Session) -> dict[str, Any]:
    """Load pre-generated questions from question_bank keyed by subtopic id."""
    try:
        rows = session.query(QuestionBank).filter(QuestionBank.is_active.is_(True)).all()
    except Exception as e:
        log.error("Failed to load questions from question_bank: %s", e)
        return {}

    result: dict[str, Any] = {}
    for q in rows:
        subtopic_id = str(q.subtopic_id)
        if subtopic_id not in result:
            result[subtopic_id] = {"questions": []}

        options = []
        if q.options:
            for opt in q.options:
                key = opt.get("key", "") if isinstance(opt, dict) else ""
                text_val = opt.get("text", "") if isinstance(opt, dict) else ""
                options.append(f"{key}: {text_val}")

        question_entry = {
            "question_id": str(q.id),
            "question_text": q.question_text,
            "options": options,
            "correct_answer": q.correct_answer,
            "explanation": q.explanation or "",
        }
        result[subtopic_id]["questions"].append(question_entry)

    log.info("Loaded %d question sets from question_bank", len(result))
    return result


def load_curriculum_subtopics() -> list[dict[str, Any]]:
    """Load all subtopics from the curriculum graph."""
    if not CURRICULUM_PATH.exists():
        log.error("Curriculum file not found at %s", CURRICULUM_PATH)
        return []
    with open(CURRICULUM_PATH) as f:
        data = json.load(f)
    subtopics: list[dict[str, Any]] = []
    for strand in data.get("strands", []):
        for chapter in strand.get("chapters", []):
            for unit in chapter.get("units", []):
                for topic in unit.get("topics", []):
                    for subtopic in topic.get("subtopics", []):
                        subtopic["_unit_id"] = unit.get("id")
                        subtopic["_topic_id"] = topic.get("id")
                        subtopic["_chapter_id"] = chapter.get("id")
                        subtopic["_strand_id"] = strand.get("id")
                        subtopics.append(subtopic)
    log.info("Loaded %d subtopics from curriculum", len(subtopics))
    return subtopics


# ---------------------------------------------------------------------------
# LLM prompts
# ---------------------------------------------------------------------------

YOUTUBE_SEARCH_PROMPT = """You are a curriculum specialist finding educational videos.

Given the subtopic: "{subtopic_name}" (ID: {subtopic_id})
Subject: {subject}
Grade level: {grade_level}

Search YouTube for a high-quality educational video that:
- Directly explains this subtopic concept
- Is between 3 and 15 minutes long
- Is appropriate for the grade level
- Has clear audio and visuals (not a whiteboard lecture recording)

Respond with ONLY a valid JSON object, no markdown:
{{
  "video_url": "https://www.youtube.com/watch?v=XXXXXXXXXXX",
  "video_provider": "youtube",
  "video_duration_seconds": 420,
  "video_thumbnail_url": "https://img.youtube.com/vi/XXXXXXXXXXX/maxresdefault.jpg",
  "search_terms_used": "search terms you used",
  "title_candidates": ["video title 1", "video title 2"]
}}

If no suitable video is found, respond with:
{{
  "video_url": null,
  "video_provider": null,
  "video_duration_seconds": null,
  "video_thumbnail_url": null,
  "search_terms_used": "...",
  "title_candidates": []
}}
"""


EXPLANATION_PROMPT = """Write a clear, concise explanation of the subtopic below.
Target audience: students in grade {grade_level} studying {subject}.
Keep it to 150-300 words. Use simple language. Include one worked example if appropriate.

Subtopic: {subtopic_name}
Prior concepts to reference: {prerequisites}

Respond with ONLY a valid JSON object, no markdown:
{{
  "explanation_text": "your markdown explanation here..."
}}
"""


QUIZ_PROMPT = """Generate 5 multiple-choice quiz questions for the subtopic below.
Each question should:
- Test understanding of a key concept
- Have 4 options (A, B, C, D) with one correct answer
- Include a brief explanation of why the correct answer is right

Respond with ONLY a valid JSON object, no markdown:
{{
  "questions": [
    {{
      "question_id": "q1",
      "question_text": "What is...?",
      "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
      "correct_answer": "A",
      "explanation": "A is correct because..."
    }},
    ...4 more questions...
  ]
}}
"""


# ---------------------------------------------------------------------------
# LLM calls — synchronous (litellm.completion), thread-safe
# ---------------------------------------------------------------------------


def call_llm(prompt: str, model: str | None = None) -> dict[str, Any] | None:
    """Call LLM via litellm.completion (sync, direct, not via router)."""
    actual_model = model or LITELLM_MODEL
    log.debug("LLM request | model=%s | prompt_chars=%d", actual_model, len(prompt))
    try:
        response = litellm.completion(
            model=actual_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout=60,
        )
        raw = response["choices"][0]["message"]["content"]
        log.debug("LLM response | chars=%d | snippet=%.120s", len(raw), raw)
        parsed: dict[str, Any] = json.loads(raw)
        return parsed
    except Exception as e:
        log.error("LLM call failed | model=%s | error=%s", actual_model, e)
        return None


# ---------------------------------------------------------------------------
# Content generation per subtopic
# ---------------------------------------------------------------------------


def generate_video_content(subtopic: dict[str, Any]) -> dict[str, Any] | None:
    """Generate video metadata for a subtopic."""
    if SKIP_VIDEOS:
        return None
    prompt = YOUTUBE_SEARCH_PROMPT.format(
        subtopic_name=subtopic.get("name", ""),
        subtopic_id=subtopic.get("id", ""),
        subject=subtopic.get("_strand_id", "Mathematics"),
        grade_level=subtopic.get("grade_level", "Grade 8"),
    )
    result = call_llm(prompt)
    log.info(
        "video_gen | subtopic=%s | found=%s",
        subtopic.get("name", ""),
        bool(result and result.get("video_url")),
    )
    return result


def generate_explanation_content(subtopic: dict[str, Any]) -> dict[str, Any] | None:
    """Generate an LLM-written explanation for a subtopic."""
    if SKIP_EXPLANATIONS:
        return None
    prerequisites = ", ".join(p.get("name", "") for p in subtopic.get("prerequisites", [])[:3])
    prompt = EXPLANATION_PROMPT.format(
        subtopic_name=subtopic.get("name", ""),
        subject=subtopic.get("_strand_id", "Mathematics"),
        grade_level=subtopic.get("grade_level", "Grade 8"),
        prerequisites=prerequisites or "basic arithmetic",
    )
    result = call_llm(prompt)
    chars = len(result.get("explanation_text", "")) if result else 0
    log.info("explanation_gen | subtopic=%s | chars=%d", subtopic.get("name", ""), chars)
    return result


def generate_quiz_content(subtopic: dict[str, Any]) -> dict[str, Any] | None:
    """Generate practice quiz questions for a subtopic."""
    if SKIP_QUIZZES:
        return None
    prompt = QUIZ_PROMPT.format(
        subtopic_name=subtopic.get("name", ""),
        subject=subtopic.get("_strand_id", "Mathematics"),
        grade_level=subtopic.get("grade_level", "Grade 8"),
    )
    result = call_llm(prompt)
    q_count = len(result.get("questions", [])) if result else 0
    log.info("quiz_gen | subtopic=%s | questions=%d", subtopic.get("name", ""), q_count)
    return result


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

CONTENT_TYPE_VIDEO = "video"
CONTENT_TYPE_EXPLANATION = "explanation"
CONTENT_TYPE_PRACTICE = "practice"
REVIEW_STATUS_APPROVED = "approved"
REVIEW_STATUS_PENDING = "pending"


def upsert_subtopic_content(session: Session, records: list[dict[str, Any]]) -> int:
    """Insert or update subtopic_content records.

    Uses INSERT ... ON CONFLICT DO UPDATE (upsert) so re-running the seed
    is idempotent.  Conflicts are identified by (subtopic_id, content_type, video_url)
    for videos and (subtopic_id, content_type) for non-videos.
    """
    if not records:
        return 0
    inserted = 0
    for rec in records:
        if rec["content_type"] == CONTENT_TYPE_VIDEO:
            constraint = "uq_subtopic_content_one_video_per_url"
            update_cols = [k for k in rec.keys() if k not in ("subtopic_id", "content_type", "video_url")]
        else:
            constraint = None
            update_cols = None

        if constraint and update_cols is not None:
            set_clause = ", ".join(f"{k} = EXCLUDED.{k}" for k in update_cols)
            sql = text(f"""
                INSERT INTO subtopic_content (id, subtopic_id, content_type, is_active,
                    applicable_tiers, review_status, is_stale, is_archived,
                    created_at, updated_at,
                    video_url, video_provider, video_duration_seconds, video_thumbnail_url,
                    explanation_text, quiz_questions, quiz_questions_count,
                    teacher_explanation, teacher_explanation_author_id,
                    interest_category_id, reviewed_at, reviewed_by_id, rejection_reason)
                VALUES (
                    :id, :subtopic_id, :content_type::content_type_enum, :is_active,
                    :applicable_tiers, :review_status::review_status_enum, :is_stale, :is_archived,
                    :created_at, :updated_at,
                    :video_url, :video_provider, :video_duration_seconds, :video_thumbnail_url,
                    :explanation_text, :quiz_questions, :quiz_questions_count,
                    :teacher_explanation, :teacher_explanation_author_id,
                    :interest_category_id, :reviewed_at, :reviewed_by_id, :rejection_reason
                )
                ON CONFLICT (subtopic_id, content_type, video_url)
                DO UPDATE SET
                    {set_clause},
                    updated_at = NOW()
                WHERE subtopic_content.subtopic_id = :subtopic_id
                  AND subtopic_content.content_type = :content_type::content_type_enum
                  AND subtopic_content.video_url = :video_url
            """)
        else:
            sql = text("""
                INSERT INTO subtopic_content (id, subtopic_id, content_type, is_active,
                    applicable_tiers, review_status, is_stale, is_archived,
                    created_at, updated_at,
                    video_url, video_provider, video_duration_seconds, video_thumbnail_url,
                    explanation_text, quiz_questions, quiz_questions_count,
                    teacher_explanation, teacher_explanation_author_id,
                    interest_category_id, reviewed_at, reviewed_by_id, rejection_reason)
                VALUES (
                    :id, :subtopic_id, :content_type::content_type_enum, :is_active,
                    :applicable_tiers, :review_status::review_status_enum, :is_stale, :is_archived,
                    :created_at, :updated_at,
                    :video_url, :video_provider, :video_duration_seconds, :video_thumbnail_url,
                    :explanation_text, :quiz_questions, :quiz_questions_count,
                    :teacher_explanation, :teacher_explanation_author_id,
                    :interest_category_id, :reviewed_at, :reviewed_by_id, :rejection_reason
                )
                ON CONFLICT (subtopic_id, content_type)
                DO UPDATE SET
                    is_active = EXCLUDED.is_active,
                    applicable_tiers = EXCLUDED.applicable_tiers,
                    review_status = EXCLUDED.review_status,
                    explanation_text = EXCLUDED.explanation_text,
                    quiz_questions = EXCLUDED.quiz_questions,
                    quiz_questions_count = EXCLUDED.quiz_questions_count,
                    updated_at = NOW()
                WHERE subtopic_content.subtopic_id = :subtopic_id
                  AND subtopic_content.content_type = :content_type::content_type_enum
            """)

        try:
            session.execute(sql, rec)
            inserted += 1
        except Exception as e:
            log.error("Failed to upsert content for subtopic %s: %s", rec.get("subtopic_id"), e)
    session.commit()
    return inserted


def build_record(
    subtopic: dict[str, Any],
    content_type: str,
    data: dict[str, Any] | None,
    review_status: str,
    is_active: bool,
) -> dict[str, Any] | None:
    """Build a subtopic_content record dict from LLM output."""
    if data is None:
        return None
    now = datetime.now(UTC)
    record_id = uuid.uuid4()
    subtopic_id_str = str(subtopic.get("id") or "")
    if not subtopic_id_str:
        return None

    base = {
        "id": record_id,
        "subtopic_id": uuid.UUID(subtopic_id_str),
        "content_type": content_type,
        "is_active": is_active,
        "applicable_tiers": [1, 2, 3],
        "review_status": review_status,
        "is_stale": False,
        "is_archived": False,
        "created_at": now,
        "updated_at": now,
        "video_url": None,
        "video_provider": None,
        "video_duration_seconds": None,
        "video_thumbnail_url": None,
        "explanation_text": None,
        "quiz_questions": None,
        "quiz_questions_count": None,
        "teacher_explanation": None,
        "teacher_explanation_author_id": None,
        "interest_category_id": None,
        "reviewed_at": now if review_status != REVIEW_STATUS_PENDING else None,
        "reviewed_by_id": None,
        "rejection_reason": None,
    }

    if content_type == CONTENT_TYPE_VIDEO:
        base["video_url"] = data.get("video_url")
        base["video_provider"] = data.get("video_provider")
        base["video_duration_seconds"] = data.get("video_duration_seconds")
        base["video_thumbnail_url"] = data.get("video_thumbnail_url")
    elif content_type == CONTENT_TYPE_EXPLANATION:
        base["explanation_text"] = data.get("explanation_text")
    elif content_type == CONTENT_TYPE_PRACTICE:
        questions = data.get("questions", [])
        base["quiz_questions"] = questions
        base["quiz_questions_count"] = len(questions)

    return base


# ---------------------------------------------------------------------------
# Per-subtopic seed logic
# ---------------------------------------------------------------------------


class SeedResult:
    """Outcome for a single subtopic seed attempt."""

    def __init__(self, subtopic_id: str, subtopic_name: str) -> None:
        self.subtopic_id = subtopic_id
        self.subtopic_name = subtopic_name
        self.inserted = 0
        self.skipped = 0
        self.errors: list[str] = []

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    @property
    def failed(self) -> bool:
        return bool(self.errors)


def seed_subtopic(subtopic: dict[str, Any], pre_gen_qs: dict[str, Any], dry_run: bool = False) -> SeedResult:
    """Generate and insert content for a single subtopic."""
    subtopic_id_str = str(subtopic.get("id") or "")
    subtopic_name = subtopic.get("name", "<unknown>")
    result = SeedResult(subtopic_id_str, subtopic_name)

    if not subtopic_id_str:
        result.add_error("missing subtopic id")
        return result

    log.info("seeding | subtopic=%s | id=%s | dry_run=%s", subtopic_name, subtopic_id_str, dry_run)

    session = get_session() if not dry_run else None

    try:
        # --- Video ---
        if not SKIP_VIDEOS:
            video_data = generate_video_content(subtopic)
            if video_data and video_data.get("video_url"):
                rec = build_record(subtopic, CONTENT_TYPE_VIDEO, video_data, REVIEW_STATUS_APPROVED, is_active=True)
                if dry_run:
                    log.info(
                        "[DRY RUN] would insert video | subtopic=%s | url=%s",
                        subtopic_name,
                        video_data.get("video_url"),
                    )
                    result.inserted += 1
                elif rec and session and upsert_subtopic_content(session, [rec]):
                    result.inserted += 1
            else:
                log.info("no video found | subtopic=%s", subtopic_name)
                result.skipped += 1
        else:
            result.skipped += 1

        # --- Explanation ---
        if not SKIP_EXPLANATIONS:
            explanation_data = generate_explanation_content(subtopic)
            if explanation_data and explanation_data.get("explanation_text"):
                rec = build_record(
                    subtopic, CONTENT_TYPE_EXPLANATION, explanation_data, REVIEW_STATUS_APPROVED, is_active=True
                )
                if dry_run:
                    log.info(
                        "[DRY RUN] would insert explanation | subtopic=%s | chars=%d",
                        subtopic_name,
                        len(explanation_data.get("explanation_text", "")),
                    )
                    result.inserted += 1
                elif rec and session and upsert_subtopic_content(session, [rec]):
                    result.inserted += 1
            else:
                log.info("no explanation generated | subtopic=%s", subtopic_name)
                result.skipped += 1
        else:
            result.skipped += 1

        # --- Practice Quiz ---
        if not SKIP_QUIZZES:
            if subtopic_id_str in pre_gen_qs:
                pre_qs: list[Any] = pre_gen_qs[subtopic_id_str].get("questions", [])
                qs_data: dict[str, Any] | None = {"questions": pre_qs}
                log.info("using pre-generated questions | subtopic=%s | count=%d", subtopic_name, len(pre_qs))
            else:
                qs_data = generate_quiz_content(subtopic)
            if qs_data and qs_data.get("questions"):
                rec = build_record(subtopic, CONTENT_TYPE_PRACTICE, qs_data, REVIEW_STATUS_PENDING, is_active=True)
                if dry_run:
                    log.info(
                        "[DRY RUN] would insert quiz | subtopic=%s | questions=%d",
                        subtopic_name,
                        len(qs_data.get("questions", [])),
                    )
                    result.inserted += 1
                elif rec and session and upsert_subtopic_content(session, [rec]):
                    result.inserted += 1
            else:
                log.info("no quiz generated | subtopic=%s", subtopic_name)
                result.skipped += 1
        else:
            result.skipped += 1

    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        log.error("seed failed | subtopic=%s | error=%s", subtopic_name, msg)
        result.add_error(msg)
        if session:
            session.rollback()
    finally:
        if session:
            session.close()

    return result


# ---------------------------------------------------------------------------
# Batching helper
# ---------------------------------------------------------------------------


def _batches(items: list[Any], size: int) -> Generator[list[Any], None, None]:
    """Yield successive chunks of `size` from `items`."""
    it = iter(items)
    while True:
        batch = list(islice(it, size))
        if not batch:
            break
        yield batch


# ---------------------------------------------------------------------------
# Main seed logic
# ---------------------------------------------------------------------------


def main() -> None:
    log.info("=" * 60)
    log.info("Subtopic Content Seeder")
    log.info("Model: %s | Dry run: %s", LITELLM_MODEL, DRY_RUN)
    log.info(
        "Skip videos: %s | explanations: %s | quizzes: %s",
        SKIP_VIDEOS,
        SKIP_EXPLANATIONS,
        SKIP_QUIZZES,
    )
    log.info("Batch size: %d | Workers: %d", BATCH_SIZE, MAX_WORKERS)
    log.info("=" * 60)

    if DRY_RUN:
        log.warning("DRY RUN — LLM calls will be made but no DB writes will occur")

    # Load curriculum
    subtopics = load_curriculum_subtopics()
    if not subtopics:
        log.error("No subtopics loaded — aborting")
        return

    if args.limit:
        subtopics = subtopics[: args.limit]
        log.info("Limited to %d subtopics", args.limit)

    # Load pre-generated questions (skip DB in dry-run)
    if DRY_RUN:
        pre_gen_qs: dict[str, Any] = {}
        log.info("[DRY RUN] skipping question_bank load")
    else:
        session = get_session()
        try:
            pre_gen_qs = load_pre_generated_questions(session)
        finally:
            session.close()

    total_inserted = 0
    total_skipped = 0
    failed_subtopics: list[SeedResult] = []

    # Process in batches
    for batch_num, batch in enumerate(_batches(subtopics, BATCH_SIZE), 1):
        log.info("--- Batch %d | subtopics %d", batch_num, len(batch))
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(seed_subtopic, s, pre_gen_qs, DRY_RUN): s for s in batch}
            for future in as_completed(futures):
                seed_result = future.result()
                total_inserted += seed_result.inserted
                total_skipped += seed_result.skipped
                if seed_result.failed:
                    failed_subtopics.append(seed_result)

        log.info(
            "Batch %d done | cumulative: inserted=%d skipped=%d failed=%d",
            batch_num,
            total_inserted,
            total_skipped,
            len(failed_subtopics),
        )

    # Final summary
    log.info("=" * 60)
    log.info(
        "SEED COMPLETE — inserted: %d | skipped: %d | failed: %d | total: %d",
        total_inserted,
        total_skipped,
        len(failed_subtopics),
        total_inserted + total_skipped + len(failed_subtopics),
    )

    if failed_subtopics:
        log.warning("FAILED SUBTOPICS (%d):", len(failed_subtopics))
        for r in failed_subtopics:
            log.warning("  - %s (%s): %s", r.subtopic_name, r.subtopic_id, "; ".join(r.errors))

    log.info("=" * 60)


if __name__ == "__main__":
    main()
