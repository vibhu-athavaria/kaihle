"""Suite-agnostic binary rubric core (T10 Step 5; T11-T14, T16, T17 build their rubrics on this).

A ``RubricSpec`` is the auditable text of one yes/no question. ``BinaryRubricMetric`` is a DeepEval
``BaseMetric`` that asks the router-backed judge for ``{"pass": bool, "evidence": str}`` (SD-5).

Case content (``LLMTestCase.metadata``, keyed by ``spec.params``) is injected as DATA behind a guard
line. This is a mitigation, not a guarantee: a sufficiently adversarial case can still try to steer
the judge (residual prompt-injection risk, documented here and in the master plan).

Verdict semantics: ``verdict`` is True/False, or None when the reply was unparseable or lacked a
boolean ``pass`` field. None sets ``indeterminate`` and is NEVER a pass. Judge/router exceptions
propagate: a swallowed failure would fabricate a score from nothing.
"""

import asyncio
from collections.abc import Mapping

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from app.ai.eval.rubric_core import _GUARD, RubricSpec, build_rubric_prompt, parse_binary_verdict, parse_json_object
from evals.judge import RouterJudge

# RubricSpec and the parsers live in app.ai.eval.rubric_core (DeepEval-free, importable from production);
# they are re-exported here (including the private `_GUARD` that evals.question_rubrics
# imports) so every existing import keeps working.
__all__ = ["_GUARD", "BinaryRubricMetric", "RubricSpec", "parse_binary_verdict", "parse_json_object"]


class BinaryRubricMetric(BaseMetric):
    """Binary, evidence-bearing rubric metric. Case fields come from ``test_case.metadata``."""

    def __init__(self, spec: RubricSpec, judge: RouterJudge) -> None:
        self.spec = spec
        self.judge = judge
        self.threshold = 1.0
        self.async_mode = True
        self.verdict: bool | None = None
        self.indeterminate = False
        self.evidence = ""

    @property
    def __name__(self) -> str:
        return self.spec.id

    def build_prompt(self, case: Mapping[str, str]) -> str:
        """Render the judge prompt. Raises ValueError if a declared param is missing from ``case``."""
        return build_rubric_prompt(self.spec, case)

    async def a_measure(self, test_case: LLMTestCase, *args: object, **kwargs: object) -> float:
        case = {str(k): str(v) for k, v in (test_case.metadata or {}).items()}
        reply = await self.judge.a_generate(self.build_prompt(case))
        verdict, evidence = parse_binary_verdict(reply)
        self.verdict = verdict
        self.indeterminate = verdict is None
        self.evidence = evidence
        self.score = 1.0 if verdict else 0.0  # indeterminate scores 0.0 but is_successful() stays False
        self.reason = f"indeterminate: {evidence}" if verdict is None else evidence
        self.success = verdict is True
        return self.score

    def measure(self, test_case: LLMTestCase, *args: object, **kwargs: object) -> float:
        """Sync wrapper; ``asyncio.run`` refuses inside a running loop, which is the intended guard."""
        return asyncio.run(self.a_measure(test_case))

    def is_successful(self) -> bool:
        return self.verdict is True
