"""Validate and fix question bank questions using LLM quality review.

Three modes:
  validate-existing  — Read active questions from the DB, validate per-subtopic
                       batch, output fixes_to_apply.json for failed questions.
  validate-generated — Read a generated JSON file (from generate_gap_questions.py),
                       validate, output a corrected JSON file ready for import.
  apply-fixes        — Apply a fixes_to_apply.json to the database by INSERTING
                       new correction records (not UPDATING originals).

IMPORTANT: apply-fixes now CREATES new question records with is_active=false
and replaces_question_id pointing to the original. Originals are NOT modified.
Approve corrections via the KaihleAdmin UI.

The validator uses a SEPARATE, more capable LLM (configured via
LLM_QUESTION_QUALITY_MODEL) to review the generator's output. This catches
factual errors, difficulty misalignment, and content-domain contamination
that the generator's own validation can't spot.

Per-subtopic batching: 15 questions per LLM call (one subtopic's full set).
Each question is validated independently for:
  - Factual accuracy (re-solves the question independently)
  - Difficulty calibration (matches the subject-specific rubric)
  - Subtopic alignment (tests the stated learning objective)
  - Distractor quality (MCQ: plausible? non-duplicate?)
  - Content-domain (ENG: no history/science factual recall)

Usage:
    # Validate existing DB questions (dry-run first — no DB writes):
    python -m scripts.validate_and_fix_questions \\
      --mode validate-existing --subject ENG --dry-run

    # Validate existing DB questions and write fixes:
    python -m scripts.validate_and_fix_questions \\
      --mode validate-existing --subject ENG

    # Validate a generated JSON file:
    python -m scripts.validate_and_fix_questions \\
      --mode validate-generated --file gap_questions_ENG.json

    # Apply fixes to the DB:
    python -m scripts.validate_and_fix_questions \\
      --mode apply-fixes --file fixes_to_apply.json

    # Filter by grade:
    python -m scripts.validate_and_fix_questions \\
      --mode validate-existing --subject ENG --grade 6,7,8

    # Limit the number of subtopics to process (for testing):
    python -m scripts.validate_and_fix_questions \\
      --mode validate-existing --subject ENG --limit 2
"""

import argparse
import asyncio
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Bootstrap path so we can import app modules
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.ai.providers.router import complete  # noqa: E402
from app.core.config import settings  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Validation output directory
# ---------------------------------------------------------------------------
VALIDATION_DIR = _BACKEND_ROOT / "validation_reports"
VALIDATION_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Subject-specific difficulty rubrics (same as generate_gap_questions.py)
# ---------------------------------------------------------------------------
DIFFICULTY_RUBRICS: dict[str, str] = {
    "ENG": """
DIFFICULTY RUBRIC FOR ENGLISH LANGUAGE:
  Level 1 — Direct recall of explicit information from a text, or identification
    of a basic language feature. Single step. ~30s. Bloom: Remember.
  Level 2 — Simple inference or understanding of a familiar concept. One-step
    reasoning with a clear clue in the text. ~45s. Bloom: Understand.
  Level 3 — Analysis of language effects, structure, or author's craft. Multi-step
    reasoning applying one concept. ~60s. Bloom: Apply/Analyze.
  Level 4 — Evaluation of arguments, comparison across texts, or analysis of complex
    techniques. Multiple concepts integrated. ~90s. Bloom: Analyze.
  Level 5 — Synthesis of ideas across texts, critical evaluation of authorial choices,
    or extended analytical reasoning. ~120s. Bloom: Evaluate.
""",
    "MATH": """
DIFFICULTY RUBRIC FOR MATHEMATICS:
  Level 1 — Direct recall of a formula, definition, or single arithmetic operation.
    ~30s. Bloom: Remember.
  Level 2 — Simple application of one formula or concept. Two-step calculation
    in a familiar context. ~45s. Bloom: Understand.
  Level 3 — Multi-step problem applying one concept in an unfamiliar context.
    Requires setting up the problem. ~60s. Bloom: Apply.
  Level 4 — Integration of multiple mathematical concepts. Word problem requiring
    problem decomposition. ~90s. Bloom: Analyze.
  Level 5 — Proof, generalisation, or multi-concept novel reasoning. Requires
    abstract thinking or justification. ~120s. Bloom: Evaluate/Create.
""",
    "SCI": """
DIFFICULTY RUBRIC FOR INTEGRATED SCIENCE:
  Level 1 — Recall a definition, fact, or scientific term. ~30s. Bloom: Remember.
  Level 2 — Understand a concept in a familiar context. ~45s. Bloom: Understand.
  Level 3 — Apply a concept to a new situation. Multi-step reasoning. ~60s. Bloom: Apply.
  Level 4 — Analyse data, compare theories, or multi-step calculation. ~90s. Bloom: Analyze.
  Level 5 — Evaluate evidence, synthesise ideas, or design an investigation. ~120s. Bloom: Evaluate.
""",
    "BIO": """
DIFFICULTY RUBRIC FOR BIOLOGY:
  Level 1 — Recall a definition, structure, or process name. ~30s. Bloom: Remember.
  Level 2 — Understand a process in a familiar context. ~45s. Bloom: Understand.
  Level 3 — Apply biological knowledge to a new scenario. ~60s. Bloom: Apply.
  Level 4 — Analyse relationships between structures/processes. ~90s. Bloom: Analyze.
  Level 5 — Evaluate evidence, synthesise across systems. ~120s. Bloom: Evaluate.
""",
    "CHEM": """
DIFFICULTY RUBRIC FOR CHEMISTRY:
  Level 1 — Recall a definition, formula, or element property. ~30s. Bloom: Remember.
  Level 2 — Understand a reaction or concept in a familiar context. ~45s. Bloom: Understand.
  Level 3 — Apply chemical principles to a new situation. ~60s. Bloom: Apply.
  Level 4 — Analyse experimental data, multi-step calculations. ~90s. Bloom: Analyze.
  Level 5 — Evaluate evidence, synthesise reaction pathways. ~120s. Bloom: Evaluate.
""",
    "PHY": """
DIFFICULTY RUBRIC FOR PHYSICS:
  Level 1 — Recall a law, definition, or formula. ~30s. Bloom: Remember.
  Level 2 — Understand a concept in a familiar context. ~45s. Bloom: Understand.
  Level 3 — Apply a formula to a multi-step problem. ~60s. Bloom: Apply.
  Level 4 — Analyse forces/energy in complex systems. ~90s. Bloom: Analyze.
  Level 5 — Evaluate experimental evidence, synthesise concepts. ~120s. Bloom: Evaluate.
""",
}

