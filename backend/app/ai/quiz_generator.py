"""Quiz Generator — M3-1-T2.

Generates 5 MCQ practice questions for a student's subtopic gap,
calibrated to student mastery level and personalised with student interests.

Architecture:
- Subtopic context from subtopic_content.get_display_explanation() (or learning_objective fallback)
- Student interests filtered via get_compatible_interests() before injection
- LLM: Gemini 2.5 Flash via complete(task="question_generation")
- No RAG, no curriculum_chunks, no embeddings.
- Validation: keyword relevance + word-count gate.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

import structlog
from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.router import complete
from app.core.questionnaire_config import get_compatible_interests
from app.models import StudentLearningProfile, Subtopic
from app.models.subtopic_content import ContentType, ReviewStatus, SubtopicContent
from app.services.quiz_validator import QuizValidator

logger = structlog.get_logger()

# Hard timeout for LLM call (seconds)
LLM_TIMEOUT_S = 8

# Jinja2 prompt template for quiz generation
QUIZ_PROMPT_TEMPLATE = """System: You are an educational content creator for {{ curriculum_code }} {{ subject_name }}.
        Generate a practice quiz. Return ONLY valid JSON — no preamble, no markdown fences.

Student mastery: {{ mastery_pct }}% on: {{ subtopic_name }}.
Difficulty calibration: {{ difficulty_label }}.

Learning objectives:
{{ learning_objectives }}

Subtopic explanation (use this to anchor questions to what was taught):
{{ subtopic_context }}

{% if top_2_interests %}
Personalisation: Where it fits naturally, frame question scenarios using topics this
student finds interesting: {{ top_2_interests | join(', ') }}.
Do NOT force the interest — academic accuracy is always the priority.
Only use if the scenario genuinely fits the subtopic.
{% endif %}

Generate exactly 5 MCQ questions.
Each MCQ must have exactly 4 options (A, B, C, D).
All questions must be MCQ — no short answer, no true/false.

Return JSON:
{
  "questions": [
    {
      "question_text": "...",
      "type": "MCQ",
      "options": [
        {"key": "A", "text": "..."},
        {"key": "B", "text": "..."},
        {"key": "C", "text": "..."},
        {"key": "D", "text": "..."}
      ],
      "correct_answer": "B",
      "explanation": "..."
    }
  ]
}
"""


class QuestionType(StrEnum):
    """Supported question types."""

    MCQ = "MCQ"


@dataclass
class QuizQuestion:
    """One MCQ question in a generated quiz."""

    question_text: str
    type: QuestionType
    options: list[dict[str, str]]  # [{"key": "A", "text": "..."}, ...]
    correct_answer: str
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_text": self.question_text,
            "type": self.type.value,
            "options": self.options,
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuizQuestion:
        return cls(
            question_text=data["question_text"],
            type=QuestionType(data["type"]),
            options=data["options"],
            correct_answer=data["correct_answer"],
            explanation=data["explanation"],
        )


@dataclass
class GeneratedQuiz:
    """A generated 5-MCQ practice quiz for a student's subtopic."""

    subtopic_id: UUID
    questions: list[QuizQuestion] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    interests_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subtopic_id": str(self.subtopic_id),
            "questions": [q.to_dict() for q in self.questions],
            "generated_at": self.generated_at.isoformat(),
            "interests_used": self.interests_used,
        }


