"""
Import questions from JSON or CSV into the question_bank table.

Usage:
    python import_questions.py --file questions.json [--format json|csv] [--dry-run]
    python import_questions.py --file generated_questions_*.json [--dry-run]

Supports two formats:
1. Task format (M1-1-T1): Array of questions with curriculum_code, subject_code, etc.
   Requires lookup through curriculum hierarchy to resolve subtopic_id.

2. Pre-resolved format: Object with {questions: [...]} where each question has
   subtopic_id, topic_id, subject_id, grade_id already set.
   Maps question_type enums: "multiple_choice" -> "MCQ", "true_false" -> "TRUE_FALSE"
"""

import argparse
import asyncio
import csv
import hashlib
import json
import sys
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

logger = structlog.get_logger("import_questions")


# Mapping from generated format question_type to DB enum
QUESTION_TYPE_MAP = {
    "multiple_choice": "MCQ",
    "true_false": "TRUE_FALSE",
    "short_answer": "SHORT_ANSWER",
    "MCQ": "MCQ",
    "TRUE_FALSE": "TRUE_FALSE",
    "SHORT_ANSWER": "SHORT_ANSWER",
}


def compute_canonical_form(question_text: str) -> str:
    """Compute SHA-256 hash of normalized question text for deduplication."""
    normalized = question_text.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()


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
        # Already in task format
        return options

    if isinstance(options, dict):
        # Generated format: {"A": "...", "B": "..."}
        return [{"key": k, "text": v} for k, v in sorted(options.items())]

    return None


def normalize_hints(hints: Any) -> list[dict] | None:
    """
    Normalize hints to the DB format.

    Handles both:
    - Task format: [{"order": 1, "text": "..."}]
    - Generated format: {"hint1": "...", "hint2": "..."}
    """
    if hints is None:
        return None

    if isinstance(hints, list):
        return hints

    if isinstance(hints, dict):
        # Generated format: {"hint1": "...", "hint2": "..."}
        result = []
        for key in sorted(hints.keys()):
            order = int(key.replace("hint", "")) if key.startswith("hint") else 0
            result.append({"order": order, "text": hints[key]})
        return result

    return None