DEFAULT_RUBRIC = """
DIFFICULTY RUBRIC:
  Level 1 — Recall. ~30s.
  Level 2 — Understand. ~45s.
  Level 3 — Apply. ~60s.
  Level 4 — Analyse. ~90s.
  Level 5 — Evaluate/Create. ~120s.
"""

# ---------------------------------------------------------------------------
# Subject-specific validation rules
# ---------------------------------------------------------------------------
VALIDATION_RULES: dict[str, str] = {
    "ENG": """
CONTENT-DOMAIN CHECK:
  - The question must test a LANGUAGE SKILL (inference, author intent, language
    analysis, narrative technique, etc.), NOT factual recall of any subject.
  - Flag any question that asks about historical events, scientific facts,
    geographical locations, or any content-domain knowledge.
  - The question should be answerable from the passage excerpt alone, not from
    prior knowledge of the topic.
  - EXCEPTION: Questions about "English in the World" or "Language Change" at
    AS/A Level may reference historical/social contexts — these are valid IF
    they test linguistic analysis, not the historical facts themselves.
""",
    "MATH": """
FACTUAL ACCURACY CHECK:
  - Re-solve every calculation independently. Verify the correct_answer.
  - Check that MCQ distractors represent common student errors (wrong operation,
    sign error, incorrect formula, off-by-one, unit confusion).
  - Flag any question where the correct answer is mathematically wrong.
""",
    "SCI": """
CONTENT ACCURACY CHECK:
  - Verify all scientific claims are factually correct for the grade level.
  - For SCI (Integrated Science, Grades 6-8): ensure content is age-appropriate.
  - Check that misconceptions used as distractors are genuine Grade 6-8 errors.
""",
    "BIO": """
CONTENT ACCURACY CHECK:
  - Verify all biological statements are factually correct.
  - Grades 9-10: IGCSE scope only. Grades 11-12: AS & A Level scope only.
  - Check that distractors reflect common biology misconceptions.
""",
    "CHEM": """
CONTENT ACCURACY CHECK:
  - Verify all chemical equations, formulas, and statements are correct.
  - Check that numerical answers (moles, concentration, mass) are correct.
  - Distractors must reflect typical student errors.
""",
    "PHY": """
CONTENT ACCURACY CHECK:
  - Verify all physics laws, constants, and formulae are correct.
  - Check that numerical answers have correct significant figures.
  - Distractors must reflect common errors (wrong formula, inverted relationship).
""",
}

DEFAULT_VALIDATION = """
FACTUAL ACCURACY CHECK:
  - Verify the correct_answer is factually correct.
  - Check that the question actually tests the subtopic's learning objective.
  - Flag any question with incorrect or misleading content.
"""

# ---------------------------------------------------------------------------
# Helpers: canonical form and problem signature
# ---------------------------------------------------------------------------

_TF_PREFIX_RE = re.compile(r"^true or false\s*:", re.IGNORECASE)
_STOP_WORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "what",
        "which",
        "how",
        "does",
        "do",
        "did",
        "of",
        "in",
        "to",
        "true",
        "false",
    }
)


def make_canonical_form(question_text: str) -> str:
    """Normalize question text for dedup/identity."""
    text = question_text.lower()
    text = _TF_PREFIX_RE.sub("", text).strip()
    text = re.sub(r"[^\w\s]", " ", text)
    words = [w for w in text.split() if w not in _STOP_WORDS]
    return " ".join(words)


def make_problem_signature(q: dict[str, Any]) -> dict[str, Any]:
    """Build a structural fingerprint of the question."""
    canon = make_canonical_form(q.get("question_text", ""))
    return {
        "type": q.get("question_type"),
        "difficulty": q.get("difficulty_level"),
        "concept_hash": hashlib.md5(canon.encode()).hexdigest()[:12],
        "bloom_level": q.get("bloom_taxonomy_level"),
        "has_options": isinstance(q.get("options"), dict),
    }


# ---------------------------------------------------------------------------
# Build the validation prompt
# ---------------------------------------------------------------------------


