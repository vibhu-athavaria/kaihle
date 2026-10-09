"""Offline tests for the router-backed DeepEval judge. No network, no real LLM, no DB."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.usage_context import current_component
from evals.judge import (
    JudgeNotConfiguredError,
    JudgeNotIndependentError,
    RouterJudge,
    check_judge_independence,
    require_judge_configured,
)

JUDGE_MODEL = "placeholder/judge-model"


def _settings(judge_model: str) -> MagicMock:
    return MagicMock(llm_eval_judge_model=judge_model)


async def test_a_generate_when_called_then_routes_via_eval_judge_task() -> None:
    with patch("evals.judge.complete", new_callable=AsyncMock) as complete:
        complete.return_value = "ok"
        result = await RouterJudge().a_generate("p")

    assert result == "ok"
    assert complete.await_args is not None
    kwargs = complete.await_args.kwargs
    assert kwargs["task"] == "eval_judge"
    assert kwargs["temperature"] == 0.0
    assert kwargs["messages"] == [{"role": "user", "content": "p"}]


async def test_a_generate_when_called_then_runs_inside_eval_component_context() -> None:
    seen: list[str | None] = []

    async def record(**_: object) -> str:
        seen.append(current_component())
        return "ok"

    with patch("evals.judge.complete", new=record):
        await RouterJudge().a_generate("p")

    assert seen == ["eval_harness"]


def test_generate_when_no_running_loop_then_returns_completion_text() -> None:
    with patch("evals.judge.complete", new_callable=AsyncMock) as complete:
        complete.return_value = "sync-ok"
        assert RouterJudge().generate("p") == "sync-ok"


def test_generate_when_called_inside_running_loop_then_raises_clear_error() -> None:
    async def call_sync_inside_loop() -> None:
        RouterJudge().generate("p")

    with pytest.raises(RuntimeError, match="a_generate"):
        asyncio.run(call_sync_inside_loop())


async def test_a_generate_when_router_raises_then_exception_propagates() -> None:
    with patch("evals.judge.complete", new_callable=AsyncMock) as complete:
        complete.side_effect = RuntimeError("provider down")
        with pytest.raises(RuntimeError, match="provider down"):
            await RouterJudge().a_generate("p")


def test_get_model_name_when_called_then_returns_router_label_not_model_string() -> None:
    assert RouterJudge().get_model_name() == "kaihle-router/eval_judge"


def test_require_judge_configured_when_model_empty_then_raises_naming_env_var() -> None:
    with patch("evals.judge.settings", _settings("")):
        with pytest.raises(JudgeNotConfiguredError, match="LLM_EVAL_JUDGE_MODEL"):
            require_judge_configured()


def test_require_judge_configured_when_model_set_then_returns_none() -> None:
    with patch("evals.judge.settings", _settings(JUDGE_MODEL)):
        require_judge_configured()


def test_check_judge_independence_when_same_model_string_then_raises() -> None:
    with (
        patch("evals.judge.settings", _settings(JUDGE_MODEL)),
        patch("evals.judge.TASK_MODEL_MAP", {"graded_task": JUDGE_MODEL}),
    ):
        with pytest.raises(JudgeNotIndependentError, match="graded_task"):
            check_judge_independence("graded_task")


def test_check_judge_independence_when_same_vendor_then_logs_warning() -> None:
    with (
        patch("evals.judge.settings", _settings("openrouter/vendor-a/judge-model")),
        patch("evals.judge.TASK_MODEL_MAP", {"graded_task": "vendor-a/other-model"}),
        patch("evals.judge.logger") as logger,
    ):
        check_judge_independence("graded_task")

    logger.warning.assert_called_once()
    assert logger.warning.call_args.args[0] == "eval_judge_same_vendor"


def test_check_judge_independence_when_different_vendor_then_passes_silently() -> None:
    with (
        patch("evals.judge.settings", _settings("vendor-a/judge-model")),
        patch("evals.judge.TASK_MODEL_MAP", {"graded_task": "vendor-b/graded-model"}),
        patch("evals.judge.logger") as logger,
    ):
        check_judge_independence("graded_task")

    logger.warning.assert_not_called()


def test_conftest_when_loaded_then_deepeval_telemetry_opt_out_is_forced() -> None:
    # evals/conftest.py is imported by pytest before this module, so the forced value
    # must already be in the environment regardless of what the shell exported.
    assert os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] == "YES"
