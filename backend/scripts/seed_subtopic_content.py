"""
Seed script: populate subtopic_content table from the curriculum graph.

Architecture: subtopic_content resources come from THIS table (structured SQL),
NOT from pgvector/curriculum_chunks. No embedder, no retriever, no cosine similarity.

Usage:
    cd backend
    python -m scripts.seed_subtopic_content

Environment variables required:
    DATABASE_URL       — PostgreSQL connection string
    LITELLM_API_KEY     — API key for LLM calls (used directly via litellm.acompletion)
    OPENAI_API_KEY      — Alias for LITELLM_API_KEY

The seed script uses litellm.acompletion() directly (not router.complete())
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

import json
import logging
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import litellm
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Ensure app is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("seed_subtopic_content")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BATCH_SIZE = int(os.environ.get("SEED_BATCH_SIZE", "10"))
MAX_WORKERS = int(os.environ.get("SEED_MAX_WORKERS", "4"))
LITELLM_MODEL = os.environ.get("LITELLM_SEED_MODEL", "gpt-4o-mini")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() in ("1", "true", "yes")
SKIP_VIDEOS = os.environ.get("SKIP_VIDEOS", "false").lower() in ("1", "true", "yes")
SKIP_EXPLANATIONS = os.environ.get("SKIP_EXPLANATIONS", "false").lower() in (
    "1",
    "true",
    "yes",
)
SKIP_QUIZZES = os.environ.get("SKIP_QUIZZES", "false").lower() in ("1", "true", "yes")

PRE_GENERATED_QS_PATH = Path(__file__).parent.parent / "data" / "question-bank" / "pre_generated_questions.json"
CURRICULUM_PATH = Path(__file__).parent.parent / "data" / "curriculum" / "cambridge_v1.json"

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

engine = create_engine(settings.database_url, pool_pre_ping=True, echo=False)
SessionLocal = sessionmaker(bind=engine)


def get_session() -> Session:
    return SessionLocal()


# ---------------------------------------------------------------------------
# Load reference data
# ---------------------------------------------------------------------------


def load_pre_generated_questions() -> dict[str, Any]:
    """Load pre-generated questions keyed by subtopic id."""
    if not PRE_GENERATED_QS_PATH.exists():
        log.warning("Pre-generated questions file not found at %s", PRE_GENERATED_QS_PATH)
        return {}
    with open(PRE_GENERATED_QS_PATH) as f:
        data = json.load(f)
    # Index by subtopic_id (the file format may vary — adapt to actual structure)
    result: dict[str, Any] = {}
    questions_list = data if isinstance(data, list) else data.get("questions", [])
    for item in questions_list:
        subtopic_id = item.get("subtopic_id") or item.get("subtopicId")
        if subtopic_id:
            result[str(subtopic_id)] = item
    return result


def load_curriculum_subtopics() -> list[dict[str, Any]]:
    """Load all subtopics from the curriculum graph."""
    if not CURRICULUM_PATH.exists():
        log.error("Curriculum file not found at %s", CURRICULUM_PATH)
        return []
    with open(CURRICULUM_PATH) as f:
        data = json.load(f)
    # The cambridge_v1.json has subtopics nested inside strands/chapters/units
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
# LLM calls
# ---------------------------------------------------------------------------


def call_llm(prompt: str, model: str | None = None) -> dict[str, Any] | None:
    """Call LLM via litellm.acompletion (direct, not via router)."""
    actual_model = model or LITELLM_MODEL
    try:
        response = litellm.acompletion(
            model=actual_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout=60,
        )
        raw = response["choices"][0]["message"]["content"]
        return json.loads(raw)
    except Exception as e:
        log.error("LLM call failed: %s", e)
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
    return call_llm(prompt)


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
    return call_llm(prompt)


def generate_quiz_content(subtopic: dict[str, Any]) -> dict[str, Any] | None:
    """Generate practice quiz questions for a subtopic."""
    if SKIP_QUIZZES:
        return None
    prompt = QUIZ_PROMPT.format(
        subtopic_name=subtopic.get("name", ""),
        subject=subtopic.get("_strand_id", "Mathematics"),
        grade_level=subtopic.get("grade_level", "Grade 8"),
    )
    return call_llm(prompt)


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
        # Build upsert based on content type
        if rec["content_type"] == CONTENT_TYPE_VIDEO:
            # Conflict on (subtopic_id, content_type, video_url)
            constraint = "uq_subtopic_content_one_video_per_url"
            update_cols = [k for k in rec.keys() if k not in ("subtopic_id", "content_type", "video_url")]
        else:
            # Conflict on (subtopic_id, content_type) — partial, so use subtopic_id
            # We handle this by matching on subtopic_id and content_type
            # since non-videos don't have a unique video_url
            constraint = None  # will use raw SQL
            update_cols = None

        if constraint:
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
            # For non-video content, use subtopic_id + content_type as unique key
            # We need a different approach — use raw SQL with ON CONFLICT
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
# Main seed logic
# ---------------------------------------------------------------------------


def seed_subtopic(subtopic: dict[str, Any], pre_gen_qs: dict[str, Any]) -> tuple[int, int]:
    """Generate and insert content for a single subtopic. Returns (inserted, skipped)."""
    subtopic_id_str = str(subtopic.get("id") or "")
    if not subtopic_id_str:
        return 0, 0

    session = get_session()
    inserted = 0
    skipped = 0

    try:
        # --- Video ---
        if not SKIP_VIDEOS:
            video_data = generate_video_content(subtopic)
            if video_data and video_data.get("video_url"):
                rec = build_record(
                    subtopic,
                    CONTENT_TYPE_VIDEO,
                    video_data,
                    REVIEW_STATUS_APPROVED,
                    is_active=True,
                )
                if rec and upsert_subtopic_content(session, [rec]):
                    inserted += 1
            else:
                skipped += 1
        else:
            skipped += 1

        # --- Explanation ---
        if not SKIP_EXPLANATIONS:
            explanation_data = generate_explanation_content(subtopic)
            if explanation_data and explanation_data.get("explanation_text"):
                rec = build_record(
                    subtopic,
                    CONTENT_TYPE_EXPLANATION,
                    explanation_data,
                    REVIEW_STATUS_APPROVED,
                    is_active=True,
                )
                if rec and upsert_subtopic_content(session, [rec]):
                    inserted += 1
            else:
                skipped += 1
        else:
            skipped += 1

        # --- Practice Quiz ---
        if not SKIP_QUIZZES:
            # Check pre-generated questions first
            if subtopic_id_str in pre_gen_qs:
                qs_data = {"questions": pre_gen_qs[subtopic_id_str].get("questions", [])}
            else:
                qs_data = generate_quiz_content(subtopic)
            if qs_data and qs_data.get("questions"):
                rec = build_record(
                    subtopic,
                    CONTENT_TYPE_PRACTICE,
                    qs_data,
                    REVIEW_STATUS_PENDING,
                    is_active=True,
                )
                if rec and upsert_subtopic_content(session, [rec]):
                    inserted += 1
            else:
                skipped += 1
        else:
            skipped += 1

    except Exception as e:
        log.error("Error seeding subtopic %s: %s", subtopic_id_str, e)
        session.rollback()
    finally:
        session.close()

    return inserted, skipped


def main() -> None:
    log.info("=" * 60)
    log.info("Subtopic Content Seeder")
    log.info("Model: %s | Dry run: %s", LITELLM_MODEL, DRY_RUN)
    log.info("Skip videos: %s | explanations: %s | quizzes: %s", SKIP_VIDEOS, SKIP_EXPLANATIONS, SKIP_QUIZZES)
    log.info("=" * 60)

    if DRY_RUN:
        log.warning("DRY RUN — no database changes will be made")

    # Load curriculum
    subtopics = load_curriculum_subtopics()
    if not subtopics:
        log.error("No subtopics loaded — aborting")
        return

    pre_gen_qs = load_pre_generated_questions()
    log.info("Loaded %d pre-generated question sets", len(pre_gen_qs))

    total_inserted = 0
    total_skipped = 0

    if DRY_RUN:
        log.info("Dry run complete — no records were written")
        return

    # Process in batches with thread pool
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(seed_subtopic, s, pre_gen_qs): s for s in subtopics}
        for i, future in enumerate(as_completed(futures), 1):
            inserted, skipped = future.result()
            total_inserted += inserted
            total_skipped += skipped
            if i % 50 == 0 or i == len(subtopics):
                log.info(
                    "Progress: %d/%d subtopics processed | inserted: %d | skipped: %d",
                    i,
                    len(subtopics),
                    total_inserted,
                    total_skipped,
                )

    log.info("=" * 60)
    log.info(
        "SEED COMPLETE — inserted: %d | skipped: %d | total: %d",
        total_inserted,
        total_skipped,
        total_inserted + total_skipped,
    )
    log.info("=" * 60)


if __name__ == "__main__":
    main()