class QuizGenerationError(Exception):
    """Raised when quiz generation fails after retries."""

    pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_quiz(
    subtopic: Subtopic,
    student_mastery: float,  # 0.0–1.0
    student_id: UUID,
    db: AsyncSession,
    grade_level: int = 8,
) -> GeneratedQuiz:
    """Generate a 5-MCQ practice quiz for a student's subtopic.

    Args:
        subtopic: The Subtopic row for the student's knowledge gap.
        student_mastery: Current mastery score (0.0–1.0).
        student_id: UUID of the student.
        db: Async SQLAlchemy session.
        grade_level: Student's grade level (default 8). Used for word-count gate.

    Returns:
        GeneratedQuiz with 5 MCQ questions.

    Raises:
        QuizGenerationError: If LLM call fails, output is invalid, or insufficient
            valid questions remain after retry.
    """
    # 1. Load subtopic context
    subtopic_context = await _load_subtopic_context(subtopic, db)

    # 2. Load student interests (filtered to subject-compatible only)
    compatible_interests = await _load_student_interests(subtopic, student_id, db)
    top_2_interests = compatible_interests[:2]

    # 3. Determine difficulty label
    difficulty_label = _mastery_to_difficulty_label(student_mastery)
    mastery_pct = int(student_mastery * 100)

    # 4. Build prompt
    learning_objectives = subtopic.learning_objective or "Not specified"
    curriculum_code = getattr(subtopic, "curriculum_code", "CAMBRIDGE")

    prompt = _build_prompt(
        curriculum_code=curriculum_code,
        subject_name=getattr(subtopic, "subject_name", "General"),
        subtopic_name=subtopic.name,
        mastery_pct=mastery_pct,
        difficulty_label=difficulty_label,
        learning_objectives=learning_objectives,
        subtopic_context=subtopic_context,
        top_2_interests=top_2_interests,
    )

    # 5. Call LLM with retry
    raw_json = await _call_llm_with_retry(prompt)

    # 6. Parse questions from LLM response
    questions_data = _parse_questions(raw_json)

    # 7. Validate questions (M3-1-T3: semantic similarity + length gate)
    validator = QuizValidator(db)
    valid_question_dicts = await validator.validate_batch(
        questions=[q.to_dict() for q in questions_data],
        subtopic_id=subtopic.id,
        grade_level=grade_level,
    )

    # 8. Retry once if fewer than 5 valid
    if len(valid_question_dicts) < 5:
        needed = 5 - len(valid_question_dicts)
        logger.warning(
            "quiz_insufficient_valid_questions_retrying",
            subtopic_id=str(subtopic.id),
            valid_count=len(valid_question_dicts),
            needed=needed,
        )
        # Ask for needed + 2 extra to account for possible rejection
        retry_prompt = prompt  # Same prompt context
        retry_raw = await _call_llm_with_retry(retry_prompt)
        retry_data = _parse_questions(retry_raw)
        retry_valid = await validator.validate_batch(
            questions=[q.to_dict() for q in retry_data],
            subtopic_id=subtopic.id,
            grade_level=grade_level,
        )
        valid_question_dicts.extend(retry_valid)

    # 9. Degrade gracefully if insufficient
    if len(valid_question_dicts) < 3:
        raise QuizGenerationError(f"Insufficient valid questions after retry: {len(valid_question_dicts)}/5")

    # 10. Take first 5 valid questions
    questions = [QuizQuestion.from_dict(q) for q in valid_question_dicts[:5]]

    logger.info(
        "quiz_generated",
        subtopic_id=str(subtopic.id),
        student_id=str(student_id),
        question_count=len(questions),
        interests_used=top_2_interests,
    )

    return GeneratedQuiz(
        subtopic_id=subtopic.id,
        questions=questions,
        interests_used=top_2_interests,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _load_subtopic_context(
    subtopic: Subtopic,
    db: AsyncSession,
) -> str:
    """Load approved explanation from subtopic_content, or fall back to learning_objective."""
    try:
        result = await db.execute(
            select(SubtopicContent)
            .where(SubtopicContent.subtopic_id == subtopic.id)
            .where(SubtopicContent.content_type == ContentType.EXPLANATION)
            .where(SubtopicContent.review_status == ReviewStatus.APPROVED)
        )
        content = result.scalar_one_or_none()
        if content:
            explanation = content.get_display_explanation()
            if explanation:
                return explanation
    except Exception as exc:
        logger.warning(
            "subtopic_context_load_failed",
            subtopic_id=str(subtopic.id),
            error=str(exc),
        )

    # Fallback
    return f"{subtopic.name}: {subtopic.learning_objective}"


async def _load_student_interests(
    subtopic: Subtopic,
    student_id: UUID,
    db: AsyncSession,
) -> list[str]:
    """Load student's compatible interests for this subject."""
    try:
        profile = await db.get(StudentLearningProfile, student_id)
        if not profile or not profile.interests:
            return []

        # Get subject_code from subtopic
        subject_code = getattr(subtopic, "subject_code", "")
        if not subject_code:
            return []

        compatible = get_compatible_interests(
            subject_code=subject_code,
            student_interests=profile.interests,
        )
        return compatible
    except Exception as exc:
        logger.warning(
            "student_interests_load_failed",
            student_id=str(student_id),
            error=str(exc),
        )
        return []


def _mastery_to_difficulty_label(mastery: float) -> str:
    """Convert mastery score to difficulty calibration label."""
    if mastery < 0.4:
        return "foundational — focus on basic recall and understanding"
    elif mastery < 0.7:
        return "developing — include application and simple problem solving"
    else:
        return "advanced — focus on analysis, evaluation, and novel problems"


def _build_prompt(
    curriculum_code: str,
    subject_name: str,
    subtopic_name: str,
    mastery_pct: int,
    difficulty_label: str,
    learning_objectives: str,
    subtopic_context: str,
    top_2_interests: list[str],
) -> str:
    """Render the Jinja2 prompt template."""
    template = Template(QUIZ_PROMPT_TEMPLATE)
    return template.render(
        curriculum_code=curriculum_code,
        subject_name=subject_name,
        subtopic_name=subtopic_name,
        mastery_pct=mastery_pct,
        difficulty_label=difficulty_label,
        learning_objectives=learning_objectives,
        subtopic_context=subtopic_context,
        top_2_interests=top_2_interests,
    )


async def _call_llm_with_retry(prompt: str) -> dict[str, Any]:
    """Call LLM with one retry on failure."""
    messages = [{"role": "user", "content": prompt}]
    last_exc: Exception = QuizGenerationError("Quiz generation failed after 2 attempts")

    for attempt in range(2):
        try:
            response = await complete(
                task="question_generation",
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )
            return _extract_json(response)
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "quiz_llm_call_failed",
                attempt=attempt + 1,
                error=str(exc),
            )

    raise QuizGenerationError(f"Quiz generation failed after 2 attempts: {last_exc}") from last_exc


