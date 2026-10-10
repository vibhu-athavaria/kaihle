"""Canonical MCQ model shared by every question-quality eval.

The two production shapes differ: the practice-quiz path uses ``options=[{"key","text"}]`` with
``type="MCQ"`` (``app.ai.quiz_generator.QuizQuestion``) while the question bank uses
``options={"A": ...}`` with ``question_type="multiple_choice"``. Rubrics and deterministic checks
work on ``EvalQuestion`` only; adapters convert at the edges.
"""

from dataclasses import dataclass
from typing import Any, Literal, Self

from app.ai.quiz_generator import QuizQuestion

OPTION_KEYS = ("A", "B", "C", "D")
DifficultyBand = Literal["foundational", "developing", "advanced"]

# The bank schema requires bloom/time/hints, which EvalQuestion does not model. These are fixed,
# content-free fillers so ``validate_question`` can run on the fields that matter; they are
# derived from the band, never judged.
_BAND_BLOOM: dict[str, str] = {"foundational": "Remember", "developing": "Apply", "advanced": "Analyze"}
_BAND_DIFFICULTY: dict[str, int] = {"foundational": 1, "developing": 3, "advanced": 5}
_PLACEHOLDER_TIME_SECONDS = 60
_PLACEHOLDER_HINTS = {"hint1": "hint 1", "hint2": "hint 2", "hint3": "hint 3"}


@dataclass(frozen=True)
class EvalQuestion:
    """One four-option MCQ plus the context a rubric needs. Invalid shapes cannot be built."""

    id: str
    subject_code: str
    grade_level: int
    subtopic_name: str
    learning_objective: str
    difficulty_band: DifficultyBand
    # 1-5 when known; None when the source (e.g. the practice-quiz path) does not carry it.
    difficulty_level: int | None
    question_text: str
    options: dict[str, str]
    correct_answer: str
    explanation: str

    def __post_init__(self) -> None:
        if tuple(sorted(self.options)) != OPTION_KEYS:
            raise ValueError(f"options must have exactly keys A, B, C, D - got {sorted(self.options)}")
        if self.correct_answer not in self.options:
            raise ValueError(f"correct_answer {self.correct_answer!r} is not one of the option keys")

    def to_quiz_dict(self) -> dict[str, Any]:
        return {
            "question_text": self.question_text,
            "type": "MCQ",
            "options": [{"key": key, "text": self.options[key]} for key in OPTION_KEYS],
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
        }

    def to_bank_dict(self) -> dict[str, Any]:
        """Bank-shaped dict that ``validate_question`` accepts (fillers documented above)."""
        return {
            "question_text": self.question_text,
            "question_type": "multiple_choice",
            "options": dict(self.options),
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "learning_objectives": [self.learning_objective],
            "difficulty_level": self.difficulty_level
            if self.difficulty_level is not None
            else _BAND_DIFFICULTY[self.difficulty_band],
            "bloom_taxonomy_level": _BAND_BLOOM[self.difficulty_band],
            "estimated_time_seconds": _PLACEHOLDER_TIME_SECONDS,
            "hints": dict(_PLACEHOLDER_HINTS),
        }

    @classmethod
    def from_quiz_question(
        cls,
        question: QuizQuestion,
        *,
        id: str,
        subject_code: str,
        grade_level: int,
        subtopic_name: str,
        learning_objective: str,
        difficulty_band: DifficultyBand,
        difficulty_level: int | None = None,
    ) -> Self:
        return cls(
            id=id,
            subject_code=subject_code,
            grade_level=grade_level,
            subtopic_name=subtopic_name,
            learning_objective=learning_objective,
            difficulty_band=difficulty_band,
            difficulty_level=difficulty_level,
            question_text=question.question_text,
            options={option["key"]: option["text"] for option in question.options},
            correct_answer=question.correct_answer,
            explanation=question.explanation,
        )

    @classmethod
    def from_bank_dict(
        cls,
        data: dict[str, Any],
        *,
        id: str,
        subject_code: str,
        grade_level: int,
        subtopic_name: str,
        difficulty_band: DifficultyBand,
    ) -> Self:
        """Build from a bank question; the bank dict carries no id/subject/grade/band, so callers pass them."""
        objectives = data["learning_objectives"]
        return cls(
            id=id,
            subject_code=subject_code,
            grade_level=grade_level,
            subtopic_name=subtopic_name,
            learning_objective=objectives[0] if objectives else "",
            difficulty_band=difficulty_band,
            difficulty_level=int(float(data["difficulty_level"])),
            question_text=data["question_text"],
            options=dict(data["options"]),
            correct_answer=data["correct_answer"],
            explanation=data["explanation"],
        )

    # New adapters (classmethods) append below this line; do not reorder the ones above.
