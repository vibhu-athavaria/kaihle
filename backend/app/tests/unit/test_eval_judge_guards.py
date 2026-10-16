"""Unit tests for the DeepEval-free judge guards used by production evaluation (MLH-T18 slice 4).

The guards are pure: judge model and task->model map are parameters, never read from globals.
"""

import pytest

from app.ai.eval.judge_config import JudgeConfigError, JudgeNotConfiguredError, JudgeNotIndependentError
from app.ai.eval.judge_guards import (
    JUDGE_UNSET_MESSAGE,
    RowIndependence,
    config_problem,
    row_independence,
    task_problem,
    vendor_token,
)

JUDGE = "vendor-j/judge-1"
TASK_MAP = {"graded": "vendor-g/model-1", "same_vendor": "vendor-j/other", "blank": ""}


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("openrouter/Vendor-X/model", "vendor-x"),
        ("vendor-x/model", "vendor-x"),
        ("bare-model", None),
        ("openrouter/bare-model", None),
    ],
)
def test_vendor_token_when_model_string_given_then_returns_lowercase_leading_segment_or_none(
    model: str, expected: str | None
) -> None:
    assert vendor_token(model) == expected


def test_row_independence_when_row_model_equals_judge_then_same_model() -> None:
    assert row_independence(JUDGE, JUDGE) is RowIndependence.SAME_MODEL


def test_row_independence_when_row_model_shares_vendor_then_same_vendor() -> None:
    assert row_independence(JUDGE, "openrouter/vendor-j/older-model") is RowIndependence.SAME_VENDOR


def test_row_independence_when_row_model_differs_then_independent() -> None:
    assert row_independence(JUDGE, "vendor-g/model-1") is RowIndependence.INDEPENDENT


def test_row_independence_when_models_have_no_vendor_segment_then_independent_unless_equal() -> None:
    assert row_independence("bare-judge", "bare-other") is RowIndependence.INDEPENDENT
    assert row_independence("bare-judge", "bare-judge") is RowIndependence.SAME_MODEL


def test_row_independence_when_row_model_blank_then_unknown() -> None:
    assert row_independence(JUDGE, "  ") is RowIndependence.UNKNOWN


def test_task_problem_when_task_unknown_then_config_error_naming_valid_tasks() -> None:
    error_type, message = task_problem("nope", judge_model=JUDGE, task_model_map=TASK_MAP) or (None, "")
    assert error_type is JudgeConfigError
    assert "Unknown graded task 'nope'" in message


def test_task_problem_when_task_has_no_model_then_config_error() -> None:
    problem = task_problem("blank", judge_model=JUDGE, task_model_map=TASK_MAP)
    assert problem is not None
    assert problem[0] is JudgeConfigError


def test_task_problem_when_judge_equals_task_model_then_not_independent_error() -> None:
    problem = task_problem("graded", judge_model="vendor-g/model-1", task_model_map=TASK_MAP)
    assert problem is not None
    assert problem[0] is JudgeNotIndependentError


def test_task_problem_when_healthy_then_none() -> None:
    assert task_problem("graded", judge_model=JUDGE, task_model_map=TASK_MAP) is None


def test_config_problem_when_judge_unset_then_not_configured_error_with_env_var_name() -> None:
    problem = config_problem("graded", judge_model="", task_model_map=TASK_MAP)
    assert problem == (JudgeNotConfiguredError, JUDGE_UNSET_MESSAGE)
    assert "LLM_EVAL_JUDGE_MODEL" in JUDGE_UNSET_MESSAGE


def test_config_problem_when_judge_set_then_delegates_to_task_problem() -> None:
    problem = config_problem("nope", judge_model=JUDGE, task_model_map=TASK_MAP)
    assert problem is not None
    assert problem[0] is JudgeConfigError
