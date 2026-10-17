"""Run a rubric against the judge WITHOUT DeepEval (MLH-T18 slice 5a).

Prompt (``build_rubric_prompt``) -> completion -> tolerant parse. The completion function is a
PARAMETER, so tests need no LLM; ``router_completion`` is the production one and goes through
``app.ai.providers.router.complete`` on the ``eval_judge`` task (CONSTITUTION Rule 4).

Verdict semantics: True/False, or None when the reply was unusable. None (indeterminate) is NEVER a
pass. Router exceptions propagate: swallowing one would fabricate a verdict from nothing. Case
content reaches the judge as DATA behind the core's guard line; the residual prompt-injection risk
documented in ``rubric_core`` applies.

``CodeScoredRubric`` covers rubrics whose judge reply is a factual statement that CODE compares with
the answer key (D6), so the judge is never asked "is it right?" directly.
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.ai.eval.judge_config import JUDGE_COMPONENT, JUDGE_MAX_TOKENS, JUDGE_TASK, JUDGE_TEMPERATURE
from app.ai.eval.rubric_core import _GUARD, RubricSpec, build_rubric_prompt, parse_binary_verdict, parse_json_object
from app.ai.providers.router import complete
from app.ai.usage_context import llm_component

Completion = Callable[[str], Awaitable[str]]
Decide = Callable[[Mapping[str, Any], str], tuple[bool | None, str]]


@dataclass(frozen=True)
class RubricOutcome:
    verdict: bool | None  # None = indeterminate, never a pass
    detail: str  # evidence, or why the reply was unusable


@dataclass(frozen=True)
class CodeScoredRubric:
    spec: RubricSpec
    reply_format: str
    decide: Decide  # (judge JSON, answer key) -> (verdict, reason); (None, why) when unusable


def build_code_scored_prompt(rubric: CodeScoredRubric, case: Mapping[str, str]) -> str:
    """Render the judge prompt. Raises ValueError if a declared param is missing from ``case``."""
    missing = [p for p in rubric.spec.params if p not in case]
    if missing:
        raise ValueError(f"case for {rubric.spec.id} lacks declared params: {missing}")
    data = "\n".join(f"[{name}]\n{case[name]}" for name in rubric.spec.params)
    return (
        f"{rubric.spec.instructions}\n\n{_GUARD}\n\n<<<CASE_DATA\n{data}\nCASE_DATA>>>\n\n"
        f"Reply with JSON only, no other text: {rubric.reply_format}"
    )


def router_completion(run_id: str | None = None) -> Completion:
    """Production completion: the ``eval_judge`` router task at temperature 0."""

    async def completion(prompt: str) -> str:
        # component and run_id reach llm_usage_events via structlog contextvars (see usage_context.py).
        with llm_component(JUDGE_COMPONENT, run_id=run_id):
            return await complete(
                task=JUDGE_TASK,
                messages=[{"role": "user", "content": prompt}],
                temperature=JUDGE_TEMPERATURE,
                max_tokens=JUDGE_MAX_TOKENS,
            )

    return completion


async def run_binary_rubric(spec: RubricSpec, case: Mapping[str, str], completion: Completion) -> RubricOutcome:
    verdict, evidence = parse_binary_verdict(await completion(build_rubric_prompt(spec, case)))
    return RubricOutcome(verdict, evidence)


async def run_code_scored_rubric(
    rubric: CodeScoredRubric, case: Mapping[str, str], completion: Completion
) -> RubricOutcome:
    if "key" not in case:
        raise ValueError(f"case for {rubric.spec.id} lacks the answer key")
    data, problem = parse_json_object(await completion(build_code_scored_prompt(rubric, case)))
    verdict, reason = (None, problem) if data is None else rubric.decide(data, case["key"])
    return RubricOutcome(verdict, reason)
