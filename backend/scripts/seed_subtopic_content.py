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
import asyncio
import json
import logging
import os
import re
import sys
import unicodedata
import uuid
from collections.abc import Coroutine, Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from itertools import islice
from pathlib import Path
from typing import Any

import litellm
from googleapiclient.discovery import build as yt_build  # type: ignore[import-untyped]
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text

# Ensure app is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.database import CeleryAsyncSessionLocal
from app.models.curriculum import CurriculumTopic, Grade, QuestionBank, Subject, Subtopic

# ---------------------------------------------------------------------------
# LLM output validation schemas (Pydantic v2)
# ---------------------------------------------------------------------------

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _is_clean_text(text: str) -> bool:
    """Return False if text contains control characters or excessive non-Latin Unicode."""
    if _CONTROL_CHAR_RE.search(text):
        return False
    non_printable = sum(1 for c in text if unicodedata.category(c) in ("Cc", "Cf", "Cs", "Co", "Cn"))
    return non_printable / max(len(text), 1) < 0.05


class _QuizQuestion(BaseModel):
    question_id: str
    question_text: str = Field(..., min_length=10)
    options: list[str] = Field(..., min_length=4, max_length=4)
    correct_answer: str
    explanation: str = Field(default="")
    difficulty_level: int = Field(..., ge=1, le=5)

    @field_validator("correct_answer")
    @classmethod
    def _valid_answer_key(cls, v: str) -> str:
        if v.upper() not in ("A", "B", "C", "D"):
            raise ValueError(f"correct_answer must be A/B/C/D, got {v!r}")
        return v.upper()

    @field_validator("question_text", "explanation")
    @classmethod
    def _clean(cls, v: str) -> str:
        if v and not _is_clean_text(v):
            raise ValueError("field contains control/garbage characters")
        return v


class _QuizOutput(BaseModel):
    questions: list[_QuizQuestion] = Field(..., min_length=1)


class _ExplanationOutput(BaseModel):
    explanation_text: str = Field(..., min_length=50)

    @field_validator("explanation_text")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("explanation_text is empty")
        if not _is_clean_text(v):
            raise ValueError("explanation_text contains control/garbage characters")
        return v


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
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
parser.add_argument(
    "--grade",
    type=int,
    default=None,
    help="Only process subtopics for this grade level (e.g. --grade 8)",
)
parser.add_argument(
    "--subject",
    type=str,
    default=None,
    help="Only process subtopics for this subject name (e.g. --subject Mathematics)",
)
parser.add_argument(
    "--list",
    action="store_true",
    help="List all available grades and subjects in the DB, then exit",
)
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


# ---------------------------------------------------------------------------
# Database helpers — async session via CeleryAsyncSessionLocal (NullPool)
# ---------------------------------------------------------------------------


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine from sync context (thread-safe, no shared loop)."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Load reference data
# ---------------------------------------------------------------------------


async def _load_pre_generated_questions_async() -> dict[str, Any]:
    async with CeleryAsyncSessionLocal() as session:
        try:
            result = await session.execute(select(QuestionBank).where(QuestionBank.is_active.is_(True)))
            rows = result.scalars().all()
        except Exception as e:
            log.error("Failed to load questions from question_bank: %s", e)
            return {}

    out: dict[str, Any] = {}
    for q in rows:
        subtopic_id = str(q.subtopic_id)
        if subtopic_id not in out:
            out[subtopic_id] = {"questions": []}

        options = []
        if q.options:
            for opt in q.options:
                key = opt.get("key", "") if isinstance(opt, dict) else ""
                text_val = opt.get("text", "") if isinstance(opt, dict) else ""
                options.append(f"{key}: {text_val}")

        out[subtopic_id]["questions"].append(
            {
                "question_id": str(q.id),
                "question_text": q.question_text,
                "options": options,
                "correct_answer": q.correct_answer,
                "explanation": q.explanation or "",
            }
        )

    log.info("Loaded %d question sets from question_bank", len(out))
    return out


def load_pre_generated_questions() -> dict[str, Any]:
    return run_async(_load_pre_generated_questions_async())


