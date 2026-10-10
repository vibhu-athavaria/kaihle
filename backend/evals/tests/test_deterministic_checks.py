"""Pure deterministic checks over EvalQuestion (SD-12: code before judge)."""

from typing import Any
from unittest.mock import patch

import pytest

from evals.deterministic_checks import (
    CheckResult,
    check_answer_not_in_stem,
    check_bank_schema,
    check_no_compliance_language,
    check_no_duplicate_questions_in_set,
    check_rendering_safe,
    check_self_contained,
    check_stem_opener_variety,
    check_true_false_share,
    check_unique_options,
    summarise_key_distribution,
)
from evals.question_model import EvalQuestion


def _q(**overrides: Any) -> EvalQuestion:
    fields: dict[str, Any] = {
        "id": "q1",
        "subject_code": "MATH",
        "grade_level": 7,
        "subtopic_name": "Adding fractions",
        "learning_objective": "Add fractions",
        "difficulty_band": "developing",
        "difficulty_level": 3,
        "question_text": "What is the sum of one half and one third?",
        "options": {"A": "5/6", "B": "2/5", "C": "1/6", "D": "3/5"},
        "correct_answer": "A",
        "explanation": "Common denominator.",
    }
    fields.update(overrides)
    return EvalQuestion(**fields)


def test_check_unique_options_when_duplicate_after_normalisation_then_fails_naming_keys() -> None:
    result = check_unique_options(_q(options={"A": "Five  Sixths", "B": "five sixths", "C": "1/6", "D": "3/5"}))

    assert isinstance(result, CheckResult)
    assert not result.passed
    assert "A" in result.detail and "B" in result.detail


def test_check_unique_options_when_all_distinct_then_passes() -> None:
    assert check_unique_options(_q()).passed


@pytest.mark.parametrize(
    "stem",
    [
        "Look at the diagram below. What is the area?",
        "Refer to the graph and find the gradient.",
        "What does the value in the table above show?",
        "The angles are shown below. Find x.",
        "Using the following image, name the shape.",
    ],
)
def test_check_self_contained_when_references_unseen_material_then_fails(stem: str) -> None:
    assert not check_self_contained(_q(question_text=stem)).passed


def test_check_self_contained_when_shape_described_in_words_then_passes() -> None:
    stem = "A triangle has sides of 3 cm, 4 cm and 5 cm. What is its perimeter?"
    assert check_self_contained(_q(question_text=stem)).passed


def test_check_self_contained_when_passage_excerpt_included_then_passes() -> None:
    stem = 'Read this sentence: "The wind howled through the empty corridor." Which device is used?'
    assert check_self_contained(_q(question_text=stem)).passed


@pytest.mark.parametrize(
    "stem",
    [
        "Evaluate $x^2$ when x = 3.",
        r"Simplify \frac{1}{2} + \frac{1}{3}.",
        "Which is **bold** here?",
        "What does `print` do?",
        "Line one<br>line two",
        "Evaluate x^2 when x = 3.",
        "Evaluate x squared when x = 3.",
    ],
)
def test_check_rendering_safe_when_markup_present_then_fails(stem: str) -> None:
    assert not check_rendering_safe(_q(question_text=stem)).passed


def test_check_rendering_safe_when_unicode_symbols_used_then_passes() -> None:
    assert check_rendering_safe(_q(question_text="Evaluate x² + ½ × 4 when x = 3.")).passed


def test_check_rendering_safe_when_markup_only_in_option_then_fails() -> None:
    assert not check_rendering_safe(_q(options={"A": "$5/6$", "B": "2/5", "C": "1/6", "D": "3/5"})).passed


def test_check_no_compliance_language_when_banned_phrase_present_then_fails() -> None:
    result = check_no_compliance_language(_q(explanation="This is a Cambridge-compliant, exam-ready item."))

    assert not result.passed
    assert "cambridge-compliant" in result.detail.lower()


def test_check_no_compliance_language_when_curriculum_informed_then_passes() -> None:
    assert check_no_compliance_language(_q(explanation="A curriculum-informed worked example.")).passed


def test_check_answer_not_in_stem_when_correct_option_text_appears_verbatim_then_fails() -> None:
    stem = "Is the answer five sixths when you add one half and one third?"
    q = _q(question_text=stem, options={"A": "five sixths", "B": "2/5", "C": "1/6", "D": "3/5"})

    assert not check_answer_not_in_stem(q).passed


def test_check_answer_not_in_stem_when_option_text_shorter_than_threshold_then_ignored() -> None:
    q = _q(question_text="Is 5/6 correct? What is 1/2 + 1/3?")

    assert check_answer_not_in_stem(q).passed


def test_check_no_duplicate_questions_in_set_when_identical_normalised_stems_then_fails() -> None:
    qs = [_q(id="a", question_text="What is 2 + 2?"), _q(id="b", question_text="  what is 2 +  2? ")]

    result = check_no_duplicate_questions_in_set(qs)

    assert not result.passed
    assert "a" in result.detail and "b" in result.detail


def test_check_no_duplicate_questions_in_set_when_distinct_then_passes() -> None:
    qs = [_q(id="a", question_text="What is 2 + 2?"), _q(id="b", question_text="What is 3 + 3?")]
    assert check_no_duplicate_questions_in_set(qs).passed


def test_check_stem_opener_variety_when_three_share_first_three_words_then_fails() -> None:
    qs = [_q(id=str(i), question_text=f"Which of the following is {i}?") for i in range(3)]

    assert not check_stem_opener_variety(qs).passed


def test_check_stem_opener_variety_when_only_two_share_then_passes() -> None:
    qs = [
        _q(id="1", question_text="Which of the following is odd?"),
        _q(id="2", question_text="Which of the following is even?"),
        _q(id="3", question_text="Calculate the area of a square."),
    ]

    assert check_stem_opener_variety(qs).passed


def test_check_true_false_share_when_over_a_quarter_then_fails() -> None:
    assert not check_true_false_share(true_false_count=3, total=10).passed


def test_check_true_false_share_when_at_a_quarter_then_passes() -> None:
    assert check_true_false_share(true_false_count=1, total=4).passed


def test_check_true_false_share_when_empty_then_passes() -> None:
    assert check_true_false_share(true_false_count=0, total=0).passed


def test_summarise_key_distribution_when_questions_given_then_counts_and_max_share_reported() -> None:
    qs = [_q(id="1", correct_answer="A"), _q(id="2", correct_answer="A"), _q(id="3", correct_answer="B")]

    summary = summarise_key_distribution(qs)

    assert summary.counts == {"A": 2, "B": 1, "C": 0, "D": 0}
    assert summary.max_share == pytest.approx(2 / 3)


def test_summarise_key_distribution_when_empty_then_does_not_raise() -> None:
    summary = summarise_key_distribution([])

    assert summary.counts == {"A": 0, "B": 0, "C": 0, "D": 0}
    assert summary.max_share == 0.0


def test_check_bank_schema_when_validate_question_returns_errors_then_fails_with_them_as_detail() -> None:
    with patch("evals.deterministic_checks.validate_question", return_value=["bad hints", "bad bloom"]) as mocked:
        result = check_bank_schema(_q())

    assert not result.passed
    assert "bad hints" in result.detail and "bad bloom" in result.detail
    assert mocked.call_args.args[1] == "MATH"


def test_check_bank_schema_when_bank_dict_valid_then_passes() -> None:
    assert check_bank_schema(_q()).passed
