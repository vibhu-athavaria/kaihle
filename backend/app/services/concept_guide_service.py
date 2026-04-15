"""Concept guide service.

Generates personalised explanations for subtopics the student is struggling with.
Uses the student's learning profile (modality, interests) to tailor the output.

All LLM calls route through app.ai.providers.router (Rule 4 compliance).
"""

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
    best = max(modality_scores, key=lambda k: modality_scores.get(k, 0.0))
    return label_map.get(best, best.replace("_", " "))


async def generate_concept_explanation(
    *,
    student: User,
    subtopic_id: UUID,
    question: str | None,
    db: AsyncSession,
) -> dict[str, str]:
    """Generate a personalised concept explanation for the student.

    Args:
        student: The requesting student User object.
        subtopic_id: UUID of the subtopic to explain.
        question: Optional specific question from the student.
        db: Async database session.

    Returns:
        dict with keys: explanation (str), subtopic_name (str).

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

    modality_scores = profile.modality_scores if profile else {}
    work_style = profile.work_style if profile else {}
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

    explanation = await llm_router.complete(
        task="concept_guide",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
        max_tokens=400,
    )

    logger.info(
        "concept_guide_generation_completed",
        student_id=str(student.id),
        subtopic_id=str(subtopic_id),
    )

    return {
        "explanation": explanation.strip(),
        "subtopic_name": subtopic.name,
    }