async def _load_curriculum_subtopics_async(
    grade_level: int | None = None,
    subject_name: str | None = None,
) -> list[dict[str, Any]]:
    async with CeleryAsyncSessionLocal() as session:
        try:
            stmt = (
                select(
                    Subtopic,
                    Subject.name.label("subject_name"),
                    Grade.name.label("grade_name"),
                    Grade.level.label("grade_level"),
                )
                .join(CurriculumTopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
                .join(Subject, CurriculumTopic.subject_id == Subject.id)
                .join(Grade, CurriculumTopic.grade_id == Grade.id)
                .where(CurriculumTopic.is_active.is_(True))
            )
            if grade_level is not None:
                stmt = stmt.where(Grade.level == grade_level)
            if subject_name is not None:
                stmt = stmt.where(Subject.name.ilike(subject_name))
            stmt = stmt.order_by(Grade.level, Subject.name, Subtopic.name)
            result = await session.execute(stmt)
            rows = result.all()
        except Exception as e:
            log.error("Failed to load subtopics from DB: %s", e)
            return []

    subtopics: list[dict[str, Any]] = []
    for row in rows:
        subtopic = row[0]
        subtopics.append(
            {
                "id": str(subtopic.id),
                "name": subtopic.name,
                "description": subtopic.description or "",
                "learning_objective": subtopic.learning_objective,
                "grade_level": f"Grade {row.grade_level}",
                "prerequisites": [],
                "_strand_id": row.subject_name,
                "_grade_name": row.grade_name,
            }
        )

    log.info("Loaded %d subtopics from database", len(subtopics))
    return subtopics


async def _list_grades_and_subjects_async() -> None:
    async with CeleryAsyncSessionLocal() as session:
        grade_rows = (await session.execute(select(Grade.level, Grade.name).order_by(Grade.level))).all()
        subject_rows = (await session.execute(select(Subject.name).order_by(Subject.name))).all()

    print("\nAvailable grades:")
    for level, name in grade_rows:
        print(f"  --grade {level:<3}  ({name})")

    print("\nAvailable subjects:")
    for (name,) in subject_rows:
        print(f'  --subject "{name}"')
    print()


def list_grades_and_subjects() -> None:
    run_async(_list_grades_and_subjects_async())


def load_curriculum_subtopics(grade_level: int | None = None, subject_name: str | None = None) -> list[dict[str, Any]]:
    return run_async(_load_curriculum_subtopics_async(grade_level=grade_level, subject_name=subject_name))


# ---------------------------------------------------------------------------
# LLM prompts
# ---------------------------------------------------------------------------

YOUTUBE_CANDIDATES_PER_REGION = 10  # search results fetched per region
YOUTUBE_TOP_N = 3
YOUTUBE_REGIONS = ["US", "GB", "AU"]  # bias search toward English-speaking creators
# Only keep videos from channels explicitly set to these countries.
# Channels with no country set are also kept (many US/UK creators leave it blank).
YOUTUBE_ALLOWED_CHANNEL_COUNTRIES = {"US", "GB", "AU", "CA", "NZ"}


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


QUIZ_PROMPT = """Generate 5 multiple-choice quiz questions for the following subtopic.
Subtopic: {subtopic_name}
Subject: {subject}
Grade level: {grade_level}

Each question should:
- Test understanding of a key concept specific to this subtopic
- Have exactly 4 options labelled A, B, C, D — one correct answer
- Include a brief explanation of why the correct answer is right
- Include a difficulty_level integer from 1 (easy recall) to 5 (hard application/analysis),
  appropriate for the grade level. Vary difficulty across the 5 questions.

Respond with ONLY a valid JSON object, no markdown, no extra keys:
{{
  "questions": [
    {{
      "question_id": "q1",
      "question_text": "What is...?",
      "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
      "correct_answer": "A",
      "explanation": "A is correct because...",
      "difficulty_level": 2
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


def _iso8601_duration_to_seconds(duration: str) -> int:
    """Convert ISO 8601 duration (PT4M13S) to total seconds."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not m:
        return 0
    h, mn, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mn * 60 + s


def _search_region(yt: Any, query: str, region: str) -> list[str]:
    """Return video IDs from a single region search (recently uploaded, medium duration)."""
    try:
        resp = (
            yt.search()
            .list(
                q=query,
                part="id",
                type="video",
                videoDuration="medium",  # 4–20 min per YouTube's own filter
                order="date",
                maxResults=YOUTUBE_CANDIDATES_PER_REGION,
                regionCode=region,
                relevanceLanguage="en",
                safeSearch="strict",
            )
            .execute()
        )
        return [item["id"]["videoId"] for item in resp.get("items", [])]
    except Exception as e:
        log.warning("youtube_search region=%s failed: %s", region, e)
        return []


def search_youtube_videos(subtopic: dict[str, Any]) -> list[dict[str, Any]]:
    """Search YouTube across US/GB/AU, rank by engagement, return top YOUTUBE_TOP_N.

    Steps:
      1. search.list × 3 regions — collect up to 30 candidate IDs (deduplicated)
      2. videos.list — fetch statistics + contentDetails in one batch call
      3. channels.list — fetch channel countries in one batch call
      4. Filter: drop non-allowed channel countries, drop out-of-range durations,
         rank by likes + 0.1×views, return top YOUTUBE_TOP_N
    """
    api_key = settings.youtube_data_api_key
    if not api_key:
        log.warning("YOUTUBE_DATA_API_KEY not set — skipping video search for %s", subtopic.get("name"))
        return []

    name = subtopic.get("name", "")
    subject = subtopic.get("_strand_id", "Mathematics")
    grade = subtopic.get("grade_level", "Grade 8")
    query = f"{name} {subject} {grade} explained tutorial"

    try:
        yt = yt_build("youtube", "v3", developerKey=api_key, cache_discovery=False)

        # Step 1: search all three regions, deduplicate preserving order
        seen: set[str] = set()
        video_ids: list[str] = []
        for region in YOUTUBE_REGIONS:
            for vid_id in _search_region(yt, query, region):
                if vid_id not in seen:
                    seen.add(vid_id)
                    video_ids.append(vid_id)

        if not video_ids:
            log.info("youtube_search | no results | subtopic=%s | query=%s", name, query)
            return []

        # Step 2: fetch stats + duration for all candidates in one call
        stats_resp = (
            yt.videos()
            .list(
                id=",".join(video_ids),
                part="id,snippet,statistics,contentDetails",
            )
            .execute()
        )

        # Step 3: fetch channel countries in one batch call, build an allow-set
        channel_ids = list({item["snippet"]["channelId"] for item in stats_resp.get("items", [])})
        channel_country: dict[str, str | None] = {}
        if channel_ids:
            ch_resp = (
                yt.channels()
                .list(
                    id=",".join(channel_ids),
                    part="id,snippet",
                )
                .execute()
            )
            for ch in ch_resp.get("items", []):
                channel_country[ch["id"]] = ch.get("snippet", {}).get("country") or None

        # Step 4: filter by duration + channel country, score by engagement
        candidates = []
        dropped_country: list[str] = []
        dropped_duration: list[str] = []
        for item in stats_resp.get("items", []):
            vid_id = item["id"]
            stats = item.get("statistics", {})
            snippet = item.get("snippet", {})
            details = item.get("contentDetails", {})
            title = snippet.get("title", "")

            # Drop videos from channels explicitly set to a non-allowed country.
            # Channels with country=None are kept (many EN creators leave it blank).
            ch_country = channel_country.get(snippet.get("channelId", ""))
            if ch_country is not None and ch_country not in YOUTUBE_ALLOWED_CHANNEL_COUNTRIES:
                dropped_country.append(f"{title!r} (channel_country={ch_country})")
                continue

            likes = int(stats.get("likeCount", 0))
            views = int(stats.get("viewCount", 0))
            duration_s = _iso8601_duration_to_seconds(details.get("duration", ""))
            if not (60 <= duration_s <= 1200):
                dropped_duration.append(f"{title!r} ({duration_s}s)")
                continue

            score = likes + 0.1 * views
            candidates.append(
                {
                    "video_url": f"https://www.youtube.com/watch?v={vid_id}",
                    "video_provider": "youtube",
                    "video_duration_seconds": duration_s,
                    "video_thumbnail_url": f"https://img.youtube.com/vi/{vid_id}/maxresdefault.jpg",
                    "title": title,
                    "_score": score,
                }
            )

        if dropped_country:
            log.info("youtube_filter | dropped by country (%d): %s", len(dropped_country), ", ".join(dropped_country))
        if dropped_duration:
            log.info(
                "youtube_filter | dropped by duration (%d): %s", len(dropped_duration), ", ".join(dropped_duration)
            )

        candidates.sort(key=lambda x: x["_score"], reverse=True)
        top = candidates[:YOUTUBE_TOP_N]
        for v in top:
            del v["_score"]

        log.info(
            "youtube_search | subtopic=%s | pool=%d | after_filter=%d | selected=%d",
            name,
            len(video_ids),
            len(candidates),
            len(top),
        )
        return top

    except Exception as e:
        log.error("YouTube API error | subtopic=%s | error=%s", name, e)
        return []


def generate_video_content(subtopic: dict[str, Any]) -> list[dict[str, Any]]:
    """Return up to YOUTUBE_TOP_N real YouTube video records for a subtopic."""
    if SKIP_VIDEOS:
        return []
    return search_youtube_videos(subtopic)


def generate_explanation_content(subtopic: dict[str, Any]) -> dict[str, Any] | None:
    """Generate an LLM-written explanation for a subtopic, validated via Pydantic."""
    if SKIP_EXPLANATIONS:
        return None
    prerequisites = ", ".join(p.get("name", "") for p in subtopic.get("prerequisites", [])[:3])
    prompt = EXPLANATION_PROMPT.format(
        subtopic_name=subtopic.get("name", ""),
        subject=subtopic.get("_strand_id", "Mathematics"),
        grade_level=subtopic.get("grade_level", "Grade 8"),
        prerequisites=prerequisites or "basic arithmetic",
    )
    raw = call_llm(prompt)
    if raw is None:
        return None
    try:
        validated = _ExplanationOutput.model_validate(raw)
        log.info(
            "explanation_gen | subtopic=%s | chars=%d",
            subtopic.get("name", ""),
            len(validated.explanation_text),
        )
        return validated.model_dump()
    except Exception as e:
        log.warning("explanation_gen validation failed | subtopic=%s | error=%s", subtopic.get("name", ""), e)
        return None


def generate_quiz_content(subtopic: dict[str, Any]) -> dict[str, Any] | None:
    """Generate practice quiz questions for a subtopic, validated via Pydantic."""
    if SKIP_QUIZZES:
        return None
    prompt = QUIZ_PROMPT.format(
        subtopic_name=subtopic.get("name", ""),
        subject=subtopic.get("_strand_id", "Mathematics"),
        grade_level=subtopic.get("grade_level", "Grade 8"),
    )
    raw = call_llm(prompt)
    if raw is None:
        return None
    try:
        validated = _QuizOutput.model_validate(raw)
        log.info(
            "quiz_gen | subtopic=%s | questions=%d | difficulties=%s",
            subtopic.get("name", ""),
            len(validated.questions),
            [q.difficulty_level for q in validated.questions],
        )
        return validated.model_dump()
    except Exception as e:
        log.warning("quiz_gen validation failed | subtopic=%s | error=%s", subtopic.get("name", ""), e)
        return None


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

CONTENT_TYPE_VIDEO = "video"
CONTENT_TYPE_EXPLANATION = "explanation"
CONTENT_TYPE_PRACTICE = "practice"
REVIEW_STATUS_APPROVED = "approved"
REVIEW_STATUS_PENDING = "pending"


# All types use the same SELECT key: (subtopic_id, content_type) — one row per type per subtopic.
_SELECT_CONTENT_SQL = text("""
    SELECT id FROM subtopic_content
    WHERE subtopic_id = :subtopic_id
      AND content_type = CAST(:content_type AS content_type)
    LIMIT 1
""")

_INSERT_SQL = text("""
    INSERT INTO subtopic_content (
        id, subtopic_id, content_type, is_active,
        applicable_tiers, review_status, is_stale, is_archived,
        created_at, updated_at,
        videos,
        video_url, video_provider, video_duration_seconds, video_thumbnail_url,
        explanation_text, quiz_questions, quiz_questions_count,
        teacher_explanation, teacher_explanation_author_id,
        interest_category_id, reviewed_at, reviewed_by_id, rejection_reason
    ) VALUES (
        :id, :subtopic_id, CAST(:content_type AS content_type), :is_active,
        :applicable_tiers, CAST(:review_status AS review_status), :is_stale, :is_archived,
        :created_at, :updated_at,
        :videos,
        :video_url, :video_provider, :video_duration_seconds, :video_thumbnail_url,
        :explanation_text, :quiz_questions, :quiz_questions_count,
        :teacher_explanation, :teacher_explanation_author_id,
        :interest_category_id, :reviewed_at, :reviewed_by_id, :rejection_reason
    )
""")

_UPDATE_VIDEO_SQL = text("""
    UPDATE subtopic_content SET
        is_active = :is_active,
        applicable_tiers = :applicable_tiers,
        review_status = CAST(:review_status AS review_status),
        is_stale = :is_stale,
        is_archived = :is_archived,
        videos = :videos,
        updated_at = NOW()
    WHERE subtopic_id = :subtopic_id
      AND content_type = CAST(:content_type AS content_type)
""")

_UPDATE_CONTENT_SQL = text("""
    UPDATE subtopic_content SET
        is_active = :is_active,
        applicable_tiers = :applicable_tiers,
        review_status = CAST(:review_status AS review_status),
        is_stale = :is_stale,
        is_archived = :is_archived,
        explanation_text = :explanation_text,
        quiz_questions = :quiz_questions,
        quiz_questions_count = :quiz_questions_count,
        updated_at = NOW()
    WHERE subtopic_id = :subtopic_id
      AND content_type = CAST(:content_type AS content_type)
""")


async def _upsert_subtopic_content_async(records: list[dict[str, Any]]) -> int:
    """Insert or update subtopic_content records (idempotent, SELECT-then-INSERT/UPDATE).

    One row per (subtopic_id, content_type). SELECT by that key, then UPDATE or INSERT.
    """
    if not records:
        return 0
    saved = 0
    async with CeleryAsyncSessionLocal() as session:
        for rec in records:
            update_sql = _UPDATE_VIDEO_SQL if rec["content_type"] == CONTENT_TYPE_VIDEO else _UPDATE_CONTENT_SQL
            try:
                async with session.begin_nested():
                    existing = await session.execute(_SELECT_CONTENT_SQL, rec)
                    if existing.fetchone():
                        await session.execute(update_sql, rec)
                        log.debug("updated | subtopic=%s | type=%s", rec.get("subtopic_id"), rec.get("content_type"))
                    else:
                        await session.execute(_INSERT_SQL, rec)
                        log.debug("inserted | subtopic=%s | type=%s", rec.get("subtopic_id"), rec.get("content_type"))
                saved += 1
            except Exception as e:
                log.error(
                    "Failed to upsert content | subtopic=%s | type=%s | error=%s",
                    rec.get("subtopic_id"),
                    rec.get("content_type"),
                    e,
                )
        await session.commit()
    return saved


def upsert_subtopic_content(records: list[dict[str, Any]]) -> int:
    return run_async(_upsert_subtopic_content_async(records))


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
        # videos JSONB array — populated for content_type='video', null otherwise
        "videos": None,
        # individual video fields — set by admin approval workflow, not seed
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
        # Store all candidates in the JSONB array for admin review.
        # Each entry matches the review-queue schema: {url, title, channel, view_count, status, last_checked_at}
        # json.dumps required: asyncpg does not auto-serialize Python lists for JSONB in raw text() SQL.
        base["videos"] = json.dumps(
            [
                {
                    "url": v.get("video_url", ""),
                    "title": v.get("title", ""),
                    "channel": v.get("video_provider", ""),
                    "view_count": None,
                    "status": "pending",
                    "last_checked_at": None,
                }
                for v in data.get("candidates", [])
            ]
        )
    elif content_type == CONTENT_TYPE_EXPLANATION:
        base["explanation_text"] = data.get("explanation_text")
    elif content_type == CONTENT_TYPE_PRACTICE:
        questions = data.get("questions", [])
        # json.dumps required: asyncpg does not auto-serialize Python lists for JSONB in raw text() SQL.
        base["quiz_questions"] = json.dumps(questions)
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

    try:
        # --- Videos — one row per subtopic, all candidates in the videos JSONB array ---
        if not SKIP_VIDEOS:
            videos = generate_video_content(subtopic)
            if videos:
                rec = build_record(
                    subtopic,
                    CONTENT_TYPE_VIDEO,
                    {"candidates": videos},
                    REVIEW_STATUS_PENDING,
                    is_active=True,
                )
                if dry_run:
                    for v in videos:
                        log.info(
                            "[DRY RUN] would upsert video candidate | subtopic=%s | url=%s",
                            subtopic_name,
                            v.get("video_url"),
                        )
                    result.inserted += 1
                elif rec and upsert_subtopic_content([rec]):
                    result.inserted += 1
            else:
                log.info("no videos found | subtopic=%s", subtopic_name)
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
                elif rec and upsert_subtopic_content([rec]):
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
                elif rec and upsert_subtopic_content([rec]):
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
    if args.list:
        list_grades_and_subjects()
        return

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

    # Load curriculum — optionally filtered by grade/subject
    if args.grade or args.subject:
        log.info("Filters — grade: %s | subject: %s", args.grade or "all", args.subject or "all")
    subtopics = load_curriculum_subtopics(grade_level=args.grade, subject_name=args.subject)
    if not subtopics:
        log.error("No subtopics loaded — aborting (check --grade / --subject filters)")
        return

    if args.limit:
        subtopics = subtopics[: args.limit]
        log.info("Limited to %d subtopics", args.limit)

    # Load pre-generated questions (skip DB in dry-run)
    if DRY_RUN:
        pre_gen_qs: dict[str, Any] = {}
        log.info("[DRY RUN] skipping question_bank load")
    else:
        pre_gen_qs = load_pre_generated_questions()

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
