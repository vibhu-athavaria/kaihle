"""
Import questions from JSON or CSV into the question_bank table.

Usage:
    python import_questions.py --file questions.json [--format json|csv] [--dry-run]
    python import_questions.py --file questions.json --strategy reresolve [--dry-run]

Supports three strategies:

1. auto (default): Detects format automatically.
   - If questions have subtopic_id → uses 'preresolved' path (trusts existing UUIDs).
   - If questions have curriculum_code → uses 'task' path (resolves via hierarchy).

2. reresolve: Forces re-resolution using text fields, ignoring ALL stale UUIDs.
   Use this when questions were generated against a different database.
   Requires: grade_level (int), subject_name (str), topic_name (str), subtopic_name (str).
   Derives curriculum_code from grade_level. Uses fuzzy subtopic name matching.

3. task: Legacy task-format path requiring curriculum_code, subject_code, topic_name, subtopic_name.
"""

import argparse
import asyncio
import csv
import difflib
import hashlib
import json
import sys
import uuid
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

# Add backend to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.models.curriculum import (
    Curriculum,
    CurriculumTopic,
    Grade,
    QuestionBank,
    Subject,
    Subtopic,
    Topic,
)
from app.services.question_selection import resolve_objective_for_subtopic

logger = structlog.get_logger("import_questions")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

QUESTION_TYPE_MAP = {
    "multiple_choice": "MCQ",
    "true_false": "TRUE_FALSE",
    "short_answer": "SHORT_ANSWER",
    "MCQ": "MCQ",
    "TRUE_FALSE": "TRUE_FALSE",
    "SHORT_ANSWER": "SHORT_ANSWER",
}

# Maps subject_name from generated questions → subject_code in DB
SUBJECT_NAME_MAP: dict[str, str] = {
    # Full names
    "Mathematics": "MATH",
    "Integrated Science": "SCI",
    "Science": "SCI",
    "English Language": "ENG",
    "English": "ENG",
    "Biology": "BIO",
    "Chemistry": "CHEM",
    "Physics": "PHY",
    "English Literature": "ENGL",
    "Geography": "GEO",
    "Global Perspectives": "GP",
    "History": "HIST",
    "Humanities": None,  # Ambiguous — question bank uses this for GEO/GP/HIST combined
    # Short forms / common variants
    "Math": "MATH",
    "Maths": "MATH",
    "Sci": "SCI",
    "Bio": "BIO",
    "Chem": "CHEM",
    "Phys": "PHY",
    "Lit": "ENGL",
    "Literature": "ENGL",
    "Geo": "GEO",
}


def infer_curriculum_code(grade_level: int) -> str | None:
    """
    Derive curriculum_code from grade_level.

    Grade 5           → cambridge_primary
    Grades 6–8        → cambridge_lower
    Grades 9–10       → igcse
    Grades 11–12      → cambridge_as_level
    """
    if grade_level == 5:
        return "cambridge_primary"
    elif 6 <= grade_level <= 8:
        return "cambridge_lower"
    elif 9 <= grade_level <= 10:
        return "igcse"
    elif 11 <= grade_level <= 12:
        return "cambridge_as_level"
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def compute_canonical_form(question_text: str) -> str:
    """Compute SHA-256 hash of normalized question text for deduplication."""
    normalized = question_text.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()