def build_validation_prompt(
    subtopic_info: dict[str, Any],
    questions: list[dict[str, Any]],
) -> str:
    """Build a prompt that validates all questions for one subtopic.

    The LLM reviews each question independently and returns structured JSON
    with pass/fail per validation criterion, plus corrected versions for
    any failed questions.
    """
    subject_code = subtopic_info["subject_code"]
    rubric = DIFFICULTY_RUBRICS.get(subject_code, DEFAULT_RUBRIC)
    rules = VALIDATION_RULES.get(subject_code, DEFAULT_VALIDATION)

    questions_json = json.dumps(questions, indent=2, ensure_ascii=False)

    return f"""You are a quality assurance reviewer for Cambridge assessment questions.

You will receive a batch of questions for ONE subtopic. For EACH question,
you must independently evaluate it and — if it fails any check — generate
a corrected version.

SUBTOPIC CONTEXT:
- Subject:            {subtopic_info["subject_name"]} ({subject_code})
- Grade:              {subtopic_info["grade_level"]}
- Topic:              {subtopic_info["topic_name"]}
- Subtopic:           {subtopic_info["subtopic_name"]}
- Learning objective: {subtopic_info["learning_objective"]}

{rubric}

{rules}

VALIDATION PROCESS — for EACH question:
  1. SOLVE IT INDEPENDENTLY — do NOT trust the provided correct_answer.
     For MATH/SCI: actually compute the answer. For ENG: read the passage
     and verify the analysis. Compare your answer to the provided one.
  2. Check difficulty calibration against the rubric above.
  3. Check subtopic alignment: does it test the learning objective, or
     a different skill/content area?
  4. Check distractor quality (MCQ only): are all 4 options non-empty,
     unique, and plausibly wrong? No obviously wrong distractors.
  5. Check content-domain: (ENG only) does it test a language skill,
     not historical/scientific factual recall?
  6. If ANY check fails → generate a corrected version of the question.

OUTPUT FORMAT — return ONLY valid JSON, no markdown fences, no trailing commas:
{{
  "subtopic": "{subtopic_info["subtopic_name"]}",
  "subject_code": "{subject_code}",
  "grade_level": {subtopic_info["grade_level"]},
  "questions": [
    {{
      "index": 0,
      "overall_pass": true,
      "validations": {{
        "factual_accuracy": {{"pass": true, "note": "Verified independently — correct answer is correct"}},
        "difficulty_calibration": {{"pass": true, "note": "Appropriate for level {int(questions[0].get("difficulty_level") or 1) if questions else 1}"}},
        "subtopic_alignment": {{"pass": true, "note": "Directly tests the learning objective"}},
        "distractor_quality": {{"pass": true, "note": "All distractors are plausible misconceptions"}},
        "content_domain": {{"pass": true, "note": "No content-domain contamination"}}
      }},
      "corrected_question": null,
      "changes_made": []
    }}
  ]
}}

If a question FAILS any check, include a "corrected_question" object with
ALL fields needed to replace the original:
  - question_text, question_type, options (or null for TF), correct_answer,
    difficulty_level, bloom_taxonomy_level, estimated_time_seconds,
    learning_objectives, explanation, hints

Here are the questions to review:

{questions_json}
"""


# ---------------------------------------------------------------------------
# Fetch questions from the DB (validate-existing mode)
# ---------------------------------------------------------------------------


