"""Generate questions for subtopics with missing question bank coverage.

Two modes:
  Default  — zero-coverage: subtopics with NO active questions at all.
  --fill-gaps — thin-coverage: subtopics missing questions at one or more difficulty
                levels (< MIN_QUESTIONS_PER_DIFFICULTY per level). Only generates for
                the specific difficulty levels that are under the minimum.

Two-step workflow:
  1. This script queries gap subtopics from the DB, generates questions via LLM,
     and writes a JSON file.
  2. A human reviews the JSON, then imports via:
       docker compose exec backend python -m scripts.import_questions \
         --file <output>.json --strategy preresolved          # same DB (dev/staging)
       docker compose exec backend python -m scripts.import_questions \
         --file <output>.json --strategy reresolve            # different DB (prod)

The JSON includes BOTH subtopic_id UUIDs (for preresolved) AND full name hierarchy
(grade_level, subject_name, topic_name, subtopic_name) so it can be imported on prod
without re-running any LLM calls.

LLM routing follows router.py:
  LLM_QUESTION_GENERATION_MODEL       — model name (e.g. gemini/gemini-2.5-flash)
  LLM_QUESTION_GENERATION_API_BASE    — optional custom endpoint (e.g. RunPod vLLM server)

Usage (from project root):
    # Generate for all subjects with zero-question subtopics:
    docker compose exec backend python -m scripts.generate_gap_questions

    # Target specific subjects and grades:
    docker compose exec backend python -m scripts.generate_gap_questions \
      --subject ENGL --grade 9,10

    docker compose exec backend python -m scripts.generate_gap_questions \
      --subject BIO,CHEM,PHY --grade 9,10,11,12

    # Fill thin-coverage subtopics (any level with < 3 questions):
    docker compose exec backend python -m scripts.generate_gap_questions \
      --subject MATH --fill-gaps

    # Dry run — shows what would be generated, no LLM calls:
    docker compose exec backend python -m scripts.generate_gap_questions \
      --subject ENG --dry-run

    # Resume an interrupted run from checkpoint:
    docker compose exec backend python -m scripts.generate_gap_questions \
      --resume checkpoints/gap_questions_checkpoint_20260516_120000.json

    # Control concurrency (default 3 — concurrent subtopic LLM calls):
    docker compose exec backend python -m scripts.generate_gap_questions \
      --subject BIO --concurrency 5

    # Outside Docker (requires env vars set):
    cd backend
    DATABASE_URL=postgresql+asyncpg://kaihle:kaihle@localhost:5433/kaihle \
    LLM_QUESTION_GENERATION_MODEL=openai/Qwen2.5-14B-Instruct \
    LLM_QUESTION_GENERATION_API_BASE=https://your-pod-id-8000.proxy.runpod.net/v1 \
      uv run python -m scripts.generate_gap_questions --subject ENGL
"""

import argparse
import asyncio
import hashlib
import html
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.ai.providers.router import complete  # noqa: E402
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

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

QUESTIONS_PER_DIFFICULTY = 3
DIFFICULTY_LEVELS = [1, 2, 3, 4, 5]
# Total per subtopic in zero-coverage mode: 3 × 5 = 15 questions in one LLM call
# In fill-gaps mode, only the under-covered difficulty levels are targeted.
MIN_QUESTIONS_PER_DIFFICULTY = 3  # threshold below which a level is considered thin

MAX_RETRIES = 3
DEFAULT_CONCURRENCY = 3
CHECKPOINT_EVERY = 10  # save after every N subtopics completed

# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

# Matches HTML tags, HTML entities, and non-printable/non-ASCII characters
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")


def clean_text(value: str) -> str:
    """Strip HTML tags, decode HTML entities, remove control characters."""
    if not isinstance(value, str):
        return value
    value = _HTML_TAG_RE.sub("", value)  # remove <b>, <br/>, etc.
    value = html.unescape(value)  # &amp; → &, &lt; → <, &#8220; → "
    value = _CONTROL_CHAR_RE.sub("", value)  # remove non-printable ASCII
    value = _MULTI_SPACE_RE.sub(" ", value)  # collapse multiple spaces
    return value.strip()


