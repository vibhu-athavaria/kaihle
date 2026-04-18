"""Concept guide service.

Generates personalised explanations for subtopics the student is struggling with.
Uses the student's learning profile (modality, interests) to tailor the output.

The LLM returns an explanation paragraph followed by a JSON MCQ check question.
This service parses them apart so the frontend can render the MCQ options.

All LLM calls route through app.ai.providers.router (Rule 4 compliance).
"""

import json
from pathlib import Path
from uuid import UUID

import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import router as llm_router
from app.models.curriculum import Subtopic
from app.models.onboarding import StudentLearningProfile
from app.models.user import User

logger = structlog.get_logger()

_PROMPTS_DIR = Path(__file__).parent.parent / "ai" / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), autoescape=False)

_VALID_MCQ_ANSWERS = {"A", "B", "C", "D"}


def _extract_json_block(text: str) -> tuple[int, int] | None:
    """Return (start, end) indices of the first top-level {...} block, or None."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1
    return None


def _get_dominant_modality(modality_scores: dict[str, float]) -> str:
    """Return the label for the highest-scoring modality.

    Falls back to 'visual' if the profile is empty or has no scores.
    """
    if not modality_scores:
        return "visual"
    label_map = {
        "visual": "visual",
        "auditory": "auditory",
        "reading_writing": "reading/writing",
        "kinesthetic": "kinesthetic",
    }
    # Sort by score descending, then by key ascending for deterministic tie-breaking
    sorted_modalities = sorted(modality_scores.keys(), key=lambda k: (-modality_scores.get(k, 0.0), k))
    best = sorted_modalities[0]
    return label_map.get(best, best.replace("_", " "))


def _parse_mcq(raw: str) -> tuple[str, dict[str, object] | None]:
    """Split the LLM response into (explanation_text, mcq_dict | None).

    The LLM is instructed to append a JSON MCQ block after the explanation.
    If parsing fails for any reason we return the full text as explanation and
    None for the MCQ — the frontend degrades gracefully to explanation-only.
    """
    span = _extract_json_block(raw)
    if not span:
        return raw.strip(), None

    json_str = raw[span[0] : span[1]]
    explanation = raw[: span[0]].strip()
    try:
        mcq = json.loads(json_str)
        # Validate required keys and options length
        if not all(k in mcq for k in ("question", "options", "correct")):
            return raw.strip(), None
        if not isinstance(mcq["options"], list) or len(mcq["options"]) != 4:
            return raw.strip(), None
        return explanation, mcq
    except json.JSONDecodeError:
        return raw.strip(), None


async def generate_concept_explanation(
    *,
    student: User,
    subtopic_id: UUID,
    question: str | None,
    db: AsyncSession,
) -> dict[str, object]:
    """Generate a personalised concept explanation for the student.

    Args:
        student: The requesting student User object.
        subtopic_id: UUID of the subtopic to explain.
        question: Optional specific question from the student.
        db: Async database session.

    Returns:
        dict with keys:
          - explanation (str): the explanation text
          - subtopic_name (str)
          - check_question (dict | None): {"question", "options", "correct"} or None

    Raises:
        ValueError: If subtopic not found.
    """
    # Fetch subtopic
    subtopic_result = await db.execute(select(Subtopic).where(Subtopic.id == subtopic_id, Subtopic.is_active.is_(True)))
    subtopic = subtopic_result.scalar_one_or_none()
    if subtopic is None:
        raise ValueError(f"Subtopic {subtopic_id} not found")

    # Fetch learning profile (optional — graceful fallback if not completed)
    profile_result = await db.execute(
        select(StudentLearningProfile).where(
            StudentLearningProfile.student_id == student.id,
            StudentLearningProfile.completed_at.is_not(None),
        )
    )
    profile = profile_result.scalar_one_or_none()

    modality_scores: dict[str, float] = profile.modality_scores if profile else {}
    work_style: dict[str, object] = profile.work_style if profile else {}
    interests: list[str] = (profile.interests or []) if profile else []

    dominant_modality = _get_dominant_modality(modality_scores)

    # Render prompt
    template = _jinja_env.get_template("concept_guide.jinja2")
    prompt = template.render(
        subtopic_name=subtopic.name,
        description=subtopic.description,
        learning_objective=subtopic.learning_objective,
        keywords=subtopic.keywords,
        dominant_modality=dominant_modality,
        interests=interests[:2],  # Top 2 interests only
        work_style=work_style,
        question=question,
    )

    logger.info(
        "concept_guide_generation_started",
        student_id=str(student.id),
        subtopic_id=str(subtopic_id),
        subtopic_name=subtopic.name,
        has_question=question is not None,
        dominant_modality=dominant_modality,
    )

    raw = await llm_router.complete(
        task="concept_guide",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
        max_tokens=600,
    )

    explanation, check_question = _parse_mcq(raw)

    logger.info(
        "concept_guide_generation_completed",
        student_id=str(student.id),
        subtopic_id=str(subtopic_id),
        has_check_question=check_question is not None,
    )

    return {
        "explanation": explanation,
        "subtopic_name": subtopic.name,
        "check_question": check_question,
    }


async def evaluate_mcq_answer(
    *,
    subtopic_name: str,
    question: str,
    options: list[str],
    correct: str,
    student_answer: str,
) -> dict[str, str]:
    """Generate a follow-up response after the student answers the MCQ.

    Correct answer  → warm acknowledgement + suggestion to try an assessment.
    Incorrect answer → re-explanation from a different angle (never say "wrong").

    This is a stateless call — the MCQ context is passed in from the frontend
    so no DB lookup is needed.
    """
    normalised = student_answer.strip().upper()
    if normalised not in _VALID_MCQ_ANSWERS:
        raise ValueError(f"Invalid answer '{student_answer}' — must be one of A, B, C, D")
    is_correct = normalised == correct.strip().upper()

    if is_correct:
        prompt = (
            f'A student just answered a check question about "{subtopic_name}" correctly.\n'
            f"Question: {question}\n"
            f"Their answer: {student_answer} (correct)\n\n"
            "Write a warm, encouraging 1-2 sentence acknowledgement. "
            "Then suggest they try an assessment to test their understanding further. "
            "Keep it brief and positive. No markdown."
        )
    else:
        options_text = "\n".join(options)
        prompt = (
            f'A student answered a check question about "{subtopic_name}" incorrectly.\n'
            f"Question: {question}\n"
            f"Options:\n{options_text}\n"
            f"Their answer: {student_answer} — Correct answer: {correct}\n\n"
            "Re-explain the concept from a different angle in 2-3 sentences. "
            "Do NOT say 'wrong', 'incorrect', or 'that's not right'. "
            "Be encouraging and clarifying. No markdown."
        )

    logger.info(
        "concept_guide_mcq_evaluated",
        subtopic_name=subtopic_name,
        is_correct=is_correct,
    )

    response = await llm_router.complete(
        task="concept_guide",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=150,
    )

    return {
        "is_correct": str(is_correct).lower(),
        "response": response.strip(),
    }
