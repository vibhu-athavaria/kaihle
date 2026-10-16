"""app.ai.eval must stay importable in the production image, where the DeepEval `eval` group is absent."""

import subprocess
import sys
from pathlib import Path

import pytest

from app.ai.eval import judge_config
from app.ai.eval.rubric_core import RubricSpec, build_rubric_prompt

_BACKEND = Path(__file__).resolve().parents[3]
_MODULES = [
    "app.ai.eval",
    "app.ai.eval.thresholds",
    "app.ai.eval.calibration",
    "app.ai.eval.judge_config",
    "app.ai.eval.rubric_core",
    "app.ai.eval.judge_guards",
    "app.services.eval_prod.budget",
    "app.services.eval_prod.registry",
]


@pytest.mark.parametrize("module", _MODULES)
def test_eval_core_module_when_imported_then_deepeval_is_not_loaded(module: str) -> None:
    code = f"import sys, {module}; sys.exit(1 if 'deepeval' in sys.modules or 'evals' in sys.modules else 0)"
    result = subprocess.run([sys.executable, "-c", code], cwd=_BACKEND, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_judge_config_when_imported_then_errors_are_runtime_errors() -> None:
    for error in (
        judge_config.JudgeNotConfiguredError,
        judge_config.JudgeNotIndependentError,
        judge_config.JudgeConfigError,
    ):
        assert issubclass(error, RuntimeError)


def test_build_rubric_prompt_when_param_missing_then_raises_value_error() -> None:
    spec = RubricSpec("R1", "Is it ok?", "Be strict.", ("a",))
    with pytest.raises(ValueError, match="lacks declared params"):
        build_rubric_prompt(spec, {})