async def resolve_subtopic_id(
    session,
    curriculum_code: str,
    subject_code: str,
    grade_level: int,
    topic_name: str,
    subtopic_name: str,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    """
    Resolve subtopic_id by walking the curriculum hierarchy.
    Returns (subtopic_id, topic_id, subject_id, grade_id, curriculum_id) or (None, ...) on failure.
    """
    # Step 1: Resolve curriculum
    result = await session.execute(select(Curriculum.id).where(Curriculum.code == curriculum_code))
    curriculum_id = result.scalar_one_or_none()
    if not curriculum_id:
        return None, None, None, None, None

    # Step 2: Resolve subject
    result = await session.execute(select(Subject.id).where(Subject.code == subject_code))
    subject_id = result.scalar_one_or_none()
    if not subject_id:
        return None, None, None, None, None

    # Step 3: Resolve grade
    result = await session.execute(select(Grade.id).where(Grade.level == grade_level))
    grade_id = result.scalar_one_or_none()
    if not grade_id:
        return None, None, None, None, None

    # Step 4: Resolve topic
    result = await session.execute(select(Topic.id).where(Topic.name == topic_name))
    topic_id = result.scalar_one_or_none()
    if not topic_id:
        return None, None, None, None, None

    # Step 5: Resolve curriculum_topic
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

    # Step 6: Resolve subtopic
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

    # Type narrowing: at this point all values are guaranteed non-None
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

    question_text = question.get("question_text", "")
    question_type_raw = question.get("question_type", "MCQ")
    question_type = QUESTION_TYPE_MAP.get(question_type_raw)
    if not question_type:
        return None, f"Row {row_num}: Unknown question_type '{question_type_raw}'"

    options_raw = question.get("options")
    options = normalize_options_for_mcq(options_raw) if question_type == "MCQ" else None

    correct_answer = question.get("correct_answer")
    if not correct_answer:
        return None, f"Row {row_num}: Missing correct_answer"

    canonical_form = compute_canonical_form(question_text)

    insert_data = {
        "subtopic_id": subtopic_id,
        "question_text": question_text,
        "question_type": question_type,
        "options": options,
        "correct_answer": correct_answer,
        "explanation": question.get("explanation"),
        "hints": normalize_hints(question.get("hints")),
        "difficulty_level": float(question["difficulty_level"]) if question.get("difficulty_level") else None,
        "bloom_taxonomy_level": question.get("bloom_taxonomy"),
        "estimated_time_seconds": question.get("estimated_time_seconds"),
        "learning_objectives": question.get("learning_objectives"),
        "canonical_form": canonical_form,
        "problem_signature": build_problem_signature(
            question_type,
            question.get("difficulty_level"),
            question.get("bloom_taxonomy"),
            options is not None,
        ),
        "source": "bank",
        "is_active": True,
    }

    return insert_data, None


async def process_question_preresolved_format(session, question: dict, row_num: int) -> tuple[dict | None, str | None]:
    """
    Process a question in pre-resolved format (with subtopic_id already set).
    Returns (insert_dict, error_message).
    """
    subtopic_id = question.get("subtopic_id")
    if not subtopic_id:
        return None, f"Row {row_num}: Missing subtopic_id"

    question_text = question.get("question_text", "")
    question_type_raw = question.get("question_type", "MCQ")
    question_type = QUESTION_TYPE_MAP.get(question_type_raw)
    if not question_type:
        return None, f"Row {row_num}: Unknown question_type '{question_type_raw}'"

    options_raw = question.get("options")
    options = normalize_options_for_mcq(options_raw) if question_type == "MCQ" else None

    correct_answer = question.get("correct_answer")
    if not correct_answer:
        return None, f"Row {row_num}: Missing correct_answer"

    canonical_form = compute_canonical_form(question_text)

    insert_data = {
        "subtopic_id": subtopic_id,
        "question_text": question_text,
        "question_type": question_type,
        "options": options,
        "correct_answer": correct_answer,
        "explanation": question.get("explanation"),
        "hints": normalize_hints(question.get("hints")),
        "difficulty_level": float(question["difficulty_level"]) if question.get("difficulty_level") else None,
        "bloom_taxonomy_level": question.get("bloom_taxonomy_level") or question.get("bloom_taxonomy"),
        "estimated_time_seconds": question.get("estimated_time_seconds"),
        "learning_objectives": question.get("learning_objectives"),
        "canonical_form": canonical_form,
        "problem_signature": question.get("problem_signature")
        or build_problem_signature(
            question_type,
            question.get("difficulty_level"),
            question.get("bloom_taxonomy_level") or question.get("bloom_taxonomy"),
            options is not None,
        ),
        "source": "bank",
        "is_active": question.get("is_active", True),
    }

    return insert_data, None


def detect_format(questions_data: Any) -> str:
    """
    Detect whether the data is in task format or pre-resolved format.

    Pre-resolved format: questions have subtopic_id field
    Task format: questions have curriculum_code, subject_code, etc.
    """
    if isinstance(questions_data, list) and len(questions_data) > 0:
        first = questions_data[0]
        if "subtopic_id" in first:
            return "preresolved"
        return "task"
    return "task"  # Default to task format


async def import_questions(
    file_path: str,
    file_format: str | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Import questions from JSON or CSV file.

    Returns stats dict with counts.
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

        # Handle both formats:
        # 1. Array: [{...}, ...]
        # 2. Object: {questions: [{...}, ...], ...}
        if isinstance(raw_data, dict) and "questions" in raw_data:
            questions_data = raw_data["questions"]
        elif isinstance(raw_data, list):
            questions_data = raw_data
        else:
            raise ValueError(f"Unexpected JSON structure in {file_path}")

    # Detect format
    detected_format = detect_format(questions_data)
    logger.info(
        "Detected format",
        format=detected_format,
        total_questions=len(questions_data),
        dry_run=dry_run,
    )

    stats = {
        "total": len(questions_data),
        "inserted": 0,
        "skipped_duplicate": 0,
        "skipped_error": 0,
        "errors": [],
    }

    async with AsyncSessionLocal() as session:
        for i, question in enumerate(questions_data, 1):
            # Process based on format
            if detected_format == "preresolved":
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

            # Insert into database
            try:
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                stmt = pg_insert(QuestionBank).values(**insert_data)
                await session.execute(stmt)
                await session.commit()
                stats["inserted"] += 1
            except IntegrityError as e:
                await session.rollback()
                if "canonical_form" in str(e):
                    stats["skipped_duplicate"] += 1
                else:
                    stats["skipped_error"] += 1
                    stats["errors"].append(f"Row {i}: {e}")
            except Exception as e:
                await session.rollback()
                stats["skipped_error"] += 1
                stats["errors"].append(f"Row {i}: {e}")

    # Log errors to file
    if stats["errors"]:
        log_dir = Path("backend/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        error_log = log_dir / "import_errors.log"
        with open(error_log, "w", encoding="utf-8") as f:
            for error in stats["errors"]:
                f.write(error + "\n")
        logger.info("Errors logged", path=str(error_log))

    return stats


def print_stats(stats: dict):
    """Print import statistics."""
    print("\n" + "=" * 50)
    print("IMPORT STATISTICS")
    print("=" * 50)
    print(f"Total rows:        {stats['total']}")
    print(f"Inserted:          {stats['inserted']}")
    print(f"Skipped (dup):     {stats['skipped_duplicate']}")
    print(f"Skipped (err):     {stats['skipped_error']}")
    if stats["errors"]:
        print("Errors logged:     backend/logs/import_errors.log")
    print("=" * 50)


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
        "--dry-run",
        action="store_true",
        help="Validate and resolve all rows without writing to DB",
    )

    args = parser.parse_args()

    try:
        stats = await import_questions(args.file, args.format, args.dry_run)
        print_stats(stats)

        if stats["skipped_error"] > 0:
            sys.exit(1)
    except Exception as e:
        logger.error("Import failed", error=str(e))
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
