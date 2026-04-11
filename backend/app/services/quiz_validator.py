"""Quiz Validator — M3-1-T3.

Validates LLM-generated quiz questions for topic relevance and grade-appropriate
length. No pgvector, no embeddings — uses keyword overlap and structural checks.

Validation gates (in order):
1. Keyword relevance: at least one key term from subtopic name/objective appears
   in the question text (case-insensitive). Prevents completely off-topic questions.
2. Length gate: word_count <= MAX_QUESTION_WORDS. Keeps questions accessible.
3. Options gate: question has at least 2 answer options.
4. Answer gate: correct_answer key is present in the options list.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import Subtopic

logger = structlog.get_logger()

# Maximum words in a question before it's flagged as too complex for Gr.6-10.
MAX_QUESTION_WORDS = 120

# Minimum number of key terms from subtopic name/objective that must appear
# in the question text (case-insensitive word overlap).
MIN_KEYWORD_MATCHES = 1

# Stop-words excluded from keyword extraction (too generic to be meaningful).
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "is",
        "are",
        "was",
        "were",
        "it",
        "its",
        "that",
        "this",
        "which",
        "with",
        "for",
        "on",
        "at",
        "by",
        "be",
        "as",
        "from",
        "has",
        "have",
        "had",
        "not",
        "but",
        "what",
        "how",
        "when",
        "where",
        "who",
        "will",
        "can",
        "do",
        "does",
        "did",
        "if",
        "so",
        "than",
        "then",
        "into",
        "more",
        "about",
        "also",
        "use",
        "used",
        "using",
        "between",
        "through",
        "after",
        "before",
    }
)


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful lower-case word tokens, excluding stop-words."""
    tokens = re.findall(r"[a-z]+", text.lower())
    return {t for t in tokens if t not in _STOP_WORDS and len(t) > 2}


class QuizValidationError(Exception):
    """Raised when quiz validation encounters a system error (not a quality rejection)."""

    pass


class QuizValidator:
    """Validates quiz questions for topic relevance and grade-appropriate length."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_question(
        self,
        question_text: str,
        subtopic_id: UUID,
        grade_level: int,
        question: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Validate a single question against the target subtopic.

        Args:
            question_text: The text of the generated MCQ question.
            subtopic_id: UUID of the target subtopic.
            grade_level: Student's grade level (reserved for future use).
            question: Full question dict (for options/answer structural checks).

        Returns:
            (is_valid: bool, rejection_reason: str | "")
        """
        # Gate 1: Keyword relevance
        subtopic = await self._get_subtopic(subtopic_id)
        if subtopic is not None:
            subtopic_keywords = _extract_keywords(subtopic.name)
            if subtopic.learning_objective:
                subtopic_keywords |= _extract_keywords(subtopic.learning_objective)

            question_keywords = _extract_keywords(question_text)
            overlap = subtopic_keywords & question_keywords

            if subtopic_keywords and len(overlap) < MIN_KEYWORD_MATCHES:
                logger.warning(
                    "quiz_question_rejected_no_keyword_overlap",
                    subtopic_id=str(subtopic_id),
                    subtopic_keywords=sorted(subtopic_keywords)[:10],
                    question_preview=question_text[:80],
                )
                return False, "Question contains no keywords from the subtopic"
        else:
            logger.warning(
                "quiz_validation_skipped_no_subtopic",
                subtopic_id=str(subtopic_id),
            )

        # Gate 2: Length / complexity heuristic
        word_count = len(question_text.split())
        if word_count > MAX_QUESTION_WORDS:
            logger.warning(
                "quiz_question_rejected_too_complex",
                word_count=word_count,
                max=MAX_QUESTION_WORDS,
                question_preview=question_text[:80],
            )
            return False, f"Question too long ({word_count} words > {MAX_QUESTION_WORDS})"

        # Gate 3: Structural checks (requires full question dict)
        if question is not None:
            options = question.get("options", [])
            if len(options) < 2:
                return False, "Question has fewer than 2 answer options"

            correct_answer = question.get("correct_answer", "")
            option_keys = {opt.get("key", "") for opt in options}
            if correct_answer not in option_keys:
                return False, f"correct_answer '{correct_answer}' not in options {sorted(option_keys)}"

        return True, ""

    async def validate_batch(
        self,
        questions: list[dict[str, Any]],
        subtopic_id: UUID,
        grade_level: int,
    ) -> list[dict[str, Any]]:
        """Validate a batch of generated questions.

        Returns only questions that pass all validation gates.
        Logs rejected questions with reasons.
        """
        validated = []
        rejected_count = 0

        for q in questions:
            is_valid, reason = await self.validate_question(
                question_text=q["question_text"],
                subtopic_id=subtopic_id,
                grade_level=grade_level,
                question=q,
            )
            if is_valid:
                validated.append(q)
            else:
                rejected_count += 1
                logger.info(
                    "quiz_question_rejected",
                    subtopic_id=str(subtopic_id),
                    reason=reason,
                    question_preview=q.get("question_text", "")[:80],
                )

        if rejected_count > 0:
            logger.info(
                "quiz_validation_batch_complete",
                total=len(questions),
                passed=len(validated),
                rejected=rejected_count,
            )

        return validated

    async def _get_subtopic(self, subtopic_id: UUID) -> Subtopic | None:
        """Fetch subtopic by ID."""
        result = await self.db.execute(select(Subtopic).where(Subtopic.id == subtopic_id))
        return result.scalar_one_or_none()