async def fetch_existing_questions(
    db,
    subject_filter: list[str] | None,
    grade_filter: list[int] | None,
    limit_subtopics: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch all active questions grouped by subtopic, with full hierarchy info.

    Returns a list of dicts, each representing one subtopic group:
    {
      "subtopic_info": { subtopic, topic, subject, grade, curriculum, ... },
      "questions": [ { question fields from question_bank }, ... ]
    }
    """
    where_clauses = ["s.code = ANY(:subjects)", "qb.is_active = true"]
    params: dict[str, Any] = {"subjects": subject_filter or ["ENG"]}

    if grade_filter:
        where_clauses.append("g.level = ANY(:grades)")
        params["grades"] = grade_filter

    where_sql = " AND ".join(where_clauses)

    # Fetch all active questions with their subtopic context
    result = await db.execute(
        sa_text(f"""
            SELECT
                qb.id                   AS question_id,
                qb.question_text,
                qb.question_type,
                qb.options,
                qb.correct_answer,
                qb.explanation,
                qb.hints,
                qb.difficulty_level,
                qb.bloom_taxonomy_level,
                qb.estimated_time_seconds,
                qb.learning_objectives,
                qb.canonical_form,
                qb.problem_signature,
                qb.subtopic_id,
                st.name                 AS subtopic_name,
                st.learning_objective,
                st.description          AS subtopic_description,
                t.name                  AS topic_name,
                s.code                  AS subject_code,
                s.name                  AS subject_name,
                g.level                 AS grade_level,
                c.code                  AS curriculum_code,
                c.name                  AS curriculum_name
            FROM question_bank qb
            JOIN subtopics st           ON st.id = qb.subtopic_id
            JOIN curriculum_topics ct   ON ct.id = st.curriculum_topic_id
            JOIN topics t               ON t.id  = ct.topic_id
            JOIN subjects s             ON s.id  = ct.subject_id
            JOIN grades g               ON g.id  = ct.grade_id
            JOIN curricula c            ON c.id  = ct.curriculum_id
            WHERE {where_sql}
            ORDER BY st.name, qb.difficulty_level, qb.question_text
        """),
        params,
    )
    rows = result.fetchall()

    if not rows:
        log.info("no_questions_found", subject_filter=subject_filter, grade_filter=grade_filter)
        return []

    # Group by subtopic_id
    subtopic_groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        r = dict(row._mapping)
        sub_id = str(r["subtopic_id"])

        if sub_id not in subtopic_groups:
            subtopic_groups[sub_id] = {
                "subtopic_info": {
                    "subtopic_id": sub_id,
                    "subtopic_name": r["subtopic_name"],
                    "learning_objective": r["learning_objective"],
                    "subtopic_description": r.get("subtopic_description") or "",
                    "topic_name": r["topic_name"],
                    "subject_code": r["subject_code"],
                    "subject_name": r["subject_name"],
                    "grade_level": r["grade_level"],
                    "curriculum_code": r["curriculum_code"],
                    "curriculum_name": r["curriculum_name"],
                },
                "questions": [],
            }

        subtopic_groups[sub_id]["questions"].append(
            {
                "question_id": str(r["question_id"]),
                "question_text": r["question_text"],
                "question_type": r["question_type"],
                "options": r["options"],
                "correct_answer": r["correct_answer"],
                "explanation": r["explanation"] or "",
                "hints": r["hints"] or {},
                "difficulty_level": r["difficulty_level"],
                "bloom_taxonomy_level": r["bloom_taxonomy_level"],
                "estimated_time_seconds": r["estimated_time_seconds"],
                "learning_objectives": r["learning_objectives"] or [],
            }
        )

    groups = list(subtopic_groups.values())

    if limit_subtopics:
        groups = groups[:limit_subtopics]

    log.info(
        "fetched_existing_questions",
        subject_groups=len(groups),
        total_questions=sum(len(g["questions"]) for g in groups),
    )
    return groups


# ---------------------------------------------------------------------------
# Parse generated JSON (validate-generated mode)
# ---------------------------------------------------------------------------


def parse_generated_file(file_path: str) -> list[dict[str, Any]]:
    """Parse a generated JSON file and group questions by subtopic.

    The generated file has a flat "questions" array. We group them by
    (subject_code, grade_level, topic_name, subtopic_name) for batching.
    """
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    raw_questions = data.get("questions", [])
    if not raw_questions:
        log.error("no_questions_in_file", path=file_path)
        return []

    # Group by hierarchy
    groups: dict[str, dict[str, Any]] = {}
    for q in raw_questions:
        key = f"{q.get('subject_name', '')}/{q.get('grade_level', '')}/{q.get('topic_name', '')}/{q.get('subtopic_name', '')}"

        if key not in groups:
            groups[key] = {
                "subtopic_info": {
                    "subtopic_name": q.get("subtopic_name", ""),
                    "learning_objective": q.get("learning_objective", ""),
                    "subtopic_description": "",
                    "topic_name": q.get("topic_name", ""),
                    "subject_code": q.get("subject_name", ""),
                    "subject_name": q.get("subject_name", ""),
                    "grade_level": q.get("grade_level", 0),
                    "curriculum_code": "",
                    "curriculum_name": "",
                },
                "questions": [],
            }

        groups[key]["questions"].append(
            {
                "question_text": q.get("question_text", ""),
                "question_type": q.get("question_type", ""),
                "options": q.get("options"),
                "correct_answer": q.get("correct_answer", ""),
                "explanation": q.get("explanation", ""),
                "hints": q.get("hints", {}),
                "difficulty_level": q.get("difficulty_level", 1),
                "bloom_taxonomy_level": q.get("bloom_taxonomy_level", ""),
                "estimated_time_seconds": q.get("estimated_time_seconds", 30),
                "learning_objectives": q.get("learning_objectives", []),
                # Preserve the original subtopic_id for the output
                "_original_subtopic_id": q.get("subtopic_id"),
                "_original_row": q,
            }
        )

    log.info(
        "parsed_generated_file",
        groups=len(groups),
        questions=sum(len(g["questions"]) for g in groups.values()),
        path=file_path,
    )
    return list(groups.values())


# ---------------------------------------------------------------------------
# Per-subtopic LLM validation
# ---------------------------------------------------------------------------


async def validate_subtopic_batch(
    subtopic_group: dict[str, Any],
    semaphore: asyncio.Semaphore,
    dry_run: bool,
) -> dict[str, Any]:
    """Validate all questions for one subtopic. Returns the validation result."""
    subtopic_info = subtopic_group["subtopic_info"]
    questions = subtopic_group["questions"]

    if dry_run:
        log.info(
            "dry_run_subtopic",
            subject=subtopic_info.get("subject_code", subtopic_info.get("subtopic_name", "?")),
            grade=subtopic_info.get("grade_level", "?"),
            subtopic=subtopic_info.get("subtopic_name", "?"),
            questions=len(questions),
        )
        return {
            "subtopic": subtopic_info["subtopic_name"],
            "subject_code": subtopic_info.get("subject_code", ""),
            "grade_level": subtopic_info.get("grade_level", 0),
            "questions": [
                {
                    "index": i,
                    "overall_pass": None,
                    "validations": {},
                    "corrected_question": None,
                    "changes_made": [],
                }
                for i in range(len(questions))
            ],
            "pass_rate": "dry_run",
            "summary": "Dry run — no LLM call made",
        }

    # Map subject_code to a usable code for rubrics
    subject_code = subtopic_info.get("subject_code", "")
    subject_code_map = {
        "English Language": "ENG",
        "English": "ENG",
        "Mathematics": "MATH",
        "Math": "MATH",
        "Science": "SCI",
        "Biology": "BIO",
        "Chemistry": "CHEM",
        "Physics": "PHY",
    }
    mapped_code = subject_code_map.get(subject_code, subject_code)
    subtopic_info["subject_code"] = mapped_code

    # Chunk questions into smaller batches so the LLM can properly validate
    # each one without hitting token limits or getting truncated.
    CHUNK_SIZE = 15

    async def _validate_chunk(chunk_questions: list[dict[str, Any]], chunk_start_idx: int) -> list[dict[str, Any]]:
        """Validate a chunk of at most CHUNK_SIZE questions and return per-question results."""
        prompt = build_validation_prompt(subtopic_info, chunk_questions)

        log.info(
            "validating_subtopic_chunk",
            subject=mapped_code,
            grade=subtopic_info["grade_level"],
            subtopic=subtopic_info["subtopic_name"],
            chunk_start=chunk_start_idx,
            questions=len(chunk_questions),
        )

        async with semaphore:
            try:
                response_text = await complete(
                    task="question_quality",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a strict quality assurance reviewer for Cambridge assessment questions. "
                                "Output valid JSON only. No markdown fences. No text outside the JSON object. "
                                "Be thorough — re-solve every question independently."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=12000,
                )
            except Exception as exc:
                log.error(
                    "llm_validation_failed",
                    error=str(exc),
                    subtopic=subtopic_info["subtopic_name"],
                    chunk_start=chunk_start_idx,
                )
                return [
                    {
                        "index": chunk_start_idx + i,
                        "overall_pass": False,
                        "validations": {},
                        "corrected_question": None,
                        "changes_made": [],
                        "error": f"LLM call failed: {exc}",
                    }
                    for i in range(len(chunk_questions))
                ]

            # Strip markdown fences
            response_text = response_text.strip()
            if response_text.startswith("```"):
                response_text = re.sub(r"^```(?:json)?\s*", "", response_text)
                response_text = re.sub(r"\s*```\s*$", "", response_text.strip())

            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as exc:
                log.error(
                    "validation_response_parse_failed",
                    error=str(exc),
                    subtopic=subtopic_info["subtopic_name"],
                    chunk_start=chunk_start_idx,
                    preview=response_text[:300],
                )
                return [
                    {
                        "index": chunk_start_idx + i,
                        "overall_pass": False,
                        "validations": {},
                        "corrected_question": None,
                        "changes_made": [],
                        "error": "Failed to parse validation response",
                    }
                    for i in range(len(chunk_questions))
                ]

            q_results = result.get("questions", [])
            # Re-index to global positions
            for qr in q_results:
                qr["index"] = chunk_start_idx + qr.get("index", 0)
            return q_results

    # Split questions into chunks and validate each
    chunks = [questions[i : i + CHUNK_SIZE] for i in range(0, len(questions), CHUNK_SIZE)]
    all_question_results: list[dict[str, Any]] = []
    for ci, chunk in enumerate(chunks):
        chunk_start = ci * CHUNK_SIZE
        chunk_results = await _validate_chunk(chunk, chunk_start)
        all_question_results.extend(chunk_results)

    # Aggregate results
    passed = sum(1 for qr in all_question_results if qr.get("overall_pass") is True)
    total = len(all_question_results)

    log.info(
        "subtopic_validated",
        subject=mapped_code,
        grade=subtopic_info["grade_level"],
        subtopic=subtopic_info["subtopic_name"],
        pass_rate=f"{passed}/{total}",
    )

    return {
        "subtopic": subtopic_info["subtopic_name"],
        "subject_code": mapped_code,
        "grade_level": subtopic_info["grade_level"],
        "questions": all_question_results,
        "pass_rate": f"{passed}/{total}",
        "summary": f"{passed}/{total} questions passed. {total - passed} questions need fixes.",
    }


# ---------------------------------------------------------------------------
# Build the fixes output
# ---------------------------------------------------------------------------


def build_fixes_from_validation(
    validation_results: list[dict[str, Any]],
    subtopic_groups: list[dict[str, Any]],
    source: str = "existing",
) -> list[dict[str, Any]]:
    """Build a list of fixes from validation results.

    Each fix has:
      - question_id (if source="existing"): UUID from the DB
      - corrected: the corrected question fields
      - changes_made: list of what changed
      - subtopic_info: context for the fix
    """
    fixes: list[dict[str, Any]] = []

    for val_result, group in zip(validation_results, subtopic_groups):
        q_results = val_result.get("questions", [])
        original_questions = group["questions"]

        for i, qr in enumerate(q_results):
            if qr.get("overall_pass") is False and qr.get("corrected_question"):
                corrected = qr["corrected_question"]
                original = original_questions[i] if i < len(original_questions) else {}

                fix = {
                    "subtopic_info": {
                        "subtopic_name": val_result.get("subtopic", group["subtopic_info"]["subtopic_name"]),
                        "subject_code": val_result.get("subject_code", group["subtopic_info"].get("subject_code", "")),
                        "grade_level": val_result.get("grade_level", group["subtopic_info"].get("grade_level", 0)),
                        "topic_name": group["subtopic_info"].get("topic_name", ""),
                        "learning_objective": group["subtopic_info"].get("learning_objective", ""),
                    },
                    "original": {
                        "question_text": original.get("question_text", ""),
                        "difficulty_level": original.get("difficulty_level", 1),
                        "correct_answer": original.get("correct_answer", ""),
                    },
                    "corrected": corrected,
                    "changes_made": qr.get("changes_made", []),
                    "validations": qr.get("validations", {}),
                }

                # Include question_id if available (from DB)
                if "question_id" in original:
                    fix["question_id"] = original["question_id"]
                    fix["subtopic_id"] = original.get("subtopic_id")

                fixes.append(fix)

    return fixes


def build_corrected_generated_file(
    validation_results: list[dict[str, Any]],
    subtopic_groups: list[dict[str, Any]],
    original_file_data: dict[str, Any],
) -> dict[str, Any]:
    """Build a corrected version of the generated questions file.

    For each question that failed validation, replace it with the corrected version.
    """
    # Build a mapping: (index_within_group, group_index) -> corrected question
    corrections: dict[tuple[int, int], dict] = {}

    for gi, (val_result, group) in enumerate(zip(validation_results, subtopic_groups)):
        q_results = val_result.get("questions", [])
        for i, qr in enumerate(q_results):
            if qr.get("overall_pass") is False and qr.get("corrected_question"):
                corrections[(gi, i)] = qr["corrected_question"]

    # Apply corrections to the original questions
    corrected_questions = list(original_file_data.get("questions", []))
    flat_idx = 0
    for gi, group in enumerate(subtopic_groups):
        for i in range(len(group["questions"])):
            if flat_idx < len(corrected_questions) and (gi, i) in corrections:
                corr = corrections[(gi, i)]
                # Overwrite fields that were corrected
                for field in (
                    "question_text",
                    "question_type",
                    "options",
                    "correct_answer",
                    "difficulty_level",
                    "bloom_taxonomy_level",
                    "estimated_time_seconds",
                    "learning_objectives",
                    "explanation",
                    "hints",
                ):
                    if field in corr:
                        corrected_questions[flat_idx][field] = corr[field]
                # Recalculate canonical_form and problem_signature
                corrected_questions[flat_idx]["canonical_form"] = make_canonical_form(
                    corr.get("question_text", corrected_questions[flat_idx].get("question_text", ""))
                )
                corrected_questions[flat_idx]["problem_signature"] = make_problem_signature(
                    corrected_questions[flat_idx]
                )
            flat_idx += 1

    output = dict(original_file_data)
    output["questions"] = corrected_questions
    output["_validation_applied"] = datetime.now().isoformat()
    output["_fixes_applied"] = sum(1 for _ in corrections.values())

    return output


# ---------------------------------------------------------------------------
# Apply fixes to the DB
# ---------------------------------------------------------------------------


async def apply_fixes_to_db(
    db,
    fixes: list[dict[str, Any]],
    dry_run: bool,
) -> int:
    """Apply fixes to the question_bank table.

    For each fix, creates a NEW question record (INSERT) with:
      - Corrected fields from the LLM
      - is_active = False (pending human review)
      - source = 'llm-correction'
      - replaces_question_id = original question's id
      - canonical_form and problem_signature recalculated

    The original question remains active until a human approves the correction
    via the KaihleAdmin UI.

    Returns the number of corrections created.
    """
    applied = 0

    for fix in fixes:
        question_id = fix.get("question_id")
        subtopic_id = fix.get("subtopic_id")
        if not question_id:
            log.warning("fix_missing_question_id", subtopic=fix.get("subtopic_info", {}).get("subtopic_name", "?"))
            continue
        if not subtopic_id:
            log.warning("fix_missing_subtopic_id", question_id=question_id)
            continue

        corrected = fix.get("corrected", {})
        if not corrected:
            continue

        # Recalculate canonical_form and problem_signature
        new_canonical = make_canonical_form(corrected.get("question_text", ""))
        new_signature = make_problem_signature(corrected)

        # Build the insert — all fields needed for a new question row
        options_val = corrected.get("options")
        hints = corrected.get("hints", {})
        learning_objectives = corrected.get("learning_objectives", [])

        insert_sql = sa_text("""
            INSERT INTO question_bank (
                subtopic_id,
                question_text,
                question_type,
                options,
                correct_answer,
                explanation,
                hints,
                difficulty_level,
                bloom_taxonomy_level,
                estimated_time_seconds,
                learning_objectives,
                canonical_form,
                problem_signature,
                source,
                is_active,
                replaces_question_id
            ) VALUES (
                CAST(:subtopic_id AS uuid),
                :question_text,
                :question_type,
                CAST(:options AS jsonb),
                :correct_answer,
                :explanation,
                CAST(:hints AS jsonb),
                :difficulty_level,
                :bloom_taxonomy_level,
                :estimated_time_seconds,
                :learning_objectives,
                :canonical_form,
                CAST(:problem_signature AS jsonb),
                'llm-correction',
                false,
                CAST(:replaces_question_id AS uuid)
            )
        """)

        params = {
            "subtopic_id": subtopic_id,
            "replaces_question_id": question_id,
            "question_text": corrected.get("question_text", ""),
            "question_type": corrected.get("question_type", ""),
            "options": json.dumps(options_val if isinstance(options_val, dict | list) else None),
            "correct_answer": corrected.get("correct_answer", ""),
            "explanation": corrected.get("explanation", ""),
            "hints": json.dumps(hints if isinstance(hints, dict) else {}),
            "difficulty_level": corrected.get("difficulty_level", 1),
            "bloom_taxonomy_level": corrected.get("bloom_taxonomy_level", ""),
            "estimated_time_seconds": corrected.get("estimated_time_seconds", 30),
            "learning_objectives": learning_objectives if isinstance(learning_objectives, list) else [],
            "canonical_form": new_canonical,
            "problem_signature": json.dumps(new_signature),
        }

        if dry_run:
            log.info(
                "dry_run_would_insert_correction",
                question_id=question_id,
                subtopic=fix.get("subtopic_info", {}).get("subtopic_name", "?"),
                changes=fix.get("changes_made", []),
            )
            applied += 1
        else:
            await db.execute(insert_sql, params)
            applied += 1
            log.info(
                "correction_inserted",
                replaces_question_id=question_id,
                subtopic=fix.get("subtopic_info", {}).get("subtopic_name", "?"),
                changes=fix.get("changes_made", []),
            )

    if not dry_run:
        await db.commit()
        log.info("corrections_committed", count=applied)

    return applied


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------


def write_report(
    validation_results: list[dict[str, Any]],
    output_name: str,
) -> Path:
    """Write the full quality report JSON."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = VALIDATION_DIR / f"quality_report_{output_name}_{timestamp}.json"

    # Aggregate stats
    total_questions = 0
    total_passed = 0
    total_failed = 0
    total_errors = 0

    for vr in validation_results:
        for qr in vr.get("questions", []):
            total_questions += 1
            if qr.get("overall_pass") is True:
                total_passed += 1
            elif qr.get("error"):
                total_errors += 1
            else:
                total_failed += 1

    report = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_subtopics": len(validation_results),
            "total_questions": total_questions,
            "passed": total_passed,
            "failed": total_failed,
            "errors": total_errors,
            "pass_rate": f"{total_passed}/{total_questions}" if total_questions else "0/0",
            "needs_fixes": total_failed,
        },
        "subtopic_results": validation_results,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    log.info(
        "report_written",
        path=str(report_path),
        passed=total_passed,
        failed=total_failed,
        errors=total_errors,
    )
    return report_path


