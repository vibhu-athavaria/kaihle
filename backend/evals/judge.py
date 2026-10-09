"""Router-backed LLM judge for the DeepEval harness.

Every judge call goes through ``app.ai.providers.router.complete`` on the ``eval_judge`` task
(CONSTITUTION Rule 4), so the model is env-driven and cost lands in ``llm_usage_events``.
DeepEval's own provider clients are never used.
"""

import asyncio

import structlog
from deepeval.models import DeepEvalBaseLLM

from app.ai.providers.router import TASK_MODEL_MAP, complete
from app.ai.usage_context import llm_component
from app.core.config import settings

logger = structlog.get_logger()

JUDGE_TASK = "eval_judge"
JUDGE_COMPONENT = "eval_harness"
JUDGE_TEMPERATURE = 0.0
JUDGE_MAX_TOKENS = 1000
# A label, deliberately not a model string: model names never appear in reports or code (SD-2).
JUDGE_MODEL_LABEL = "kaihle-router/eval_judge"
_OPENROUTER_PREFIX = "openrouter/"


class JudgeNotConfiguredError(RuntimeError):
    """The judge model env var is empty."""


class JudgeNotIndependentError(RuntimeError):
    """The judge would grade its own model's output."""


class RouterJudge(DeepEvalBaseLLM):
    """DeepEval judge that calls the ``eval_judge`` router task at temperature 0.

    Router exceptions propagate: a swallowed judge failure would yield a plausible-looking
    score from nothing.
    """

    def __init__(self, run_id: str | None = None) -> None:
        self.run_id = run_id
        super().__init__()

    def load_model(self) -> "RouterJudge":
        return self

    async def a_generate(self, prompt: str, *args: object, **kwargs: object) -> str:
        with llm_component(JUDGE_COMPONENT, run_id=self.run_id):
            return await complete(
                task=JUDGE_TASK,
                messages=[{"role": "user", "content": prompt}],
                temperature=JUDGE_TEMPERATURE,
                max_tokens=JUDGE_MAX_TOKENS,
            )

    def generate(self, prompt: str, *args: object, **kwargs: object) -> str:
        """Sync fallback via ``asyncio.run``; the harness is async-first.

        Not a Celery task, so the ``new_event_loop`` rule does not apply. Refuses to run inside
        a live loop, where ``asyncio.run`` would fail or deadlock.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.a_generate(prompt))
        raise RuntimeError("RouterJudge.generate() cannot run inside a running event loop; await a_generate() instead.")

    def get_model_name(self, *args: object, **kwargs: object) -> str:
        return JUDGE_MODEL_LABEL


def require_judge_configured() -> None:
    """Fail fast, naming the env var, when no judge model is configured."""
    if not settings.llm_eval_judge_model:
        raise JudgeNotConfiguredError("LLM_EVAL_JUDGE_MODEL is not set; the eval harness cannot run without a judge.")


def _vendor_token(model: str) -> str | None:
    """First path segment after an optional ``openrouter/`` prefix, or None if there is no slash."""
    stripped = model.removeprefix(_OPENROUTER_PREFIX)
    if "/" not in stripped:
        return None
    return stripped.split("/", 1)[0].lower()


def check_judge_independence(task: str) -> None:
    """Refuse to judge a task whose model is the judge; warn when the vendor matches.

    Identical model strings raise ``JudgeNotIndependentError`` (self-preference bias). The
    vendor comparison is a HEURISTIC: it only compares the leading path segment of the model
    string, so aggregators, self-hosted endpoints and bare model names can hide or fake a
    shared vendor. A warning is advisory, not proof either way.
    """
    judge_model = settings.llm_eval_judge_model
    graded_model = TASK_MODEL_MAP[task]
    if judge_model == graded_model:
        raise JudgeNotIndependentError(
            f"Judge model is identical to the model under test for task {task!r}; "
            "set LLM_EVAL_JUDGE_MODEL to a different model."
        )
    judge_vendor = _vendor_token(judge_model)
    if judge_vendor is not None and judge_vendor == _vendor_token(graded_model):
        logger.warning("eval_judge_same_vendor", task=task, vendor=judge_vendor)