def safe_float(value: Any) -> float | None:
    """Safely convert a value to float, returning None if conversion fails."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def build_problem_signature(
    question_type: str,
    difficulty: float | None,
    bloom_level: str | None,
    has_options: bool,
) -> dict:
    """Build a structural fingerprint for the question."""
    concept_hash = hashlib.md5(f"{question_type}:{bloom_level or 'unknown'}".encode()).hexdigest()[:12]
    return {
        "type": question_type,
        "difficulty": difficulty or 1,
        "concept_hash": concept_hash,
        "bloom_level": bloom_level or "Remember",
        "has_options": has_options,
    }


def normalize_options_for_mcq(options: Any) -> list[dict] | None:
    """
    Normalize options to the DB format: [{"key": "A", "text": "..."}, ...]

    Handles both:
    - Task format: [{"key": "A", "text": "..."}]
    - Generated format: {"A": "...", "B": "..."}
    """
    if options is None:
        return None
    if isinstance(options, list):
        return options
    if isinstance(options, dict):
        return [{"key": k, "text": v} for k, v in sorted(options.items())]
    return None


def normalize_hints(hints: Any) -> list[dict] | None:
    """
    Normalize hints to the DB format: [{"order": 1, "text": "..."}, ...]

    Handles both:
    - Task format: [{"order": 1, "text": "..."}]
    - Generated format: {"hint1": "...", "hint2": "..."}
    """
    if hints is None:
        return None
    if isinstance(hints, list):
        return hints
    if isinstance(hints, dict):
        result = []
        for i, key in enumerate(sorted(hints.keys())):
            if key.startswith("hint"):
                try:
                    order = int(key.replace("hint", ""))
                except ValueError:
                    order = i + 1
            else:
                order = i + 1
            result.append({"order": order, "text": hints[key]})
        return result
    return None


def build_insert_dict(
    question: dict,
    subtopic_id: str,
    question_type: str,
    options: list | None,
    learning_objective_id: str,
) -> dict:
    """Shared helper to build the insert dict from a resolved question.

    learning_objective_id is required, not optional. Selection resolves through the
    objective — never through subtopic_id — so a row written without it is imported
    successfully and then served to nobody. Callers resolve it via
    resolve_objective_for_subtopic and skip the question if the subtopic has none.
    """
    question_text = question.get("question_text", "")
    canonical_form = compute_canonical_form(question_text)
    bloom = question.get("bloom_taxonomy_level") or question.get("bloom_taxonomy")

    return {
        "subtopic_id": subtopic_id,
        "learning_objective_id": learning_objective_id,
        "question_text": question_text,
        "question_type": question_type,
        "options": options,
        "correct_answer": question.get("correct_answer"),
        "explanation": question.get("explanation"),
        "hints": normalize_hints(question.get("hints")),
        "difficulty_level": safe_float(question.get("difficulty_level")),
        "bloom_taxonomy_level": bloom,
        "estimated_time_seconds": question.get("estimated_time_seconds"),
        "learning_objectives": question.get("learning_objectives"),
        "canonical_form": canonical_form,
        "problem_signature": question.get("problem_signature")
        or build_problem_signature(
            question_type,
            question.get("difficulty_level"),
            bloom,
            options is not None,
        ),
        "source": "bank",
        "is_active": question.get("is_active", True),
    }


# ---------------------------------------------------------------------------
# Subtopic resolution — exact match
# ---------------------------------------------------------------------------


async def resolve_subtopic_id(
    session,
    curriculum_code: str,
    subject_code: str,
    grade_level: int,
    topic_name: str,
    subtopic_name: str,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    """
    Resolve subtopic_id by walking the curriculum hierarchy with exact name matching.
    Returns (subtopic_id, topic_id, subject_id, grade_id, curriculum_id) or all-None on failure.
    """
    result = await session.execute(select(Curriculum.id).where(Curriculum.code == curriculum_code))
    curriculum_id = result.scalar_one_or_none()
    if not curriculum_id:
        return None, None, None, None, None

    result = await session.execute(select(Subject.id).where(Subject.code == subject_code))
    subject_id = result.scalar_one_or_none()
    if not subject_id:
        return None, None, None, None, None

    result = await session.execute(select(Grade.id).where(Grade.level == grade_level))
    grade_id = result.scalar_one_or_none()
    if not grade_id:
        return None, None, None, None, None

    result = await session.execute(select(Topic.id).where(Topic.name == topic_name))
    topic_id = result.scalar_one_or_none()
    if not topic_id:
        return None, None, None, None, None

    result = await session.execute(
        select(CurriculumTopic.id).where(
            CurriculumTopic.curriculum_id == curriculum_id,
            CurriculumTopic.subject_id == subject_id,
            CurriculumTopic.grade_id == grade_id,
            CurriculumTopic.topic_id == topic_id,
        )
    )
    ct_id = result.scalar_one_or_none()
    if not ct_id:
        return None, None, None, None, None

    result = await session.execute(
        select(Subtopic.id).where(
            Subtopic.curriculum_topic_id == ct_id,
            Subtopic.name == subtopic_name,
        )
    )
    subtopic_id = result.scalar_one_or_none()
    if not subtopic_id:
        return None, None, None, None, None

    return subtopic_id, topic_id, subject_id, grade_id, curriculum_id


# ---------------------------------------------------------------------------
# Subtopic resolution — fuzzy match (used by reresolve strategy)
# ---------------------------------------------------------------------------


async def resolve_subtopic_id_fuzzy(
    session,
    curriculum_code: str,
    subject_code: str,
    grade_level: int,
    topic_name: str,
    subtopic_name: str,
    topic_cutoff: float = 0.6,
    subtopic_cutoff: float = 0.55,
) -> tuple[str | None, str | None, str | None, str | None, str | None, str | None]:
    """
    Resolve subtopic_id using fuzzy name matching via difflib.

    Lower cutoffs than exact-match (0.55–0.6) because question bank topic/subtopic
    names ('Develop broad reading skills') differ structurally from cambridge_v1.json
    names ('Reading for Explicit Meaning').

    Returns (subtopic_id, topic_id, subject_id, grade_id, curriculum_id, match_note).
    match_note is a string describing the fuzzy matches made — logged for audit.
    """
    # Resolve curriculum
    result = await session.execute(select(Curriculum.id).where(Curriculum.code == curriculum_code))
    curriculum_id = result.scalar_one_or_none()
    if not curriculum_id:
        return None, None, None, None, None, f"curriculum_code '{curriculum_code}' not found"

    # Resolve subject
    result = await session.execute(select(Subject.id).where(Subject.code == subject_code))
    subject_id = result.scalar_one_or_none()
    if not subject_id:
        return None, None, None, None, None, f"subject_code '{subject_code}' not found"

    # Resolve grade — exact integer match, no fuzzy needed
    result = await session.execute(select(Grade.id).where(Grade.level == grade_level))
    grade_id = result.scalar_one_or_none()
    if not grade_id:
        return None, None, None, None, None, f"grade_level {grade_level} not found in grades table"

    # Fetch all topics for this curriculum+subject+grade combination
    rows = await session.execute(
        select(Topic.id, Topic.name)
        .join(
            CurriculumTopic,
            CurriculumTopic.topic_id == Topic.id,
        )
        .where(
            CurriculumTopic.curriculum_id == curriculum_id,
            CurriculumTopic.subject_id == subject_id,
            CurriculumTopic.grade_id == grade_id,
        )
    )
    topic_rows = rows.fetchall()

    if not topic_rows:
        return (
            None,
            None,
            None,
            None,
            None,
            (f"No topics found for {curriculum_code}/{subject_code}/grade {grade_level}"),
        )

    topic_names = [r.name for r in topic_rows]
    topic_map = {r.name: r.id for r in topic_rows}

    # Fuzzy match topic name
    topic_matches = difflib.get_close_matches(topic_name, topic_names, n=1, cutoff=topic_cutoff)
    if not topic_matches:
        return (
            None,
            None,
            None,
            None,
            None,
            (
                f"No topic fuzzy match for '{topic_name}' in {curriculum_code}/{subject_code}/grade {grade_level}. "
                f"Available: {topic_names}"
            ),
        )

    matched_topic_name = topic_matches[0]
    topic_id = topic_map[matched_topic_name]
    topic_match_note = f"topic '{topic_name}' → '{matched_topic_name}'"

    # Resolve curriculum_topic
    result = await session.execute(
        select(CurriculumTopic.id).where(
            CurriculumTopic.curriculum_id == curriculum_id,
            CurriculumTopic.subject_id == subject_id,
            CurriculumTopic.grade_id == grade_id,
            CurriculumTopic.topic_id == topic_id,
        )
    )
    ct_id = result.scalar_one_or_none()
    if not ct_id:
        return None, None, None, None, None, "curriculum_topic not found after topic resolution"

    # Fetch all subtopics for this curriculum_topic
    rows = await session.execute(select(Subtopic.id, Subtopic.name).where(Subtopic.curriculum_topic_id == ct_id))
    subtopic_rows = rows.fetchall()

    if not subtopic_rows:
        return None, None, None, None, None, (f"No subtopics found under curriculum_topic for '{matched_topic_name}'")

    subtopic_names = [r.name for r in subtopic_rows]
    subtopic_map = {r.name: r.id for r in subtopic_rows}

    # Fuzzy match subtopic name
    subtopic_matches = difflib.get_close_matches(subtopic_name, subtopic_names, n=1, cutoff=subtopic_cutoff)
    if not subtopic_matches:
        return (
            None,
            None,
            None,
            None,
            None,
            (
                f"No subtopic fuzzy match for '{subtopic_name}' under topic '{matched_topic_name}'. "
                f"Available: {subtopic_names}"
            ),
        )

    matched_subtopic_name = subtopic_matches[0]
    subtopic_id = subtopic_map[matched_subtopic_name]
    match_note = f"{topic_match_note} | subtopic '{subtopic_name}' → '{matched_subtopic_name}'"

    return str(subtopic_id), str(topic_id), str(subject_id), str(grade_id), str(curriculum_id), match_note


# ---------------------------------------------------------------------------
# Question processors
# ---------------------------------------------------------------------------


async def process_question_task_format(session, question: dict, row_num: int) -> tuple[dict | None, str | None]:
    """
    Process a question in task format (with curriculum_code, subject_code, etc.).
    Returns (insert_dict, error_message).
    """
    curriculum_code = question.get("curriculum_code")
    subject_code = question.get("subject_code")
    grade_level = question.get("grade_level")
    topic_name = question.get("topic_name")
    subtopic_name = question.get("subtopic_name")

    if not all([curriculum_code, subject_code, grade_level, topic_name, subtopic_name]):
        return None, f"Row {row_num}: Missing required fields for lookup"

    assert curriculum_code is not None
    assert subject_code is not None
    assert grade_level is not None
    assert topic_name is not None
    assert subtopic_name is not None

    subtopic_id, topic_id, subject_id, grade_id, curriculum_id = await resolve_subtopic_id(
        session, curriculum_code, subject_code, grade_level, topic_name, subtopic_name
    )

    if not subtopic_id:
        return None, (
            f"Row {row_num}: Could not resolve subtopic for "
            f"curriculum={curriculum_code}, subject={subject_code}, "
            f"grade={grade_level}, topic={topic_name}, subtopic={subtopic_name}"
        )

    question_type_raw = question.get("question_type", "MCQ")
    question_type = QUESTION_TYPE_MAP.get(question_type_raw)
    if not question_type:
        return None, f"Row {row_num}: Unknown question_type '{question_type_raw}'"

    correct_answer = question.get("correct_answer")
    if not correct_answer:
        return None, f"Row {row_num}: Missing correct_answer"

    options_raw = question.get("options")
    options = normalize_options_for_mcq(options_raw) if question_type == "MCQ" else None

    objective_id = await resolve_objective_for_subtopic(session, uuid.UUID(str(subtopic_id)))
    if objective_id is None:
        return None, (
            f"Row {row_num}: Subtopic {subtopic_id} has no learning objective. Importing "
            f"would write a question that selection can never reach."
        )

    return build_insert_dict(question, subtopic_id, question_type, options, str(objective_id)), None


async def process_question_preresolved_format(session, question: dict, row_num: int) -> tuple[dict | None, str | None]:
    """
    Process a question in pre-resolved format (trusts existing subtopic_id UUID).
    Only use when the UUIDs came from THIS database.
    Returns (insert_dict, error_message).
    """
    subtopic_id = question.get("subtopic_id")
    if not subtopic_id:
        return None, f"Row {row_num}: Missing subtopic_id"

    question_type_raw = question.get("question_type", "MCQ")
    question_type = QUESTION_TYPE_MAP.get(question_type_raw)
    if not question_type:
        return None, f"Row {row_num}: Unknown question_type '{question_type_raw}'"

    correct_answer = question.get("correct_answer")
    if not correct_answer:
        return None, f"Row {row_num}: Missing correct_answer"

    options_raw = question.get("options")
    options = normalize_options_for_mcq(options_raw) if question_type == "MCQ" else None

    objective_id = await resolve_objective_for_subtopic(session, uuid.UUID(str(subtopic_id)))
    if objective_id is None:
        return None, (
            f"Row {row_num}: Subtopic {subtopic_id} has no learning objective. Importing "
            f"would write a question that selection can never reach."
        )

    return build_insert_dict(question, subtopic_id, question_type, options, str(objective_id)), None


def load_subtopic_mapping(mapping_path: str | None) -> dict[str, str]:
    """
    Load subtopic_mapping.json produced by generate_subtopic_mapping.py.
    Returns empty dict if path is None or file not found.
    """
    if not mapping_path:
        return {}
    path = Path(mapping_path)
    if not path.exists():
        logger.warning("subtopic_mapping_not_found", path=str(path))
        return {}
    with open(path) as f:
        data = json.load(f)
    data.pop("UNMAPPED", None)
    logger.info("subtopic_mapping_loaded", entries=len(data), path=str(path))
    return data


async def process_question_reresolve_format(
    session,
    question: dict,
    row_num: int,
    fuzzy_log: list[str],
    subtopic_mapping: dict[str, str] | None = None,
) -> tuple[dict | None, str | None]:
    """
    Re-resolve a question using text fields, ignoring all stale UUIDs.

    Resolution order:
      1. subtopic_mapping.json key lookup (fast, semantic — from generate_subtopic_mapping.py)
      2. Fuzzy string matching fallback

    fuzzy_log: mutable list — successful matches appended for audit trail.
    Returns (insert_dict, error_message).
    """
    grade_level = question.get("grade_level")
    if grade_level is None:
        return None, f"Row {row_num}: Missing grade_level — required for reresolve"

    try:
        grade_level = int(grade_level)
    except (ValueError, TypeError):
        return None, f"Row {row_num}: grade_level '{grade_level}' is not an integer"

    curriculum_code = infer_curriculum_code(grade_level)
    if not curriculum_code:
        return None, (f"Row {row_num}: grade_level {grade_level} is outside supported range (5–12). Skipping.")

    subject_name = question.get("subject_name", "")
    topic_name = question.get("topic_name", "").strip()
    subtopic_name = question.get("subtopic_name", "").strip()

    if not topic_name or not subtopic_name:
        return None, f"Row {row_num}: Missing topic_name or subtopic_name"

    question_text = question.get("question_text", "")
    if not question_text:
        return None, f"Row {row_num}: Missing question_text"

    question_type_raw = question.get("question_type", "MCQ")
    question_type = QUESTION_TYPE_MAP.get(question_type_raw)
    if not question_type:
        return None, f"Row {row_num}: Unknown question_type '{question_type_raw}'"

    correct_answer = question.get("correct_answer")
    if not correct_answer:
        return None, f"Row {row_num}: Missing correct_answer"

    options_raw = question.get("options")
    options = normalize_options_for_mcq(options_raw) if question_type == "MCQ" else None

    subtopic_id = None

    # ── Step 1: Check subtopic_mapping.json ─────────────────────────────────
    # This must happen BEFORE subject_code validation because some subject_names
    # (e.g. 'Humanities') are intentionally ambiguous in SUBJECT_NAME_MAP (mapped
    # to None) but ARE resolved correctly via the mapping file. Checking the
    # mapping file first allows these to succeed without a subject_code.
    if subtopic_mapping:
        mapping_key = f"{curriculum_code}/{subject_name}/{grade_level}/{topic_name}/{subtopic_name}"
        canonical_code = subtopic_mapping.get(mapping_key)
        if canonical_code:
            from sqlalchemy import select

            from app.models.curriculum import Subtopic

            result = await session.execute(select(Subtopic.id).where(Subtopic.canonical_code == canonical_code))
            subtopic_id = result.scalar_one_or_none()
            if subtopic_id:
                subtopic_id = str(subtopic_id)
                fuzzy_log.append(f"Row {row_num}: mapping_file '{subtopic_name}' → {canonical_code}")

    # ── Step 2: Fuzzy fallback ───────────────────────────────────────────────
    # Only reached if mapping file didn't resolve. Requires a valid subject_code.
    if not subtopic_id:
        subject_code = SUBJECT_NAME_MAP.get(subject_name) or next(
            (v for k, v in SUBJECT_NAME_MAP.items() if k.lower() == subject_name.lower()),
            None,
        )

        # Special handling for 'Humanities' — derive subject_code from topic_name
        # since Humanities is a generic label covering GEO, GP, HIST and others.
        # For grades 11-12 these subjects exist in DB. For grades 5-10 they don't,
        # so fall back to a grade-adjacent Humanities mapping key if one exists.
        if not subject_code and subject_name == "Humanities":
            topic_lower = topic_name.lower()
            if "geography" in topic_lower:
                subject_code = "GEO"
            elif "history" in topic_lower:
                subject_code = "HIST"
            elif "global perspectives" in topic_lower or "global" in topic_lower:
                subject_code = "GP"

            # For grades 5-10, GEO/GP/HIST don't exist in DB — use nearest
            # mapping file entry matching curriculum/grade/topic as fallback
            if subject_code and grade_level <= 10:
                prefix = f"{curriculum_code}/Humanities/{grade_level}/{topic_name}/"
                nearest = next(
                    (v for k, v in (subtopic_mapping or {}).items() if k.startswith(prefix)),
                    None,
                )
                if nearest:
                    from sqlalchemy import select

                    from app.models.curriculum import Subtopic

                    result = await session.execute(select(Subtopic.id).where(Subtopic.canonical_code == nearest))
                    subtopic_id = result.scalar_one_or_none()
                    if subtopic_id:
                        subtopic_id = str(subtopic_id)
                        fuzzy_log.append(
                            f"Row {row_num}: humanities_proximity '{subtopic_name}' "
                            f"→ {nearest} (nearest {topic_name} entry at grade {grade_level})"
                        )

        if not subtopic_id and not subject_code:
            return None, (
                f"Row {row_num}: Cannot map subject_name '{subject_name}' to a subject_code "
                f"and no mapping file entry found for this combination."
            )

        result = await resolve_subtopic_id_fuzzy(
            session, curriculum_code, subject_code, grade_level, topic_name, subtopic_name
        )
        subtopic_id, _, _, _, _, match_note = result

        if not subtopic_id:
            return None, (
                f"Row {row_num}: Resolution failed — {match_note} "
                f"[{curriculum_code}/{subject_code}/grade {grade_level}]"
            )
        fuzzy_log.append(f"Row {row_num}: fuzzy {match_note}")

    objective_id = await resolve_objective_for_subtopic(session, uuid.UUID(str(subtopic_id)))
    if objective_id is None:
        return None, (
            f"Row {row_num}: Subtopic {subtopic_id} has no learning objective. Importing "
            f"would write a question that selection can never reach."
        )

    return build_insert_dict(question, subtopic_id, question_type, options, str(objective_id)), None


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


def detect_format(questions_data: Any) -> str:
    """
    Detect whether data is in task or pre-resolved format.
    Note: reresolve is never auto-detected — it must be set explicitly via --strategy.
    """
    if isinstance(questions_data, list) and len(questions_data) > 0:
        first = questions_data[0]
        if "subtopic_id" in first:
            return "preresolved"
        return "task"
    return "task"


# ---------------------------------------------------------------------------
# Main import function
# ---------------------------------------------------------------------------


async def import_questions(
    file_path: str,
    file_format: str | None = None,
    dry_run: bool = False,
    strategy: str = "auto",
    mapping_file: str | None = None,
) -> dict:
    """
    Import questions from JSON or CSV file.

    strategy:
      'auto'       — detect format automatically (preresolved or task)
      'reresolve'  — ignore stale UUIDs, re-resolve via text fields + fuzzy matching
      'task'       — force task format path (curriculum_code, subject_code, etc.)

    Returns stats dict.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Load data
    if file_format == "csv" or path.suffix == ".csv":
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            questions_data = list(reader)
    else:
        with open(path, encoding="utf-8") as f:
            raw_data = json.load(f)

        if isinstance(raw_data, dict) and "questions" in raw_data:
            questions_data = raw_data["questions"]
        elif isinstance(raw_data, list):
            questions_data = raw_data
        else:
            raise ValueError(f"Unexpected JSON structure in {file_path}")

    # Determine active strategy
    if strategy == "auto":
        active_strategy = detect_format(questions_data)
    else:
        active_strategy = strategy

    logger.info(
        "Starting import",
        strategy=active_strategy,
        total_questions=len(questions_data),
        dry_run=dry_run,
    )

    # Load subtopic mapping file if provided (reresolve strategy)
    subtopic_mapping = load_subtopic_mapping(mapping_file) if active_strategy == "reresolve" else {}

    stats = {
        "total": len(questions_data),
        "inserted": 0,
        "skipped_duplicate": 0,
        "skipped_error": 0,
        "errors": [],
    }
    fuzzy_log: list[str] = []

    BATCH_SIZE = 100
    async with AsyncSessionLocal() as session:
        batch_insert_data = []
        batch_row_numbers = []

        for i, question in enumerate(questions_data, 1):
            # Route to correct processor
            if active_strategy == "reresolve":
                insert_data, error = await process_question_reresolve_format(
                    session, question, i, fuzzy_log, subtopic_mapping
                )
            elif active_strategy == "preresolved":
                insert_data, error = await process_question_preresolved_format(session, question, i)
            else:
                insert_data, error = await process_question_task_format(session, question, i)

            if error:
                stats["skipped_error"] += 1
                stats["errors"].append(error)
                continue

            if dry_run:
                stats["inserted"] += 1
                continue

            batch_insert_data.append(insert_data)
            batch_row_numbers.append(i)

            if len(batch_insert_data) >= BATCH_SIZE or i == len(questions_data):
                try:
                    from sqlalchemy.dialects.postgresql import insert as pg_insert

                    stmt = pg_insert(QuestionBank).values(batch_insert_data)
                    await session.execute(stmt)
                    await session.commit()
                    stats["inserted"] += len(batch_insert_data)
                except IntegrityError:
                    await session.rollback()
                    await session.close()
                    async with AsyncSessionLocal() as retry_session:
                        for data, row_num in zip(batch_insert_data, batch_row_numbers):
                            try:
                                stmt = pg_insert(QuestionBank).values([data])
                                await retry_session.execute(stmt)
                                await retry_session.commit()
                                stats["inserted"] += 1
                            except IntegrityError as ie:
                                await retry_session.rollback()
                                error_str = str(ie).lower()
                                is_fk = "foreign key" in error_str or (
                                    "subtopic_id" in error_str and "is not present in table" in error_str
                                )
                                is_dup = "duplicate" in error_str and "canonical_form" in error_str
                                if is_dup:
                                    stats["skipped_duplicate"] += 1
                                elif is_fk:
                                    stats["skipped_error"] += 1
                                    stats["errors"].append(f"Row {row_num}: FK violation — subtopic_id not found in DB")
                                else:
                                    stats["skipped_error"] += 1
                                    stats["errors"].append(f"Row {row_num}: {ie}")
                            except Exception as ie:
                                await retry_session.rollback()
                                stats["skipped_error"] += 1
                                stats["errors"].append(f"Row {row_num}: {ie}")
                except Exception:
                    await session.rollback()
                    await session.close()
                    async with AsyncSessionLocal() as retry_session:
                        for data, row_num in zip(batch_insert_data, batch_row_numbers):
                            try:
                                stmt = pg_insert(QuestionBank).values([data])
                                await retry_session.execute(stmt)
                                await retry_session.commit()
                                stats["inserted"] += 1
                            except Exception as ie:
                                await retry_session.rollback()
                                error_str = str(ie).lower()
                                is_dup = "duplicate" in error_str and "canonical_form" in error_str
                                if is_dup:
                                    stats["skipped_duplicate"] += 1
                                else:
                                    stats["skipped_error"] += 1
                                    stats["errors"].append(f"Row {row_num}: {ie}")

                batch_insert_data = []
                batch_row_numbers = []

    # Write error log
    script_dir = Path(__file__).parent
    log_dir = script_dir.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    if stats["errors"]:
        error_log = log_dir / "import_errors.log"
        with open(error_log, "w", encoding="utf-8") as f:
            for error in stats["errors"]:
                f.write(error + "\n")
        logger.info("Errors logged", path=str(error_log))

    # Write fuzzy match audit log (reresolve only)
    if fuzzy_log:
        fuzzy_audit_log = log_dir / "import_fuzzy_matches.log"
        with open(fuzzy_audit_log, "w", encoding="utf-8") as f:
            for entry in fuzzy_log:
                f.write(entry + "\n")
        logger.info(
            "Fuzzy match audit written",
            path=str(fuzzy_audit_log),
            total_matches=len(fuzzy_log),
        )

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def print_stats(stats: dict, strategy: str):
    print("\n" + "=" * 55)
    print("IMPORT STATISTICS")
    print("=" * 55)
    print(f"Strategy:          {strategy}")
    print(f"Total rows:        {stats['total']}")
    print(f"Inserted:          {stats['inserted']}")
    print(f"Skipped (dup):     {stats['skipped_duplicate']}")
    print(f"Skipped (err):     {stats['skipped_error']}")
    if stats["errors"]:
        print("Errors logged:     backend/logs/import_errors.log")
    if strategy == "reresolve":
        print("Fuzzy audit:       backend/logs/import_fuzzy_matches.log")
    print("=" * 55)


async def main():
    parser = argparse.ArgumentParser(description="Import questions into question_bank table")
    parser.add_argument(
        "--file",
        required=True,
        help="Path to JSON or CSV file with questions",
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv"],
        default=None,
        help="Force file format (auto-detected if not specified)",
    )
    parser.add_argument(
        "--strategy",
        choices=["auto", "reresolve", "task"],
        default="auto",
        help=(
            "Resolution strategy. "
            "'auto': detect format automatically. "
            "'reresolve': ignore stale UUIDs, resolve via text fields + fuzzy matching. "
            "'task': force task-format path requiring curriculum_code."
        ),
    )
    parser.add_argument(
        "--mapping-file",
        default=None,
        help=(
            "Path to subtopic_mapping.json from generate_subtopic_mapping.py. "
            "Used by --strategy reresolve to resolve questions via semantic mapping "
            "before falling back to fuzzy matching."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and resolve all rows without writing to DB",
    )

    args = parser.parse_args()

    try:
        stats = await import_questions(args.file, args.format, args.dry_run, args.strategy, args.mapping_file)
        print_stats(stats, args.strategy)

        if stats["skipped_error"] > 0:
            sys.exit(1)
    except Exception as e:
        logger.error("Import failed", error=str(e))
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