def print_summary(validation_results: list[dict[str, Any]]) -> None:
    """Print a human-readable summary to the terminal."""
    total_q = 0
    total_p = 0
    total_f = 0
    total_e = 0

    print("\n" + "=" * 70)
    print("QUALITY VALIDATION SUMMARY")
    print("=" * 70)

    for vr in validation_results:
        label = f"{vr.get('subject_code', '?')} G{vr.get('grade_level', '?')} — {vr.get('subtopic', '?')}"
        q_results = vr.get("questions", [])
        passed = sum(1 for q in q_results if q.get("overall_pass") is True)
        failed = sum(1 for q in q_results if q.get("overall_pass") is False)
        errors = sum(1 for q in q_results if q.get("error"))
        total_q += len(q_results)
        total_p += passed
        total_f += failed
        total_e += errors

        if errors:
            print(f"  ❌ {label}: {passed}/{len(q_results)} pass, {failed} fail, {errors} errors")
        elif failed:
            print(f"  ⚠️  {label}: {passed}/{len(q_results)} pass, {failed} fail")
        else:
            print(f"  ✅ {label}: {passed}/{len(q_results)} pass")

    print("-" * 70)
    print(f"  TOTAL: {total_p}/{total_q} passed, {total_f} failed, {total_e} errors")
    print(f"  Fixes needed: {total_f} questions")
    print("=" * 70)
    print()


