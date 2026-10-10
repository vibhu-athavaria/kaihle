"""EvalQuestion: construction invariants and quiz/bank adapters."""

from dataclasses import replace
from typing import Any

import pytest

from app.ai.quiz_generator import QuizQuestion
from evals.question_model import EvalQuestion

_META: dict[str, Any] = {
    "id": "q1",
    "subject_code": "MATH",
    "grade_level": 7,
    "subtopic_name": "Adding fractions",
    "difficulty_band": "developing",
}


def _question(**overrides: Any) -> EvalQuestion:
    fields: dict[str, Any] = {
        **_META,
        "learning_objective": "Add fractions with unlike denominators",
        "difficulty_level": 3,
        "question_text": "What is 1/2 + 1/3?",
        "options": {"A": "5/6", "B": "2/5", "C": "1/6", "D": "3/5"},
        "correct_answer": "A",
        "explanation": "Common denominator 6: 3/6 + 2/6 = 5/6.",
    }
    fields.update(overrides)
    return EvalQuestion(**fields)


def test_eval_question_when_converted_to_quiz_dict_then_options_are_key_text_objects() -> None:
    quiz = _question().to_quiz_dict()

    assert quiz["type"] == "MCQ"
    assert quiz["options"] == [
        {"key": "A", "text": "5/6"},
        {"key": "B", "text": "2/5"},
        {"key": "C", "text": "1/6"},
        {"key": "D", "text": "3/5"},
    ]
    assert quiz["correct_answer"] == "A"


def test_eval_question_when_converted_to_bank_dict_then_options_are_key_value_dict_and_type_multiple_choice() -> None:
    bank = _question().to_bank_dict()

    assert bank["question_type"] == "multiple_choice"
    assert bank["options"] == {"A": "5/6", "B": "2/5", "C": "1/6", "D": "3/5"}
    assert bank["correct_answer"] == "A"
    assert bank["learning_objectives"] == ["Add fractions with unlike denominators"]


def test_eval_question_when_round_tripped_through_quiz_dict_then_equal() -> None:
    original = _question()

    restored = EvalQuestion.from_quiz_question(
        QuizQuestion.from_dict(original.to_quiz_dict()),
        learning_objective=original.learning_objective,
        difficulty_level=original.difficulty_level,
        **_META,
    )

    assert restored == original


def test_eval_question_when_round_tripped_through_bank_dict_then_equal() -> None:
    original = _question()

    restored = EvalQuestion.from_bank_dict(original.to_bank_dict(), **_META)

    assert restored == original


def test_eval_question_when_key_not_an_option_then_raises() -> None:
    with pytest.raises(ValueError, match="correct_answer"):
        _question(correct_answer="E")


@pytest.mark.parametrize(
    "options",
    [
        {"A": "a", "B": "b", "C": "c"},
        {"A": "a", "B": "b", "C": "c", "D": "d", "E": "e"},
        {"A": "a", "B": "b", "C": "c", "X": "d"},
    ],
)
def test_eval_question_when_options_not_exactly_a_to_d_then_raises(options: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="options"):
        _question(options=options)


def test_eval_question_when_modified_via_replace_then_revalidated() -> None:
    with pytest.raises(ValueError, match="correct_answer"):
        replace(_question(), correct_answer="Z")
