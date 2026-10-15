"""DeepEval-free judge constants and error types (the guards themselves live in ``evals.judge``).

Importable from production code: the judge task name, the usage-event component and the three
configuration errors. ``evals.judge`` re-exports every name, so the classes are identical objects.
"""

JUDGE_TASK = "eval_judge"
JUDGE_COMPONENT = "eval_harness"
JUDGE_TEMPERATURE = 0.0
JUDGE_MAX_TOKENS = 1000
# A label, deliberately not a model string: model names never appear in reports or code (SD-2).
JUDGE_MODEL_LABEL = "kaihle-router/eval_judge"


class JudgeNotConfiguredError(RuntimeError):
    """The judge model env var is empty."""


class JudgeNotIndependentError(RuntimeError):
    """The judge would grade its own model's output."""


class JudgeConfigError(RuntimeError):
    """The graded task is unknown or has no model configured, so independence cannot be checked."""