# ---------------------------------------------------------------------------
# Mode 1: validate-existing
# ---------------------------------------------------------------------------


async def run_validate_existing(
    subject_filter: list[str],
    grade_filter: list[int] | None,
    dry_run: bool,
    limit: int | None,
    concurrency: int,
) -> int:
    """Read active questions from DB, validate, write fixes."""
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with async_session() as db:
            subtopic_groups = await fetch_existing_questions(
                db,
                subject_filter=subject_filter,
                grade_filter=grade_filter,
                limit_subtopics=limit,
            )

        if not subtopic_groups:
            log.info("no_questions_to_validate")
            return 0

        log.info("validation_start", groups=len(subtopic_groups), dry_run=dry_run)

        semaphore = asyncio.Semaphore(concurrency)
        validation_results = await asyncio.gather(
            *[validate_subtopic_batch(g, semaphore, dry_run=dry_run) for g in subtopic_groups]
        )

        # Filter out dry_run results for reporting
        real_results = [r for r in validation_results if r.get("pass_rate") != "dry_run"]
        if real_results:
            print_summary(real_results)

        if dry_run:
            log.info("dry_run_complete", would_validate=len(subtopic_groups))
            return 0

        # Write quality report
        ts = "_".join(subject_filter) if subject_filter else "all"
        write_report(validation_results, f"existing_{ts}")

        # Build fixes
        fixes = build_fixes_from_validation(validation_results, subtopic_groups, source="existing")

        if not fixes:
            log.info("all_questions_pass — no fixes needed")
            return 0

        # Write fixes JSON
        fixes_path = VALIDATION_DIR / f"fixes_to_apply_{ts}.json"
        fixes_data = {
            "generated_at": datetime.now().isoformat(),
            "source": "validate-existing",
            "subject_filter": subject_filter,
            "grade_filter": grade_filter,
            "total_fixes": len(fixes),
            "fixes": fixes,
        }
        with open(fixes_path, "w", encoding="utf-8") as f:
            json.dump(fixes_data, f, indent=2, ensure_ascii=False)

        log.info(
            "fixes_written",
            path=str(fixes_path),
            count=len(fixes),
            hint=f"Run: python -m scripts.validate_and_fix_questions --mode apply-fixes --file {fixes_path.name}",
        )

        return 0

    except Exception as exc:
        log.error("validate_existing_failed", error=str(exc), exc_info=True)
        return 1
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Mode 2: validate-generated
# ---------------------------------------------------------------------------