def clean_question(q: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of q with all string fields cleaned."""
    q = dict(q)
    for field in ("question_text", "correct_answer", "explanation"):
        if field in q and isinstance(q[field], str):
            q[field] = clean_text(q[field])

    if isinstance(q.get("options"), dict):
        q["options"] = {k: clean_text(v) for k, v in q["options"].items()}

    if isinstance(q.get("hints"), dict):
        q["hints"] = {k: clean_text(v) for k, v in q["hints"].items()}

    if isinstance(q.get("learning_objectives"), list):
        q["learning_objectives"] = [clean_text(o) for o in q["learning_objectives"] if isinstance(o, str)]

    return q


# ---------------------------------------------------------------------------
# Subject-specific guardrails (injected into every prompt for that subject)
# ---------------------------------------------------------------------------

SUBJECT_GUARDRAILS: dict[str, str] = {
    "ENG": """
CRITICAL GUARDRAILS FOR ENGLISH LANGUAGE:
- You are assessing a LANGUAGE SKILL, not subject-matter knowledge.
- The question MUST test the specific skill named in the subtopic (e.g. inference,
  author intent, language analysis, narrative technique).
- DO NOT ask factual recall questions about history, geography, science, or any
  other content domain — even if a passage about that domain could be used as context.
- WRONG: "Which event started World War II?" (tests history recall, not English skill)
- WRONG: "What is photosynthesis?" (tests science recall, not English skill)
- RIGHT: "What does the author imply by the phrase 'silent machine'?" (tests inference)
- RIGHT: "How does the writer create tension in paragraph 3?" (tests language analysis)
- Reading questions must test HOW the text works, not WHAT the content is about.
- Distractors for MCQ must represent common misreadings or misinterpretations of a text,
  not factually wrong statements about another subject.
""",
    "MATH": """
CRITICAL GUARDRAILS FOR MATHEMATICS:
- Every numerical answer MUST be mathematically correct — verify calculation before including.
- MCQ distractors must be common student errors: wrong operation, sign error, incorrect
  formula, off-by-one, unit confusion — NOT random numbers.
- Difficulty 1–2: single-step arithmetic or procedure recall.
- Difficulty 3: multi-step reasoning applying a single concept.
- Difficulty 4–5: proof, generalisation, or integration of multiple concepts.
- Do NOT generate trick questions that rely on ambiguous wording.
- State all units clearly. Do not leave numerical context ambiguous.
""",
    "SCI": """
CRITICAL GUARDRAILS FOR INTEGRATED SCIENCE (Cambridge Lower Secondary, Grades 6–8):
- Content must be factually accurate for Cambridge Lower Secondary level ONLY.
- SCI is an integrated framework — the subtopic tells you which strand (Physics,
  Chemistry, or Biology) and concept to assess. Stay within that strand.
- Do NOT introduce IGCSE-level depth (e.g. nuclear equations, organic mechanisms,
  mole calculations, genetics beyond simple inheritance).
- All scientific claims must be factually correct and age-appropriate for Grades 6–8.
- MCQ distractors should reflect common Grade 6–8 misconceptions about the concept.
""",
    "BIO": """
CRITICAL GUARDRAILS FOR BIOLOGY (Cambridge IGCSE / AS & A Level):
- Content must be scientifically accurate.
- Grades 9–10: IGCSE Biology scope only. Grades 11–12: AS & A Level scope only.
- Do NOT mix IGCSE and A-Level depth within the same question set.
- MCQ distractors must be common student misconceptions about the concept — e.g.
  confusing osmosis with diffusion, or mitosis with meiosis.
- Do NOT describe diagrams that cannot be clearly conveyed in text form.
""",
    "CHEM": """
CRITICAL GUARDRAILS FOR CHEMISTRY (Cambridge IGCSE / AS & A Level):
- All chemical equations, formulas, compound names, and element symbols must be correct.
- Grades 9–10: IGCSE Chemistry scope only. Grades 11–12: AS & A Level scope only.
- Do NOT include organic reaction mechanisms at IGCSE level.
- Numerical answers (moles, concentration, mass) must be mathematically verified.
- MCQ distractors must reflect typical student errors: wrong formula, reversed equation,
  incorrect state symbol, wrong valency.
""",
    "PHY": """
CRITICAL GUARDRAILS FOR PHYSICS (Cambridge IGCSE / AS & A Level):
- All physics laws, constants, and formulae must be correct.
- Grades 9–10: IGCSE Physics scope only. Grades 11–12: AS & A Level scope only.
- Numerical answers must be correct with appropriate significant figures.
- Do NOT mix SI and non-SI units within a single question.
- MCQ distractors must reflect common errors: wrong formula substitution, inverted
  relationship (e.g. confusing directly and inversely proportional), unit errors.
""",
    "ENGL": """
CRITICAL GUARDRAILS FOR ENGLISH LITERATURE (Cambridge IGCSE):
- Questions must assess literary analysis and textual interpretation skills, NOT plot recall.
- Focus on: author's craft, use of language, structure, form, themes, characterisation,
  context, and the effect of literary techniques on the reader.
- WRONG: "What happens at the end of chapter 3?" (plot recall — no marks in IGCSE)
- RIGHT: "How does the author use the motif of water to develop the theme of isolation?"
- For unseen text subtopics: use a short invented extract (2–4 lines of prose or poetry)
  directly in the question_text, then ask an analytical question about it. Do NOT assume
  the student has read a specific set text.
- For essay-writing subtopics: assess the analytical vocabulary and structural knowledge
  needed to write the essay — e.g. understanding of argument construction, use of evidence,
  awareness of form — not the essay content itself.
- True/False statements must be analytically nuanced, testing genuine literary understanding.
""",
    "HIST": """
CRITICAL GUARDRAILS FOR HISTORY:
- Questions must require historical reasoning, not mere memorisation of dates or names.
- Prioritise: causation, consequence, change over time, significance, source evaluation.
- Difficulty 1–2: identify key events or figures, recall key terms.
- Difficulty 3–4: explain causes or consequences, compare perspectives.
- Difficulty 5: evaluate competing historical interpretations or construct an argument.
- MCQ distractors must reflect common misunderstandings or plausible alternative
  interpretations — not obviously wrong statements.
""",
    "GEO": """
CRITICAL GUARDRAILS FOR GEOGRAPHY:
- Questions must be grounded in geographical concepts: place, space, environment,
  interconnection, sustainability, scale.
- Include both physical and human geography as appropriate to the subtopic.
- Numerical data used in questions must be realistic and verifiable.
- MCQ distractors must reflect genuine geographical misconceptions, not arbitrary facts.
""",
    "GP": """
CRITICAL GUARDRAILS FOR GLOBAL PERSPECTIVES:
- Questions must assess analytical and research skills about global issues, NOT factual recall.
- Focus on: identifying perspectives, evaluating evidence, argument construction,
  research methodology, and understanding multiple stakeholder viewpoints.
- Questions should not have a single "correct" political or ethical answer — assess
  reasoning skills and understanding of the process, not conclusions.
""",
}

DEFAULT_GUARDRAIL = """
CRITICAL GUARDRAILS:
- Questions must be factually accurate and age-appropriate.
- Each question must directly assess the specific subtopic skill named.
- Do NOT generate questions that test content from a different subject or topic.
"""

# ---------------------------------------------------------------------------
# Subject-specific difficulty rubrics (concrete operational definitions)
# WARNING: This dict is duplicated in backend/scripts/validate_and_fix_questions.py.
# Keep both in sync when adding or modifying rubrics.
# ---------------------------------------------------------------------------

DIFFICULTY_RUBRICS: dict[str, str] = {
    "ENG": """
DIFFICULTY RUBRIC FOR ENGLISH LANGUAGE:
  Level 1 — Direct recall of explicit information from a text, or identification
    of a basic language feature. Single step. ~30s. Bloom: Remember.
    Example: "Which word in the passage tells you the character is angry?"
  Level 2 — Simple inference or understanding of a familiar concept. One-step
    reasoning with a clear clue in the text. ~45s. Bloom: Understand.
    Example: "What does the phrase 'his voice trembled' suggest about the character?"
  Level 3 — Analysis of language effects, structure, or author's craft. Multi-step
    reasoning applying one concept. ~60s. Bloom: Apply/Analyze.
    Example: "How does the writer use imagery in paragraph 3 to create a sense of isolation?"
  Level 4 — Evaluation of arguments, comparison across texts, or analysis of complex
    techniques. Multiple concepts integrated. ~90s. Bloom: Analyze.
    Example: "Compare how the two writers use tone to convey their perspective on the same event."
  Level 5 — Synthesis of ideas across texts, critical evaluation of authorial choices,
    or extended analytical reasoning. ~120s. Bloom: Evaluate.
    Example: "Evaluate how effectively the writer's structural choices support their argument."
""",
    "MATH": """
DIFFICULTY RUBRIC FOR MATHEMATICS:
  Level 1 — Direct recall of a formula, definition, or single arithmetic operation.
    ~30s. Bloom: Remember.
    Example: "What is the formula for the area of a rectangle?"
  Level 2 — Simple application of one formula or concept. Two-step calculation
    in a familiar context. ~45s. Bloom: Understand.
    Example: "Calculate the area of a rectangle with length 8 cm and width 5 cm."
  Level 3 — Multi-step problem applying one concept in an unfamiliar context.
    Requires setting up the problem. ~60s. Bloom: Apply.
    Example: "A rectangular garden is 3 m longer than it is wide. If its perimeter is 30 m, find its area."
  Level 4 — Integration of multiple mathematical concepts. Word problem requiring
    problem decomposition. ~90s. Bloom: Analyze.
    Example: "A cylinder has a volume of 500 cm³ and height of 10 cm. A sphere has the same radius. Find the sphere's volume."
  Level 5 — Proof, generalisation, or multi-concept novel reasoning. Requires
    abstract thinking or justification. ~120s. Bloom: Evaluate/Create.
    Example: "Prove that the sum of the squares of the first n natural numbers is n(n+1)(2n+1)/6."
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
    "ENGL": """
DIFFICULTY RUBRIC FOR ENGLISH LITERATURE:
  Level 1 — Identify a literary device or recall a plot detail. ~30s. Bloom: Remember.
  Level 2 — Understand the effect of a simple device. ~45s. Bloom: Understand.
  Level 3 — Analyse language, structure, or form in a text. ~60s. Bloom: Apply/Analyze.
  Level 4 — Compare texts, evaluate themes, or analyse complex techniques. ~90s. Bloom: Analyze.
  Level 5 — Evaluate authorial choices, synthesise across texts, construct critical argument. ~120s. Bloom: Evaluate.
""",
    "HIST": """
DIFFICULTY RUBRIC FOR HISTORY:
  Level 1 — Recall a key event, date, or figure. ~30s. Bloom: Remember.
  Level 2 — Understand causes or consequences. ~45s. Bloom: Understand.
  Level 3 — Explain causation, compare perspectives. ~60s. Bloom: Apply.
  Level 4 — Analyse sources, evaluate evidence. ~90s. Bloom: Analyze.
  Level 5 — Evaluate competing interpretations, construct an argument. ~120s. Bloom: Evaluate.
""",
    "GEO": """
DIFFICULTY RUBRIC FOR GEOGRAPHY:
  Level 1 — Recall a definition, location, or term. ~30s. Bloom: Remember.
  Level 2 — Understand a geographical concept. ~45s. Bloom: Understand.
  Level 3 — Apply concepts to a case study. ~60s. Bloom: Apply.
  Level 4 — Analyse data, compare places/processes. ~90s. Bloom: Analyze.
  Level 5 — Evaluate solutions, synthesise across human/physical geography. ~120s. Bloom: Evaluate.
""",
    "GP": """
DIFFICULTY RUBRIC FOR GLOBAL PERSPECTIVES:
  Level 1 — Recall a term or definition. ~30s. Bloom: Remember.
  Level 2 — Understand a perspective or concept. ~45s. Bloom: Understand.
  Level 3 — Apply research skills to a global issue. ~60s. Bloom: Apply.
  Level 4 — Analyse multiple stakeholder perspectives. ~90s. Bloom: Analyze.
  Level 5 — Evaluate evidence, construct reasoned argument. ~120s. Bloom: Evaluate.
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
# Bloom's taxonomy bands by difficulty level
# ---------------------------------------------------------------------------

BLOOM_BY_DIFFICULTY: dict[int, list[str]] = {
    1: ["Remember"],
    2: ["Remember", "Understand"],
    3: ["Understand", "Apply"],
    4: ["Apply", "Analyze"],
    5: ["Evaluate", "Create"],
}

# ---------------------------------------------------------------------------
# DB query — fetch zero-question subtopics
# ---------------------------------------------------------------------------


async def fetch_gap_subtopics(
    db,
    subject_filter: list[str] | None,
    grade_filter: list[int] | None,
) -> list[dict[str, Any]]:
    """Return all active subtopics with zero active questions, with full hierarchy info."""

    where_clauses = [
        "st.is_active = true",
        "NOT EXISTS (SELECT 1 FROM question_bank qb WHERE qb.subtopic_id = st.id AND qb.is_active = true)",
    ]
    params: dict[str, Any] = {}

    if subject_filter:
        where_clauses.append("s.code = ANY(:subjects)")
        params["subjects"] = subject_filter

    if grade_filter:
        where_clauses.append("g.level = ANY(:grades)")
        params["grades"] = grade_filter

    where_sql = " AND ".join(where_clauses)

    result = await db.execute(
        sa_text(f"""
            SELECT
                st.id                   AS subtopic_id,
                st.name                 AS subtopic_name,
                st.learning_objective,
                st.description          AS subtopic_description,
                st.keywords,
                st.bloom_taxonomy_level AS subtopic_bloom,
                ct.id                   AS curriculum_topic_id,
                t.id                    AS topic_id,
                t.name                  AS topic_name,
                s.id                    AS subject_id,
                s.code                  AS subject_code,
                s.name                  AS subject_name,
                g.id                    AS grade_id,
                g.level                 AS grade_level,
                c.id                    AS curriculum_id,
                c.code                  AS curriculum_code,
                c.name                  AS curriculum_name
            FROM subtopics st
            JOIN curriculum_topics ct ON ct.id = st.curriculum_topic_id
            JOIN topics t             ON t.id  = ct.topic_id
            JOIN subjects s           ON s.id  = ct.subject_id
            JOIN grades g             ON g.id  = ct.grade_id
            JOIN curricula c          ON c.id  = ct.curriculum_id
            WHERE {where_sql}
            ORDER BY s.code, g.level, t.name, st.name
        """),
        params,
    )
    rows = result.fetchall()
    return [dict(r._mapping) for r in rows]


async def fetch_thin_subtopics(
    db,
    subject_filter: list[str] | None,
    grade_filter: list[int] | None,
) -> list[dict[str, Any]]:
    """Return subtopics that are missing questions at one or more difficulty levels.

    A subtopic is included if any difficulty level (1–5) has fewer than
    MIN_QUESTIONS_PER_DIFFICULTY active questions. The returned dicts include a
    'fill_plan' key: {difficulty_level: questions_needed} for only the thin levels.
    """
    where_clauses = ["st.is_active = true"]
    params: dict[str, Any] = {"min_per_level": MIN_QUESTIONS_PER_DIFFICULTY}

    if subject_filter:
        where_clauses.append("s.code = ANY(:subjects)")
        params["subjects"] = subject_filter

    if grade_filter:
        where_clauses.append("g.level = ANY(:grades)")
        params["grades"] = grade_filter

    where_sql = " AND ".join(where_clauses)

    # For each subtopic, count active questions per difficulty level.
    # The CROSS JOIN against generate_series produces one row per (subtopic, difficulty)
    # even when no question exists at that level — allowing us to spot missing levels.
    result = await db.execute(
        sa_text(f"""
            WITH difficulty_counts AS (
                SELECT
                    st.id           AS subtopic_id,
                    d.level         AS difficulty_level,
                    COUNT(qb.id)    AS question_count
                FROM subtopics st
                JOIN curriculum_topics ct ON ct.id = st.curriculum_topic_id
                JOIN topics t             ON t.id  = ct.topic_id
                JOIN subjects s           ON s.id  = ct.subject_id
                JOIN grades g             ON g.id  = ct.grade_id
                JOIN curricula c          ON c.id  = ct.curriculum_id
                CROSS JOIN (SELECT generate_series(1, 5) AS level) d
                LEFT JOIN question_bank qb
                    ON  qb.subtopic_id     = st.id
                    AND qb.difficulty_level = d.level
                    AND qb.is_active        = true
                WHERE {where_sql}
                GROUP BY st.id, d.level
            ),
            thin_subtopics AS (
                SELECT subtopic_id
                FROM difficulty_counts
                WHERE question_count < :min_per_level
                GROUP BY subtopic_id
            ),
            fill_plans AS (
                SELECT
                    dc.subtopic_id,
                    jsonb_object_agg(
                        dc.difficulty_level::text,
                        :min_per_level - dc.question_count
                    ) FILTER (WHERE dc.question_count < :min_per_level) AS fill_plan
                FROM difficulty_counts dc
                JOIN thin_subtopics ts ON ts.subtopic_id = dc.subtopic_id
                GROUP BY dc.subtopic_id
            )
            SELECT
                st.id                   AS subtopic_id,
                st.name                 AS subtopic_name,
                st.learning_objective,
                st.description          AS subtopic_description,
                st.keywords,
                st.bloom_taxonomy_level AS subtopic_bloom,
                ct.id                   AS curriculum_topic_id,
                t.id                    AS topic_id,
                t.name                  AS topic_name,
                s.id                    AS subject_id,
                s.code                  AS subject_code,
                s.name                  AS subject_name,
                g.id                    AS grade_id,
                g.level                 AS grade_level,
                c.id                    AS curriculum_id,
                c.code                  AS curriculum_code,
                c.name                  AS curriculum_name,
                fp.fill_plan
            FROM subtopics st
            JOIN curriculum_topics ct ON ct.id = st.curriculum_topic_id
            JOIN topics t             ON t.id  = ct.topic_id
            JOIN subjects s           ON s.id  = ct.subject_id
            JOIN grades g             ON g.id  = ct.grade_id
            JOIN curricula c          ON c.id  = ct.curriculum_id
            JOIN fill_plans fp        ON fp.subtopic_id = st.id
            WHERE {where_sql}
            ORDER BY s.code, g.level, t.name, st.name
        """),
        params,
    )
    rows = result.fetchall()
    result_dicts = []
    for r in rows:
        d = dict(r._mapping)
        # fill_plan comes back as a dict from jsonb; keys are strings — cast to int
        raw_plan = d.get("fill_plan") or {}
        d["fill_plan"] = {int(k): int(v) for k, v in raw_plan.items() if int(v) > 0}
        result_dicts.append(d)
    return result_dicts


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def build_prompt(
    subtopic: dict[str, Any],
    remaining: int | None = None,
    fill_plan: dict[int, int] | None = None,
) -> str:
    """Build the LLM prompt for a subtopic.

    fill_plan — used in --fill-gaps mode: {difficulty_level: questions_needed}.
    remaining  — used on retry passes to ask for only what's still missing.
    """
    subject_code = subtopic["subject_code"]
    guardrail = SUBJECT_GUARDRAILS.get(subject_code, DEFAULT_GUARDRAIL)
    rubric = DIFFICULTY_RUBRICS.get(subject_code, DEFAULT_RUBRIC)
    keywords = subtopic.get("keywords") or []
    keyword_hint = f"\nKey concepts to draw on: {', '.join(keywords)}" if keywords else ""
    description = subtopic.get("subtopic_description") or ""
    description_hint = f"\nSubtopic description: {description}" if description else ""

    if fill_plan:
        # Fill-gaps mode: only generate for the specific levels that are thin
        if remaining is not None:
            n_questions = remaining
            total_line = f"Generate EXACTLY {n_questions} MORE questions to complete the fill."
        else:
            n_questions = sum(fill_plan.values())
            total_line = f"Generate exactly {n_questions} questions to fill coverage gaps."

        diff_spec = "\n".join(
            f"  Difficulty {lvl}: {count} questions — Bloom: {' / '.join(BLOOM_BY_DIFFICULTY[lvl])}"
            for lvl, count in sorted(fill_plan.items())
        )
    else:
        # Zero-coverage mode: generate all 5 difficulty levels
        if remaining is not None:
            n_questions = remaining
            total_line = f"Generate EXACTLY {n_questions} MORE questions to complete the set."
        else:
            n_questions = QUESTIONS_PER_DIFFICULTY * len(DIFFICULTY_LEVELS)
            total_line = f"Generate exactly {n_questions} assessment questions in a single JSON object."

        diff_spec = "\n".join(
            f"  Difficulty {lvl}: {QUESTIONS_PER_DIFFICULTY} questions — Bloom: {' / '.join(BLOOM_BY_DIFFICULTY[lvl])}"
            for lvl in DIFFICULTY_LEVELS
        )

    return f"""You are an expert Cambridge curriculum assessment author writing questions for
international school students aged 11–18 in Southeast Asia. Use globally familiar
examples (avoid heavily US/UK-centric cultural references).

{total_line}

CURRICULUM CONTEXT:
- Programme:          {subtopic["curriculum_name"]} ({subtopic["curriculum_code"]})
- Subject:            {subtopic["subject_name"]} ({subject_code})
- Grade:              {subtopic["grade_level"]}
- Topic:              {subtopic["topic_name"]}
- Subtopic:           {subtopic["subtopic_name"]}
- Learning objective: {subtopic["learning_objective"]}{description_hint}{keyword_hint}

REQUIRED DIFFICULTY DISTRIBUTION:
{diff_spec}

{rubric}

QUESTION TYPES — mix of MCQ and True/False:
- "multiple_choice": provide exactly 4 options keyed A, B, C, D.
    • All 4 option VALUES must be unique (no duplicate option text).
    • All 4 options must be non-empty strings.
    • correct_answer must be one of: "A", "B", "C", or "D".
    • Distractors must be plausible misconceptions, not obviously wrong.
    • GOOD distractor: "The sum of the interior angles of a triangle is 200°" (common misconception)
    • BAD distractor: "The sum of the interior angles of a triangle is 42" (incoherent number)
    • For ENG: distractors must be plausible misreadings of the text, not factual errors.
- "true_false": question_text MUST begin with "True or False: " (exactly this prefix).
    • correct_answer must be "TRUE" or "FALSE" (uppercase).
    • Do NOT include an "options" field for true_false questions.
- Target 75% MCQ and 25% True/False across the full set. True/False carries a 50%
  guess rate, so it must never exceed a quarter of the questions, and every True/False
  statement must hinge on a real misconception — not a definition a student can
  recognise without understanding it.
- Vary question stem formats within the same difficulty (what / which / how / why /
  calculate / describe / identify) — do not repeat the same opener for 3 questions.

{guardrail}

SELF-CONTAINMENT — APPLIES TO EVERY SUBJECT. This is the single most important rule.
This is an ONLINE assessment. The student sees ONLY the words you write. There is no
diagram, no figure, no image, no accompanying worksheet, and no textbook page.
- NEVER write "the diagram below", "the figure shows", "refer to the graph",
  "look at the shape", "in the table above", "the following image", or any phrase
  that points at something you have not written out in full.
- If a question needs a shape, describe it completely in words:
    BAD:  "Find the area of the triangle shown below."
    GOOD: "A triangle has a base of 8 cm and a perpendicular height of 5 cm.
           Find its area."
- If a question needs data, write the data into the question text:
    BAD:  "Use the frequency table above to find the mode."
    GOOD: "A class recorded shoe sizes: 5, 6, 6, 7, 6, 8, 7. Find the mode."
- If a question cannot be made self-contained in plain text, DO NOT WRITE IT.
  Choose a different question that assesses the same objective instead.

ENG READING / LANGUAGE QUESTIONS — FOR ENGLISH LANGUAGE (ENG) ONLY:
If you are generating a question that requires a text to reference (e.g. inference,
language analysis, author's intent), you MUST include a SHORT invented passage excerpt
(2-4 sentences) DIRECTLY IN the question_text, then ask about it.
  Example:
    "Read this passage: 'The old house loomed against the grey sky, its windows
    like hollow eyes watching the road.' How does the writer use personification
    to create atmosphere?"
  Do NOT assume the student has read any external text. The question must be
  self-contained and answerable from the passage excerpt alone.

QUALITY REQUIREMENTS:
- Every question must DIRECTLY assess the learning objective stated above.
- Questions at the same difficulty level must test DIFFERENT aspects of the subtopic.
- PITCH TO THE GRADE, NOT BELOW IT. The commonest failure is writing questions a
  student two years younger could answer. A grade {subtopic["grade_level"]} question
  must require grade {subtopic["grade_level"]} reasoning.
    TOO EASY (rejected): "Estimate the sum of 29 + 31." — single-step, no reasoning.
    APPROPRIATE:         "A shop sells notebooks at $2.95 each. Estimate the cost of
                          21 notebooks, and state whether your estimate is above or
                          below the true cost."
- Difficulty 1 means "straightforward for a student who has learned this topic",
  NOT "trivial for anyone". Difficulty 5 must demand multi-step reasoning.
- A question whose answer is obvious from the wording of the question itself is
  invalid, whatever difficulty it claims.
- Explanations must state WHY the correct answer is right AND why each wrong option is wrong.
- Hints must scaffold thinking without revealing the answer. hint3 may strongly guide.
RENDERING CONTRACT — the student app renders question_text and every option as PLAIN
TEXT. There is no markdown parser, no LaTeX renderer, and no image support.
- USE Unicode directly. These render correctly and make questions readable:
    superscripts x² x³   fractions ½ ⅓ ¾   operators × ÷ ± ≈ ≠ ≤ ≥ √
    units °C ° cm² m³    Greek π α β θ     arrows → ↔   money $ £ €
- NEVER emit LaTeX ($x^2$, \\frac{{1}}{{2}}, \\times), markdown (**bold**, `code`, tables),
  or HTML (<sub>, <br>). These appear literally on screen as broken text.
- Write "x²" — NOT "x^2", NOT "x squared", NOT "$x^2$".
- Keep each option on a single line. No line breaks inside options.

SELF-VERIFICATION — Before including each question, verify:
  1. FACTUAL ACCURACY: Is the correct answer DEFINITELY correct? Re-solve if needed.
  2. DIFFICULTY: Does this question match the rubric for its labeled difficulty level?
     Would a student one grade below still find it demanding? If not, raise it.
  3. SUBTOPIC: Does this question test the stated learning objective, not a different skill?
  4. DISTRACTORS: Are wrong answers truly plausible? No obviously wrong options.
  5. SELF-CONTAINED: Does the question reference ANY diagram, figure, image, table or
     text you did not write out in full? If yes, rewrite or discard it.
  6. RENDERING: Does any field contain LaTeX, markdown, or HTML? Convert to Unicode.
  7. CONTENT DOMAIN: (ENG only) Does this test a language skill, not factual recall?

OUTPUT FORMAT — return ONLY valid JSON, no markdown fences, no trailing commas:
{{
  "questions": [
    {{
      "difficulty_level": 1,
      "question_type": "multiple_choice",
      "question_text": "Which of the following best describes ...?",
      "options": {{"A": "first option", "B": "second option", "C": "third option", "D": "fourth option"}},
      "correct_answer": "B",
      "bloom_taxonomy_level": "Remember",
      "estimated_time_seconds": 30,
      "learning_objectives": ["Recall the definition of ..."],
      "explanation": "B is correct because ... A is wrong because ... C is wrong because ... D is wrong because ...",
      "hints": {{"hint1": "Think about ...", "hint2": "Consider ...", "hint3": "The answer relates to ..."}}
    }},
    {{
      "difficulty_level": 2,
      "question_type": "true_false",
      "question_text": "True or False: [statement about {subtopic["subtopic_name"]}].",
      "correct_answer": "TRUE",
      "bloom_taxonomy_level": "Understand",
      "estimated_time_seconds": 45,
      "learning_objectives": ["Understand ..."],
      "explanation": "This is TRUE because ...",
      "hints": {{"hint1": "Consider ...", "hint2": "Think about ...", "hint3": "Focus on ..."}}
    }}
  ]
}}

Generate all {n_questions} questions now. Return ONLY the JSON object."""


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------

VALID_BLOOM = {"Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"}
VALID_QUESTION_TYPES = {"multiple_choice", "true_false"}

# ENG: flag questions testing non-language factual content
# Points at something the student cannot see. There is no image column on
# question_bank and no upload path, so any such reference is unanswerable.
_DANGLING_REFERENCE_RE = re.compile(
    r"\b(?:"
    r"(?:the|this|following|above|below)\s+(?:diagram|figure|graph|chart|image|picture|"
    r"illustration|drawing|table|grid|net|shape\s+shown)"
    r"|(?:diagram|figure|graph|chart|image|picture|table)\s+(?:above|below|shown)"
    r"|refer\s+to\s+the\s+\w+"
    r"|shown\s+(?:above|below|in\s+the)"
    r"|as\s+shown"
    r"|see\s+(?:the\s+)?(?:diagram|figure|graph|chart|image|table)"
    r")\b",
    re.IGNORECASE,
)

# Renders literally on screen: question_text goes through JSX text interpolation with
# no markdown or maths renderer. Unicode is safe; these markups are not.
_UNRENDERABLE_RE = re.compile(
    r"(?:\$[^$\n]{1,80}\$"  # $...$ LaTeX
    r"|\\(?:frac|sqrt|times|div|leq|geq|neq|approx|pi|alpha|beta|theta|circ|degree)\b"
    r"|\\\(|\\\)|\\\[|\\\]"  # \( \) \[ \] LaTeX delimiters
    r"|\*\*[^*\n]+\*\*"  # **bold**
    r"|<(?:sub|sup|br|b|i|em|strong|p|div)\b[^>]*>"  # HTML tags
    r"|`[^`\n]+`"  # `code`
    r"|\b[a-zA-Z]\^\d"  # x^2 ASCII exponent
    r")",
)

_ENG_HISTORY_RE = re.compile(
    r"\b(world war|french revolution|treaty of versailles|league of nations|"
    r"marshall plan|magna carta|enlightenment|cold war|nazi|allied powers|"
    r"yalta conference|renaissance|roman empire|fall of rome|black death)\b",
    re.IGNORECASE,
)
_ENG_SCIENCE_RE = re.compile(
    r"\b(photosynthesis|mitosis|meiosis|periodic table|newton.s law|"
    r"chemical equation|atomic number|dna strand|rna strand|ecosystem)\b",
    re.IGNORECASE,
)

# True/False questions must begin with this prefix (case-insensitive match)
_TF_PREFIX_RE = re.compile(r"^true or false\s*:", re.IGNORECASE)


def validate_question(q: dict[str, Any], subject_code: str) -> list[str]:
    """Return a list of validation errors. Empty list = valid."""
    errors: list[str] = []

    # ── Required fields ──────────────────────────────────────────────────────
    required = (
        "question_text",
        "question_type",
        "correct_answer",
        "bloom_taxonomy_level",
        "estimated_time_seconds",
        "learning_objectives",
        "explanation",
        "hints",
        "difficulty_level",
    )
    missing = [f for f in required if f not in q]
    if missing:
        errors.append(f"missing fields: {missing}")
        return errors  # can't continue without core fields

    # ── Question type ────────────────────────────────────────────────────────
    q_type = q["question_type"]
    if q_type not in VALID_QUESTION_TYPES:
        errors.append(f"invalid question_type: {q_type!r} — must be one of {sorted(VALID_QUESTION_TYPES)}")
        return errors

    # ── Difficulty level (safe cast — LLMs sometimes return "1" as string) ──
    try:
        difficulty = int(float(q["difficulty_level"]))
        if difficulty not in range(1, 6):
            errors.append(f"difficulty_level {difficulty} out of range 1–5")
    except (TypeError, ValueError):
        errors.append(f"difficulty_level is not numeric: {q['difficulty_level']!r}")

    # ── Question text ────────────────────────────────────────────────────────
    q_text = q.get("question_text", "")
    if not q_text or not q_text.strip():
        errors.append("question_text is empty")

    # Deterministic guards for the two failure modes an LLM reviewer misses most often.
    # Checked across the stem and every option, since a dangling reference or a stray
    # LaTeX fragment in an option is just as unanswerable as one in the stem.
    option_values = list(q["options"].values()) if isinstance(q.get("options"), dict) else []
    for field_name, text in [("question_text", q_text), *[(f"option {i}", v) for i, v in enumerate(option_values)]]:
        if not isinstance(text, str):
            continue
        if match := _DANGLING_REFERENCE_RE.search(text):
            errors.append(
                f"{field_name} refers to {match.group(0)!r} but this is an online "
                f"assessment with no images — the question must be self-contained"
            )
        if match := _UNRENDERABLE_RE.search(text):
            errors.append(
                f"{field_name} contains {match.group(0)!r}, which renders literally "
                f"as broken text — use Unicode (x², ½, ×, ≤) instead"
            )

    # ── MCQ-specific validation ───────────────────────────────────────────────
    if q_type == "multiple_choice":
        options = q.get("options")
        if not isinstance(options, dict):
            errors.append("options must be a dict for multiple_choice questions")
        elif set(options.keys()) != {"A", "B", "C", "D"}:
            errors.append(f"options must have exactly keys A, B, C, D — got {sorted(options.keys())}")
        else:
            # All option values must be non-empty
            empty_keys = [k for k, v in options.items() if not v or not str(v).strip()]
            if empty_keys:
                errors.append(f"options {empty_keys} have empty values")

            # All option values must be unique
            values = list(options.values())
            if len(set(str(v).strip().lower() for v in values)) < len(values):
                errors.append("MCQ options contain duplicate values — all 4 options must be distinct")

            # correct_answer must be one of the option keys
            correct = q.get("correct_answer")
            if correct not in options:
                errors.append(f"correct_answer {correct!r} is not one of the option keys (A/B/C/D)")

    # ── True/False-specific validation ───────────────────────────────────────
    if q_type == "true_false":
        answer = str(q.get("correct_answer", "")).upper().strip()
        if answer not in ("TRUE", "FALSE"):
            errors.append(f"true_false correct_answer must be 'TRUE' or 'FALSE', got {q.get('correct_answer')!r}")
        if not _TF_PREFIX_RE.match(q_text.strip()):
            errors.append(f"true_false question_text must begin with 'True or False: ' — got: {q_text[:60]!r}")
        if "options" in q:
            errors.append("true_false questions must NOT include an 'options' field")

    # ── Bloom's taxonomy ─────────────────────────────────────────────────────
    bloom = q.get("bloom_taxonomy_level", "")
    if bloom not in VALID_BLOOM:
        errors.append(f"invalid bloom_taxonomy_level: {bloom!r} — must be one of {sorted(VALID_BLOOM)}")

    # ── Hints ────────────────────────────────────────────────────────────────
    hints = q.get("hints", {})
    if not isinstance(hints, dict):
        errors.append("hints must be a dict")
    elif not all(f"hint{i}" in hints for i in (1, 2, 3)):
        errors.append("hints must contain hint1, hint2, hint3")
    else:
        empty_hints = [k for k in ("hint1", "hint2", "hint3") if not hints.get(k, "").strip()]
        if empty_hints:
            errors.append(f"hints {empty_hints} are empty")

    # ── Learning objectives ───────────────────────────────────────────────────
    objectives = q.get("learning_objectives", [])
    if not isinstance(objectives, list) or not objectives:
        errors.append("learning_objectives must be a non-empty list")

    # ── ENG content-domain filter ─────────────────────────────────────────────
    if subject_code == "ENG" and q_text:
        if _ENG_HISTORY_RE.search(q_text):
            errors.append("ENG question contains history keywords — tests factual recall, not a language skill")
        if _ENG_SCIENCE_RE.search(q_text):
            errors.append("ENG question contains science keywords — tests factual recall, not a language skill")

    return errors


# ---------------------------------------------------------------------------
# Canonical form and dedup
# ---------------------------------------------------------------------------

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
    text = question_text.lower()
    # Strip the "True or False:" prefix for dedup purposes
    text = _TF_PREFIX_RE.sub("", text).strip()
    text = re.sub(r"[^\w\s]", " ", text)
    words = [w for w in text.split() if w not in _STOP_WORDS]
    return " ".join(words)


# ---------------------------------------------------------------------------
# LLM call with retry and exponential backoff
# ---------------------------------------------------------------------------


async def generate_for_subtopic(
    subtopic: dict[str, Any],
    semaphore: asyncio.Semaphore,
    dry_run: bool,
    fill_plan: dict[int, int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """
    One LLM call per subtopic — all required difficulty levels in a single batch.

    fill_plan: {difficulty_level: questions_needed} — used in --fill-gaps mode.
               When None, generates QUESTIONS_PER_DIFFICULTY per all 5 levels.

    Retries with backoff if the response is malformed or insufficient.
    Returns (accepted_questions, stats_fragment).
    """
    stats: dict[str, int] = {
        "llm_calls": 0,
        "validation_failures": 0,
        "duplicates_detected": 0,
        "questions_accepted": 0,
    }

    if dry_run:
        log.info(
            "dry_run_subtopic",
            subject=subtopic["subject_code"],
            grade=subtopic["grade_level"],
            subtopic=subtopic["subtopic_name"],
            fill_plan=fill_plan,
        )
        return [], stats

    subject_code = subtopic["subject_code"]
    seen_canonicals: set[str] = set()
    accepted: list[dict[str, Any]] = []

    if fill_plan:
        expected = sum(fill_plan.values())
        # Track per-level counts so we can filter questions for unlisted levels
        target_levels: set[int] = set(fill_plan.keys())
    else:
        expected = QUESTIONS_PER_DIFFICULTY * len(DIFFICULTY_LEVELS)
        target_levels = set(DIFFICULTY_LEVELS)

    async with semaphore:
        for attempt in range(1, MAX_RETRIES + 1):
            remaining = expected - len(accepted)
            prompt = build_prompt(
                subtopic,
                remaining=remaining if attempt > 1 else None,
                fill_plan=fill_plan,
            )

            stats["llm_calls"] += 1
            log.info(
                "llm_call",
                subject=subject_code,
                grade=subtopic["grade_level"],
                subtopic=subtopic["subtopic_name"],
                attempt=attempt,
                accepted_so_far=len(accepted),
                remaining=remaining,
            )

            response_text: str | None = None
            try:
                response_text = await complete(
                    task="question_generation",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an expert Cambridge curriculum assessment author. "
                                "Output valid JSON only. "
                                "No markdown fences. No text outside the JSON object. "
                                "No HTML tags, no LaTeX, no markdown inside string values. "
                                "DO use Unicode maths characters (x² ½ × ÷ ≤ √ ° π) — the "
                                "student app renders them correctly and they make questions "
                                "readable."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.4,
                    # 15 fully-specified questions — stem, 4 options, explanation covering
                    # every distractor, and 3 hints — runs well past 8000 tokens on a
                    # capable model. Truncation lands mid-string, so the whole batch fails
                    # JSON parsing and the subtopic yields nothing after three attempts.
                    # Measured range on a Sonnet-class model: 11.7k-15.0k tokens, so the
                    # headroom here is deliberate — a cap set near the observed maximum
                    # fails only on the richest subtopics, which are the ones worth having.
                    max_tokens=20000,
                )
            except Exception as exc:
                log.error(
                    "llm_call_failed",
                    attempt=attempt,
                    error=str(exc),
                    subtopic=subtopic["subtopic_name"],
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2**attempt)  # 2s, 4s, 8s backoff
                continue

            # Strip markdown fences if the model added them despite instructions
            response_text = response_text.strip()
            if response_text.startswith("```"):
                response_text = re.sub(r"^```(?:json)?\s*", "", response_text)
                response_text = re.sub(r"\s*```\s*$", "", response_text.strip())

            try:
                batch = json.loads(response_text)
            except json.JSONDecodeError as exc:
                log.error(
                    "json_parse_failed",
                    attempt=attempt,
                    error=str(exc),
                    preview=response_text[:200],
                    subtopic=subtopic["subtopic_name"],
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2**attempt)
                continue

            raw_questions = batch.get("questions", [])
            if not isinstance(raw_questions, list) or not raw_questions:
                log.warning(
                    "empty_or_invalid_questions_array",
                    subtopic=subtopic["subtopic_name"],
                    attempt=attempt,
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2**attempt)
                continue

            # Clean → validate → deduplicate
            for q in raw_questions:
                if not isinstance(q, dict):
                    stats["validation_failures"] += 1
                    continue

                q = clean_question(q)

                errors = validate_question(q, subject_code)
                if errors:
                    stats["validation_failures"] += 1
                    log.warning(
                        "question_validation_failed",
                        subtopic=subtopic["subtopic_name"],
                        errors=errors,
                        preview=str(q.get("question_text", ""))[:80],
                    )
                    continue

                # Normalise difficulty_level to int before level check
                try:
                    q["difficulty_level"] = int(float(q["difficulty_level"]))
                except (TypeError, ValueError):
                    stats["validation_failures"] += 1
                    continue

                # In fill-gaps mode, skip questions at levels we did not request
                if q["difficulty_level"] not in target_levels:
                    log.debug(
                        "question_skipped_unrequested_level",
                        difficulty=q["difficulty_level"],
                        target_levels=sorted(target_levels),
                        subtopic=subtopic["subtopic_name"],
                    )
                    continue

                canon = make_canonical_form(q["question_text"])
                if canon in seen_canonicals:
                    stats["duplicates_detected"] += 1
                    continue
                seen_canonicals.add(canon)

                # Normalise true_false fields
                if q["question_type"] == "true_false":
                    q["correct_answer"] = q["correct_answer"].upper().strip()
                    q.pop("options", None)

                accepted.append(q)
                stats["questions_accepted"] += 1

            if len(accepted) >= expected:  # noqa: SIM102
                break

            log.warning(
                "insufficient_questions_retrying",
                accepted=len(accepted),
                expected=expected,
                attempt=attempt,
                subtopic=subtopic["subtopic_name"],
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2**attempt)

    return accepted, stats


# ---------------------------------------------------------------------------
# Build output record per question
# ---------------------------------------------------------------------------


def build_output_record(q: dict[str, Any], subtopic: dict[str, Any]) -> dict[str, Any]:
    """
    Build a question record compatible with import_questions.py.

    - subtopic_id UUID → preresolved import on same DB (dev/staging)
    - name hierarchy   → reresolve import on different DB (prod)
    """
    canon = make_canonical_form(q["question_text"])
    sig = {
        "type": q.get("question_type"),
        "difficulty": q.get("difficulty_level"),
        "concept_hash": hashlib.md5(canon.encode()).hexdigest()[:12],
        "bloom_level": q.get("bloom_taxonomy_level"),
        "has_options": isinstance(q.get("options"), dict),
    }

    return {
        # ── For preresolved import (same DB) ──────────────────────────────
        "subtopic_id": str(subtopic["subtopic_id"]),
        # ── For reresolve import (prod / different DB) ────────────────────
        "grade_level": subtopic["grade_level"],
        "subject_name": subtopic["subject_name"],
        "topic_name": subtopic["topic_name"],
        "subtopic_name": subtopic["subtopic_name"],
        # ── Question content ──────────────────────────────────────────────
        "question_text": q["question_text"],
        "question_type": q["question_type"],
        "options": q.get("options"),  # None for true_false
        "correct_answer": q["correct_answer"],
        "difficulty_level": q["difficulty_level"],
        "bloom_taxonomy_level": q.get("bloom_taxonomy_level"),
        "estimated_time_seconds": q.get("estimated_time_seconds"),
        "learning_objectives": q.get("learning_objectives", []),
        "explanation": q.get("explanation", ""),
        "hints": q.get("hints", {}),
        "canonical_form": canon,
        "problem_signature": sig,
        "is_active": True,
        "source": "bank",
        # ── Audit metadata ────────────────────────────────────────────────
        "_generated_by": "generate_gap_questions.py",
        "_curriculum_id": str(subtopic["curriculum_id"]),
        "_curriculum_code": subtopic["curriculum_code"],
    }


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

CHECKPOINT_DIR = Path("checkpoints")


def save_checkpoint(
    completed_subtopic_ids: list[str],
    questions: list[dict[str, Any]],
    stats: dict[str, Any],
    checkpoint_path: Path | None = None,
) -> Path:
    CHECKPOINT_DIR.mkdir(exist_ok=True)
    if checkpoint_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        checkpoint_path = CHECKPOINT_DIR / f"gap_questions_checkpoint_{ts}.json"

    data = {
        "completed_subtopic_ids": completed_subtopic_ids,
        "questions": questions,
        "stats": stats,
        "saved_at": datetime.now().isoformat(),
    }
    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Keep only 5 most recent checkpoints
    all_checkpoints = sorted(CHECKPOINT_DIR.glob("gap_questions_checkpoint_*.json"))
    for old in all_checkpoints[:-5]:
        old.unlink()

    log.info("checkpoint_saved", path=str(checkpoint_path), questions=len(questions))
    return checkpoint_path


def load_checkpoint(checkpoint_path: str) -> tuple[list[str], list[dict], dict]:
    with open(checkpoint_path, encoding="utf-8") as f:
        data = json.load(f)
    completed = data.get("completed_subtopic_ids", [])
    questions = data.get("questions", [])
    stats = data.get("stats", {})
    log.info(
        "checkpoint_loaded",
        path=checkpoint_path,
        completed_subtopics=len(completed),
        questions=len(questions),
    )
    return completed, questions, stats


# ---------------------------------------------------------------------------
# Main orchestration — concurrent processing via semaphore
# ---------------------------------------------------------------------------


async def run(
    subject_filter: list[str] | None,
    grade_filter: list[int] | None,
    dry_run: bool,
    fill_gaps: bool,
    resume_checkpoint: str | None,
    output_file: str | None,
    concurrency: int,
    limit: int | None = None,
) -> int:
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with async_session() as db:
            if fill_gaps:
                log.info(
                    "fetching_thin_subtopics",
                    subject_filter=subject_filter,
                    grade_filter=grade_filter,
                    min_per_level=MIN_QUESTIONS_PER_DIFFICULTY,
                )
                gap_subtopics = await fetch_thin_subtopics(db, subject_filter, grade_filter)
            else:
                log.info(
                    "fetching_zero_coverage_subtopics",
                    subject_filter=subject_filter,
                    grade_filter=grade_filter,
                )
                gap_subtopics = await fetch_gap_subtopics(db, subject_filter, grade_filter)

        if not gap_subtopics:
            log.info("no_gap_subtopics_found — nothing to generate")
            return 0

        mode_label = "fill-gaps (thin coverage)" if fill_gaps else "zero-coverage"
        log.info("gap_subtopics_found", count=len(gap_subtopics), mode=mode_label)

        # Trial runs: generate for a handful of subtopics so the output can be read and
        # the prompt tuned before committing spend on the full scope. Truncating after
        # the query keeps the selection identical to what a full run would process.
        if limit is not None and limit < len(gap_subtopics):
            log.info("limiting_scope_for_trial", requested=limit, available=len(gap_subtopics))
            gap_subtopics = gap_subtopics[:limit]

        # Restore from checkpoint if requested
        completed_ids: list[str] = []
        all_questions: list[dict[str, Any]] = []
        cumulative_stats: dict[str, Any] = {
            "llm_calls": 0,
            "validation_failures": 0,
            "duplicates_detected": 0,
            "questions_accepted": 0,
            "subtopics_attempted": 0,
            "subtopics_completed": 0,
            "subtopics_empty": 0,
        }

        checkpoint_path: Path | None = None
        if resume_checkpoint:
            completed_ids, all_questions, loaded_stats = load_checkpoint(resume_checkpoint)
            cumulative_stats.update(loaded_stats)
            checkpoint_path = Path(resume_checkpoint)

        already_done = set(completed_ids)
        to_process = [s for s in gap_subtopics if str(s["subtopic_id"]) not in already_done]

        log.info(
            "processing_plan",
            total_gap=len(gap_subtopics),
            already_completed=len(already_done),
            remaining=len(to_process),
            concurrency=concurrency,
        )

        if dry_run:
            total_estimated = 0
            for subtopic in to_process:
                fp = subtopic.get("fill_plan") if fill_gaps else None
                q_count = sum(fp.values()) if fp else QUESTIONS_PER_DIFFICULTY * len(DIFFICULTY_LEVELS)
                total_estimated += q_count
                log.info(
                    "dry_run_subtopic",
                    subject=subtopic["subject_code"],
                    grade=subtopic["grade_level"],
                    subtopic=subtopic["subtopic_name"],
                    fill_plan=fp,
                    questions_needed=q_count,
                )
            log.info(
                "dry_run_complete",
                subtopics_that_would_be_processed=len(to_process),
                estimated_questions=total_estimated,
            )
            return 0

        start_time = time.time()
        semaphore = asyncio.Semaphore(concurrency)

        # Thread-safe accumulators for concurrent tasks
        lock = asyncio.Lock()
        completed_count = 0

        async def process_one(subtopic: dict[str, Any]) -> None:
            nonlocal completed_count
            fp = subtopic.get("fill_plan") if fill_gaps else None

            questions, stats_fragment = await generate_for_subtopic(subtopic, semaphore, dry_run=False, fill_plan=fp)

            async with lock:
                for key in ("llm_calls", "validation_failures", "duplicates_detected", "questions_accepted"):
                    cumulative_stats[key] = cumulative_stats.get(key, 0) + stats_fragment.get(key, 0)
                cumulative_stats["subtopics_attempted"] += 1

                if questions:
                    records = [build_output_record(q, subtopic) for q in questions]
                    all_questions.extend(records)
                    completed_ids.append(str(subtopic["subtopic_id"]))
                    cumulative_stats["subtopics_completed"] += 1
                    completed_count += 1
                    log.info(
                        "subtopic_done",
                        subject=subtopic["subject_code"],
                        grade=subtopic["grade_level"],
                        subtopic=subtopic["subtopic_name"],
                        questions_generated=len(questions),
                        total_so_far=len(all_questions),
                        progress=f"{completed_count}/{len(to_process)}",
                    )
                else:
                    cumulative_stats["subtopics_empty"] += 1
                    log.warning(
                        "subtopic_generated_nothing",
                        subject=subtopic["subject_code"],
                        grade=subtopic["grade_level"],
                        subtopic=subtopic["subtopic_name"],
                    )

                # Checkpoint periodically
                if completed_count % CHECKPOINT_EVERY == 0:
                    save_checkpoint(completed_ids, all_questions, cumulative_stats, checkpoint_path)

        await asyncio.gather(*[process_one(s) for s in to_process])

        cumulative_stats["total_time_seconds"] = round(time.time() - start_time, 1)

        if not all_questions:
            log.warning("no_questions_generated — output file not written")
            return 1

        # Final checkpoint before writing output
        save_checkpoint(completed_ids, all_questions, cumulative_stats, checkpoint_path)

        # Write output JSON
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        subject_tag = "_".join(sorted(subject_filter)) if subject_filter else "all"
        grade_tag = "_".join(str(g) for g in sorted(grade_filter)) if grade_filter else "all"
        mode_tag = "fillgaps" if fill_gaps else "zerocoverage"
        default_name = f"gap_questions_{mode_tag}_{subject_tag}_grade{grade_tag}_{ts}.json"
        out_path = Path(output_file) if output_file else Path(default_name)

        output_data = {
            "generated_at": datetime.now().isoformat(),
            "generated_by": "generate_gap_questions.py",
            "subject_filter": subject_filter,
            "grade_filter": grade_filter,
            "total_questions": len(all_questions),
            "subtopics_completed": cumulative_stats["subtopics_completed"],
            "subtopics_empty": cumulative_stats["subtopics_empty"],
            "import_instructions": {
                "same_db_dev_staging": (
                    f"python -m scripts.import_questions --file {out_path.name} --strategy preresolved"
                ),
                "different_db_prod": (
                    f"python -m scripts.import_questions --file {out_path.name} --strategy reresolve"
                ),
            },
            "statistics": cumulative_stats,
            "questions": all_questions,
        }

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        log.info(
            "output_written",
            path=str(out_path),
            total_questions=len(all_questions),
            subtopics_completed=cumulative_stats["subtopics_completed"],
        )
        _print_summary(cumulative_stats, str(out_path))
        return 0

    except Exception as exc:
        log.error("script_failed", error=str(exc), exc_info=True)
        return 1
    finally:
        await engine.dispose()


def _print_summary(stats: dict[str, Any], output_path: str) -> None:
    print("\n" + "=" * 65)
    print("QUESTION GENERATION COMPLETE")
    print("=" * 65)
    print(f"Questions generated:      {stats.get('questions_accepted', 0)}")
    print(f"Subtopics completed:      {stats.get('subtopics_completed', 0)}")
    print(f"Subtopics with no output: {stats.get('subtopics_empty', 0)}")
    print(f"Validation failures:      {stats.get('validation_failures', 0)}")
    print(f"Duplicates dropped:       {stats.get('duplicates_detected', 0)}")
    print(f"LLM calls made:           {stats.get('llm_calls', 0)}")
    elapsed = stats.get("total_time_seconds", 0)
    print(f"Total time:               {elapsed / 60:.1f} minutes")
    print(f"\nOutput file: {output_path}")
    print("\nTo import on the SAME database (dev/staging):")
    print("  python -m scripts.import_questions \\")
    print(f"    --file {Path(output_path).name} --strategy preresolved")
    print("\nTo import on a DIFFERENT database (prod):")
    print("  python -m scripts.import_questions \\")
    print(f"    --file {Path(output_path).name} --strategy reresolve")
    print("=" * 65)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def main(args: argparse.Namespace) -> int:
    subject_filter = [s.strip().upper() for s in args.subject.split(",")] if args.subject else None
    grade_filter = [int(g.strip()) for g in args.grade.split(",")] if args.grade else None

    return await run(
        subject_filter=subject_filter,
        grade_filter=grade_filter,
        dry_run=args.dry_run,
        fill_gaps=args.fill_gaps,
        resume_checkpoint=args.resume,
        output_file=args.output,
        concurrency=args.concurrency,
        limit=args.limit,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Generate assessment questions for subtopics with missing question bank coverage.\n"
            "\n"
            "TWO MODES:\n"
            "  Default      — zero-coverage: only subtopics with NO active questions at all.\n"
            "                 Use this first pass — highest impact, fastest to review.\n"
            "  --fill-gaps  — thin-coverage: subtopics that have some questions but are\n"
            "                 missing coverage at one or more difficulty levels\n"
            f"                 (fewer than {MIN_QUESTIONS_PER_DIFFICULTY} questions per level).\n"
            "                 Run this after zero-coverage questions are reviewed and imported.\n"
            "\n"
            "OUTPUT: A JSON file you review before importing. Import commands are printed at the end.\n"
            "  Same DB (dev/staging): python -m scripts.import_questions --file <file> --strategy preresolved\n"
            "  Production DB:         python -m scripts.import_questions --file <file> --strategy reresolve\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--subject",
        default=None,
        metavar="CODE[,CODE...]",
        help=(
            "Filter by subject code(s). Comma-separated. Omit to process all subjects.\n"
            "\n"
            "Subject codes in the Kaihle database:\n"
            "  ENG   — English Language       (Cambridge Primary + Lower Secondary + IGCSE + AS/A Level)\n"
            "  MATH  — Mathematics            (all programmes)\n"
            "  SCI   — Integrated Science     (Cambridge Lower Secondary ONLY, Grades 6–8)\n"
            "  BIO   — Biology                (IGCSE + AS/A Level, Grades 9–12)\n"
            "  CHEM  — Chemistry              (IGCSE + AS/A Level, Grades 9–12)\n"
            "  PHY   — Physics                (IGCSE + AS/A Level, Grades 9–12)\n"
            "  ENGL  — English Literature     (IGCSE, Grades 9–10)\n"
            "  HIST  — History                (if seeded)\n"
            "  GEO   — Geography              (if seeded)\n"
            "  GP    — Global Perspectives    (if seeded)\n"
            "\n"
            "To see the exact codes in your DB:\n"
            "  docker compose exec db psql -U kaihle -d kaihle -c 'SELECT code, name FROM subjects ORDER BY code;'\n"
            "\n"
            "Examples: --subject ENGL   --subject BIO,CHEM,PHY   --subject ENG,MATH"
        ),
    )
    parser.add_argument(
        "--grade",
        default=None,
        metavar="LEVEL[,LEVEL...]",
        help=(
            "Filter by grade level(s). Comma-separated integers. Omit to process all grades.\n"
            "\n"
            "Grade levels in the Kaihle database:\n"
            "  5        — Cambridge Primary Grade 5\n"
            "  6, 7, 8  — Cambridge Lower Secondary\n"
            "  9, 10    — Cambridge IGCSE\n"
            "  11, 12   — Cambridge AS & A Level\n"
            "\n"
            "To see grades in your DB:\n"
            "  docker compose exec db psql -U kaihle -d kaihle -c 'SELECT level, name FROM grades ORDER BY level;'\n"
            "\n"
            "Examples: --grade 9,10   --grade 6,7,8   --grade 11,12"
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Process at most N subtopics. For trial runs: read the output and tune the\n"
            "prompt before committing spend on the full scope."
        ),
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        metavar="N",
        help=(
            f"How many subtopics to generate questions for simultaneously (default: {DEFAULT_CONCURRENCY}).\n"
            "\n"
            "Each subtopic is one LLM API call. Running several in parallel cuts total wall-clock\n"
            "time significantly when processing many subtopics (e.g. all of BIO = ~120 subtopics).\n"
            "\n"
            "Guidelines by provider:\n"
            "  Cloud APIs (Gemini, GPT-4, Claude via OpenRouter):\n"
            "    Start at 3–5. If you see rate-limit errors, drop to 2.\n"
            "  Self-hosted RunPod vLLM:\n"
            "    A single A100 GPU handles ~2–4 concurrent requests comfortably.\n"
            "    Use 2–3 to keep the queue short. Going higher may slow each request down.\n"
            "\n"
            "Examples: --concurrency 2   --concurrency 5"
        ),
    )
    parser.add_argument(
        "--fill-gaps",
        action="store_true",
        dest="fill_gaps",
        help=(
            f"Target subtopics that have some questions but fewer than {MIN_QUESTIONS_PER_DIFFICULTY} "
            "per difficulty level.\n"
            "Only generates for the specific difficulty levels that are under the minimum —\n"
            "existing questions are untouched.\n"
            "\n"
            "Run this AFTER zero-coverage questions are reviewed and imported."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Print which subtopics would be processed and how many questions would be generated,\n"
            "without making any LLM calls or writing any files. Use this to check the scope\n"
            "before committing to a long generation run."
        ),
    )
    parser.add_argument(
        "--resume",
        default=None,
        metavar="CHECKPOINT_FILE",
        help=(
            "Resume a previously interrupted run from a checkpoint file.\n"
            "Checkpoints are saved automatically every 10 completed subtopics in the\n"
            "checkpoints/ directory. Pass the path to the .json checkpoint file.\n"
            "\n"
            "Example: --resume checkpoints/gap_questions_checkpoint_20260516_120000.json"
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="OUTPUT_FILE",
        help=(
            "Override the output JSON filename.\n"
            "Default: auto-generated based on mode, subject, grade, and timestamp,\n"
            "e.g. gap_questions_zerocoverage_ENGL_gradeall_20260516_143000.json\n"
            "\n"
            "Example: --output engl_batch1.json"
        ),
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args)))