def _extract_json(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response text.

    Handles common LLM output patterns like:
    - Plain JSON: {"questions": [...]}
    - JSON with markdown fences: ```json {"questions": [...]}
    """
    text = text.strip()

    # Try direct JSON parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try stripping markdown fences
    fences_pattern = re.compile(r"```(?:json)?\s*([\s\S]+?)\s*```")
    match = fences_pattern.search(text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding first { and last }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace : last_brace + 1])
        except json.JSONDecodeError:
            pass

    raise QuizGenerationError(f"Could not extract valid JSON from LLM response: {text[:200]}")


def _parse_questions(raw_json: dict[str, Any]) -> list[QuizQuestion]:
    """Parse and validate questions from LLM JSON output."""
    questions_data = raw_json.get("questions", [])

    if len(questions_data) != 5:
        raise QuizGenerationError(f"Expected 5 questions, got {len(questions_data)}")

    # Count MCQ
    mcq_count = sum(1 for q in questions_data if q.get("type") == "MCQ")
    if mcq_count != 5:
        raise QuizGenerationError(f"Expected all 5 MCQ questions, got {mcq_count} MCQ")

    questions = []
    for q_data in questions_data:
        # Validate options
        options = q_data.get("options", [])
        if len(options) != 4:
            raise QuizGenerationError(
                f"Question '{q_data.get('question_text', '')[:30]}...' has {len(options)} options, expected 4"
            )

        # Ensure all options have key and text
        for opt in options:
            if "key" not in opt or "text" not in opt:
                raise QuizGenerationError("Options must have 'key' and 'text' fields")

        questions.append(QuizQuestion.from_dict(q_data))

    return questions