async def run_validate_generated(
    file_path: str,
    dry_run: bool,
    limit: int | None,
    concurrency: int,
) -> int:
    """Read a generated JSON file, validate, output corrected JSON."""
    with open(file_path, encoding="utf-8") as f:
        original_data = json.load(f)

    subtopic_groups = parse_generated_file(file_path)
    if not subtopic_groups:
        return 1

    if limit:
        subtopic_groups = subtopic_groups[:limit]

    log.info("validation_start", groups=len(subtopic_groups), dry_run=dry_run)

    semaphore = asyncio.Semaphore(concurrency)
    validation_results = await asyncio.gather(
        *[validate_subtopic_batch(g, semaphore, dry_run=dry_run) for g in subtopic_groups]
    )

    real_results = [r for r in validation_results if r.get("pass_rate") != "dry_run"]
    if real_results:
        print_summary(real_results)

    if dry_run:
        log.info("dry_run_complete", would_validate=len(subtopic_groups))
        return 0

    # Write quality report
    in_name = Path(file_path).stem
    write_report(validation_results, f"generated_{in_name}")

    # Build corrected file
    corrected = build_corrected_generated_file(validation_results, subtopic_groups, original_data)

    out_path = Path(file_path).with_suffix(".corrected.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(corrected, f, indent=2, ensure_ascii=False)

    fixes_applied = corrected.get("_fixes_applied", 0)
    log.info(
        "corrected_file_written",
        path=str(out_path),
        fixes_applied=fixes_applied,
        total_questions=len(corrected.get("questions", [])),
    )

    return 0


# ---------------------------------------------------------------------------
# Mode 3: apply-fixes
# ---------------------------------------------------------------------------


async def run_apply_fixes(
    file_path: str,
    dry_run: bool,
) -> int:
    """Insert correction records from a fixes_to_apply.json into the database."""
    with open(file_path, encoding="utf-8") as f:
        fixes_data = json.load(f)

    fixes = fixes_data.get("fixes", [])
    if not fixes:
        log.info("no_fixes_to_apply")
        return 0

    log.info("creating_corrections", count=len(fixes), dry_run=dry_run)

    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with async_session() as db:
            applied = await apply_fixes_to_db(db, fixes, dry_run=dry_run)

        log.info(
            "corrections_created",
            applied=applied,
            total=len(fixes),
            dry_run=dry_run,
        )
        return 0

    except Exception as exc:
        log.error("apply_fixes_failed", error=str(exc), exc_info=True)
        return 1
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def main(args: argparse.Namespace) -> int:
    mode = args.mode

    if mode == "validate-existing":
        subject_filter = [s.strip().upper() for s in args.subject.split(",")] if args.subject else ["ENG"]
        grade_filter = [int(g.strip()) for g in args.grade.split(",")] if args.grade else None
        return await run_validate_existing(
            subject_filter=subject_filter,
            grade_filter=grade_filter,
            dry_run=args.dry_run,
            limit=args.limit,
            concurrency=args.concurrency,
        )

    elif mode == "validate-generated":
        return await run_validate_generated(
            file_path=args.file,
            dry_run=args.dry_run,
            limit=args.limit,
            concurrency=args.concurrency,
        )

    elif mode == "apply-fixes":
        return await run_apply_fixes(
            file_path=args.file,
            dry_run=args.dry_run,
        )

    else:
        log.error("unknown_mode", mode=mode)
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Validate and fix question bank questions using LLM quality review.\n"
            "\n"
            "THREE MODES:\n"
            "  validate-existing  — Read active questions from DB, validate, output fixes.\n"
            "  validate-generated — Read a generated JSON file, validate, output corrected JSON.\n"
            "  apply-fixes        — Insert correction records into the DB (is_active=false).\n"
            "\n"
            "Examples:\n"
            "  # Dry-run validation of existing ENG questions:\n"
            "  python -m scripts.validate_and_fix_questions \\\n"
            "    --mode validate-existing --subject ENG --dry-run\n"
            "\n"
            "  # Validate and generate fixes for existing ENG questions:\n"
            "  python -m scripts.validate_and_fix_questions \\\n"
            "    --mode validate-existing --subject ENG\n"
            "\n"
            "  # Validate a generated JSON file:\n"
            "  python -m scripts.validate_and_fix_questions \\\n"
            "    --mode validate-generated --file gap_questions_ENG.json\n"
            "\n"
            "  # Insert corrections into the DB (creates new inactive records):\n"
            "  python -m scripts.validate_and_fix_questions \\\n"
            "    --mode apply-fixes --file fixes_to_apply_ENG.json\n"
            "\n"
            "  # Filter by grade (validate-existing only):\n"
            "  python -m scripts.validate_and_fix_questions \\\n"
            "    --mode validate-existing --subject ENG --grade 6,7,8\n"
            "\n"
            "  # Limit to N subtopics for testing:\n"
            "  python -m scripts.validate_and_fix_questions \\\n"
            "    --mode validate-existing --subject ENG --limit 2"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--mode",
        required=True,
        choices=["validate-existing", "validate-generated", "apply-fixes"],
        help="Operation mode (required).",
    )

    parser.add_argument(
        "--subject",
        default=None,
        metavar="CODE[,CODE...]",
        help=(
            "Subject code(s) for validate-existing mode. "
            "Comma-separated. Default: ENG.\n"
            "Examples: --subject ENG   --subject MATH,BIO"
        ),
    )

    parser.add_argument(
        "--grade",
        default=None,
        metavar="LEVEL[,LEVEL...]",
        help=(
            "Grade level(s) for validate-existing mode. "
            "Comma-separated integers. Omit for all.\n"
            "Examples: --grade 6,7,8   --grade 9,10"
        ),
    )

    parser.add_argument(
        "--file",
        default=None,
        metavar="PATH",
        help=(
            "Path to the input JSON file for validate-generated or apply-fixes modes.\n"
            "Examples: --file gap_questions_ENG.json   --file fixes_to_apply_ENG.json"
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Show what would be validated without making any LLM calls or DB writes.\n"
            "For validate-existing: shows subtopics and question counts.\n"
            "For validate-generated: shows subtopics and question counts.\n"
            "For apply-fixes: shows which fixes would be applied."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Limit the number of subtopics to process (for testing). Default: all.",
    )

    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        metavar="N",
        help="How many subtopics to validate simultaneously (default: 3).",
    )

    args = parser.parse_args()

    # Validate args
    if args.mode in ("validate-generated", "apply-fixes") and not args.file:
        parser.error(f"--file is required for --mode {args.mode}")

    sys.exit(asyncio.run(main(args)))
