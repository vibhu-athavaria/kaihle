"""Offline tests for the MCQ quality rubrics (R1-R7). The judge is mocked; no network, no DB."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from deepeval.metrics import BaseMetric

from evals.deterministic_checks import find_banned_phrases
from evals.judge import RouterJudge
from evals.question_model import DifficultyBand, EvalQuestion
from evals.question_rubrics import (
    DISTRACTOR_PLAUSIBILITY_SPEC,
    EXACTLY_ONE_CORRECT_SPEC,
    GRADE_CALIBRATION_SPEC,
    OBJECTIVE_ALIGNMENT_SPEC,
    BlindSolveMetric,
    ExactlyOneCorrectMetric,
    explanation_spec,
    question_case,
    understanding_spec,
)
from evals.rubric_core import BinaryRubricMetric, RubricSpec

_MODEL_NAMES = ("gpt", "claude", "gemini", "llama", "sonnet", "opus", "haiku")


def _question() -> EvalQuestion:
    return EvalQuestion(
        id="q1",
        subject_code="MATH",
        grade_level=7,
        subtopic_name="Fractions",
        learning_objective="Add fractions with unlike denominators",
        difficulty_band="developing",
        difficulty_level=3,
        question_text="What is 1/2 + 1/3?",
        options={"A": "2/5", "B": "5/6", "C": "1/6", "D": "2/6"},
        correct_answer="B",
        explanation="The common denominator is 6, so 3/6 + 2/6 = 5/6.",
    )


def _case_data() -> dict[str, str]:
    return {str(k): str(v) for k, v in (question_case(_question()).metadata or {}).items()}


async def _run(metric: BaseMetric, reply: str) -> None:
    with patch.object(RouterJudge, "a_generate", new_callable=AsyncMock) as generate:
        generate.return_value = reply
        await metric.a_measure(question_case(_question()))


def test_blind_solve_prompt_when_built_then_excludes_answer_key_and_explanation() -> None:
    question = _question()

    prompt = BlindSolveMetric(RouterJudge()).build_prompt(_case_data())

    assert question.question_text in prompt
    assert "5/6" in prompt  # options are shown
    assert question.explanation not in prompt
    assert "common denominator" not in prompt
    assert "[key]" not in prompt
    assert "[explanation]" not in prompt


async def test_blind_solve_metric_when_judge_answer_matches_key_then_passes() -> None:
    metric = BlindSolveMetric(RouterJudge())

    await _run(metric, '{"answer": "B", "working": "3/6 + 2/6"}')

    assert metric.verdict is True
    assert metric.is_successful() is True
    assert metric.score == 1.0


async def test_blind_solve_metric_when_judge_answer_differs_then_fails_and_reason_names_both_letters() -> None:
    metric = BlindSolveMetric(RouterJudge())

    await _run(metric, '{"answer": "C", "working": "guess"}')

    assert metric.verdict is False
    assert metric.is_successful() is False
    assert "chose C" in str(metric.reason) and "key is B" in str(metric.reason)


@pytest.mark.parametrize("reply", ['{"answer": "E"}', '{"answer": "ab"}', "not json", '{"working": "x"}'])
async def test_blind_solve_metric_when_judge_answer_not_a_to_d_then_indeterminate(reply: str) -> None:
    metric = BlindSolveMetric(RouterJudge())

    await _run(metric, reply)

    assert metric.verdict is None
    assert metric.indeterminate is True
    assert metric.is_successful() is False


async def test_exactly_one_correct_when_judge_marks_two_options_correct_then_fails() -> None:
    metric = ExactlyOneCorrectMetric(RouterJudge())

    await _run(metric, json.dumps({"correct_options": ["B", "D"], "evidence": "2/6 is not 5/6"}))

    assert metric.verdict is False
    assert metric.indeterminate is False


async def test_exactly_one_correct_when_judge_marks_only_keyed_option_correct_then_passes() -> None:
    metric = ExactlyOneCorrectMetric(RouterJudge())

    await _run(metric, json.dumps({"correct_options": ["B"], "evidence": "only B"}))

    assert metric.verdict is True
    assert metric.is_successful() is True


async def test_exactly_one_correct_when_judge_marks_a_different_option_correct_then_fails() -> None:
    metric = ExactlyOneCorrectMetric(RouterJudge())

    await _run(metric, json.dumps({"correct_options": ["A"], "evidence": "wrong key"}))

    assert metric.verdict is False


async def test_exactly_one_correct_when_reply_unusable_then_indeterminate_not_pass() -> None:
    metric = ExactlyOneCorrectMetric(RouterJudge())

    await _run(metric, '{"correct_options": "B"}')

    assert metric.verdict is None
    assert metric.indeterminate is True
    assert metric.is_successful() is False


def test_understanding_rubric_when_band_foundational_then_prompt_permits_recall() -> None:
    spec = understanding_spec("foundational")

    assert "recall is acceptable" in spec.instructions.lower()


@pytest.mark.parametrize("band", ["developing", "advanced"])
def test_understanding_rubric_when_band_advanced_then_prompt_does_not_permit_recall(band: DifficultyBand) -> None:
    spec = understanding_spec(band)

    assert "recall is acceptable" not in spec.instructions.lower()
    assert "must not be answerable by recall" in spec.instructions.lower()
    assert spec.text_hash != understanding_spec("foundational").text_hash


def test_explanation_rubric_when_path_is_bank_then_prompt_requires_why_each_wrong_option_is_wrong() -> None:
    spec = explanation_spec("bank")

    assert "each wrong option" in spec.instructions.lower()


def test_explanation_rubric_when_path_is_quiz_then_prompt_requires_only_why_correct_is_right() -> None:
    spec = explanation_spec("quiz")

    assert "each wrong option" not in spec.instructions.lower()
    assert "why the keyed option is right" in spec.instructions.lower()
    assert spec.text_hash != explanation_spec("bank").text_hash


def _binary_specs() -> list[RubricSpec]:
    return [
        EXACTLY_ONE_CORRECT_SPEC,
        DISTRACTOR_PLAUSIBILITY_SPEC,
        OBJECTIVE_ALIGNMENT_SPEC,
        GRADE_CALIBRATION_SPEC,
        understanding_spec("foundational"),
        understanding_spec("advanced"),
        explanation_spec("bank"),
        explanation_spec("quiz"),
    ]


def test_all_rubric_prompts_when_rendered_then_contain_no_banned_compliance_phrases_or_model_names() -> None:
    case = _case_data()
    prompts = [BinaryRubricMetric(spec, RouterJudge()).build_prompt(case) for spec in _binary_specs()]
    prompts.append(BlindSolveMetric(RouterJudge()).build_prompt(case))
    prompts.append(ExactlyOneCorrectMetric(RouterJudge()).build_prompt(case))

    for prompt in prompts:
        assert find_banned_phrases(prompt) == []
        assert not any(name in prompt.lower() for name in _MODEL_NAMES)


def test_rubric_specs_when_listed_then_ids_are_distinct_and_params_exist_in_case() -> None:
    specs = _binary_specs()

    assert len({spec.id for spec in specs}) == len(specs)
    for spec in specs:
        assert set(spec.params) <= set(_case_data())


async def test_judge_rubric_metrics_when_judge_passes_then_each_is_successful() -> None:
    for spec in (DISTRACTOR_PLAUSIBILITY_SPEC, OBJECTIVE_ALIGNMENT_SPEC, GRADE_CALIBRATION_SPEC):
        metric = BinaryRubricMetric(spec, RouterJudge())

        await _run(metric, '{"pass": true, "evidence": "ok"}')

        assert metric.is_successful() is True


def test_question_case_when_difficulty_unknown_then_says_not_specified() -> None:
    question = EvalQuestion(**{**_question().__dict__, "difficulty_level": None})

    assert (question_case(question).metadata or {})["difficulty_level"] == "not specified"
