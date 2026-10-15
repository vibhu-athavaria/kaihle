"""Offline tests for the production question-quality judge meta-evaluation. complete() is mocked."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from evals import prod_judge
from evals.calibration_set.build import SHIPPED_PATH, load_calibration_cases
from evals.prod_judge import map_prod_verdict, prod_verdicts_for_case, run_prod_judge
from scripts.validate_and_fix_questions import QUALITY_MAX_TOKENS, QUALITY_SYSTEM_PROMPT, QUALITY_TEMPERATURE

QUESTION = load_calibration_cases(SHIPPED_PATH)[0].question
NAMES = (
    "factual_accuracy",
    "difficulty_calibration",
    "subtopic_alignment",
    "distractor_quality",
    "self_contained",
    "rendering_safe",
    "content_domain",
)


def _validations(**overrides: bool) -> dict[str, object]:
    out: dict[str, object] = {n: {"pass": True, "note": "ok"} for n in NAMES}
    for name, value in overrides.items():
        out[name] = {"pass": value, "note": "x"}
    return out


def _reply(validations: dict[str, object]) -> str:
    return json.dumps({"questions": [{"index": 0, "overall_pass": True, "validations": validations}]})


async def test_run_prod_judge_when_called_then_prompt_comes_from_production_build_validation_prompt() -> None:
    with (
        patch("evals.prod_judge.complete", new_callable=AsyncMock, return_value=_reply(_validations())) as complete,
        patch("evals.prod_judge.build_validation_prompt", return_value="PROD PROMPT") as build,
    ):
        await run_prod_judge(QUESTION)

    info, questions = build.call_args.args
    assert info["learning_objective"] == QUESTION.learning_objective
    assert questions == [QUESTION.to_bank_dict()]
    assert complete.call_args.kwargs["messages"][-1] == {"role": "user", "content": "PROD PROMPT"}


async def test_run_prod_judge_when_called_then_uses_question_quality_task_with_production_params() -> None:
    with patch("evals.prod_judge.complete", new_callable=AsyncMock, return_value=_reply(_validations())) as complete:
        await run_prod_judge(QUESTION)

    kwargs = complete.call_args.kwargs
    assert kwargs["task"] == "question_quality"
    assert kwargs["temperature"] == QUALITY_TEMPERATURE
    assert kwargs["max_tokens"] == QUALITY_MAX_TOKENS
    assert kwargs["messages"][0] == {"role": "system", "content": QUALITY_SYSTEM_PROMPT}


async def test_run_prod_judge_when_reply_is_not_json_then_returns_empty_validations_and_logs() -> None:
    with (
        patch("evals.prod_judge.complete", new_callable=AsyncMock, return_value="garbled"),
        patch.object(prod_judge, "logger") as logger,
    ):
        result = await run_prod_judge(QUESTION)

    assert result == {}
    logger.warning.assert_called_once()


async def test_run_prod_judge_when_router_raises_then_exception_propagates() -> None:
    with (
        patch("evals.prod_judge.complete", new_callable=AsyncMock, side_effect=RuntimeError("down")),
        pytest.raises(RuntimeError, match="down"),
    ):
        await run_prod_judge(QUESTION)


def test_map_prod_verdict_when_factual_accuracy_fails_then_key_correctness_and_exactly_one_correct_marked_failed() -> (
    None
):
    mapped = map_prod_verdict(_validations(factual_accuracy=False))

    assert mapped["R1_key_correctness"] is False
    assert mapped["R2_exactly_one_correct"] is False
    assert mapped["R3_distractor_plausibility"] is True


def test_map_prod_verdict_when_distractor_quality_fails_then_plausibility_and_unique_options_marked_failed() -> None:
    mapped = map_prod_verdict(_validations(distractor_quality=False))

    assert mapped["R3_distractor_plausibility"] is False
    assert mapped["unique_options"] is False


def test_map_prod_verdict_when_all_criteria_pass_then_every_mapped_criterion_passes() -> None:
    mapped = map_prod_verdict(_validations())

    assert set(mapped) == {
        "R1_key_correctness",
        "R2_exactly_one_correct",
        "R3_distractor_plausibility",
        "R4_objective_alignment",
        "R5_grade_calibration",
        "unique_options",
        "self_contained",
        "rendering_safe",
    }
    assert all(v is True for v in mapped.values())


def test_map_prod_verdict_when_criterion_missing_then_that_criterion_is_indeterminate() -> None:
    validations = _validations()
    del validations["subtopic_alignment"]
    validations["rendering_safe"] = {"note": "no pass field"}

    mapped = map_prod_verdict(validations)

    assert mapped["R4_objective_alignment"] is None
    assert mapped["rendering_safe"] is None
    assert mapped["R5_grade_calibration"] is True


def test_map_prod_verdict_when_content_domain_present_then_it_is_not_scored() -> None:
    mapped = map_prod_verdict(_validations(content_domain=False))

    assert all(v is True for v in mapped.values())


def test_prod_verdicts_for_case_when_scheduled_criteria_given_then_only_mapped_ones_become_verdicts() -> None:
    mapped = map_prod_verdict(_validations(factual_accuracy=False))
    scheduled = [("R1_key_correctness", False), ("R6_understanding_not_recall_foundational", True)]

    verdicts = prod_verdicts_for_case("c1", "wrong_key", "computed", scheduled, mapped)

    assert [(v.criterion, v.expected_pass, v.observed_pass) for v in verdicts] == [("R1_key_correctness", False, False)]


def test_prod_verdicts_for_case_when_judge_gave_no_result_then_observed_is_none() -> None:
    verdicts = prod_verdicts_for_case("c1", None, "computed", [("rendering_safe", True)], map_prod_verdict({}))

    assert [v.observed_pass for v in verdicts] == [None]
