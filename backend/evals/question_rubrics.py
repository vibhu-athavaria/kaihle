"""MCQ quality rubrics R1-R7 (T10 Step 5) as DeepEval metrics, built on ``evals.rubric_core``.

The DeepEval-free definitions (the ``RubricSpec``s, R6/R7 factories, prompt and decision logic of the
code-scored rubrics) moved to ``app.ai.eval.question_rubrics`` (MLH-T18 slice 5a) so production code
can run them; they are re-exported here so every existing import keeps working. This module keeps
only what needs DeepEval: the ``BaseMetric`` wrappers, which delegate to that logic.

An unusable judge reply is ``verdict=None`` / ``indeterminate=True`` and is never a pass (D8).
Router exceptions propagate. Question content is passed as DATA behind the core's guard line.
"""

import asyncio
from collections.abc import Mapping

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from app.ai.eval.judge_runner import CodeScoredRubric, build_code_scored_prompt
from app.ai.eval.question_rubrics import (
    BLIND_SOLVE,
    BLIND_SOLVE_SPEC,
    DISTRACTOR_PLAUSIBILITY_SPEC,
    EXACTLY_ONE_CORRECT,
    EXACTLY_ONE_CORRECT_SPEC,
    GRADE_CALIBRATION_SPEC,
    OBJECTIVE_ALIGNMENT_SPEC,
    QuestionPath,
    explanation_spec,
    question_case_data,
    understanding_spec,
)
from app.ai.eval.rubric_core import parse_json_object
from evals.judge import RouterJudge
from evals.question_model import EvalQuestion

__all__ = [
    "BLIND_SOLVE_SPEC",
    "DISTRACTOR_PLAUSIBILITY_SPEC",
    "EXACTLY_ONE_CORRECT_SPEC",
    "GRADE_CALIBRATION_SPEC",
    "OBJECTIVE_ALIGNMENT_SPEC",
    "BlindSolveMetric",
    "ExactlyOneCorrectMetric",
    "QuestionPath",
    "explanation_spec",
    "question_case",
    "understanding_spec",
]


def question_case(question: EvalQuestion) -> LLMTestCase:
    """Package a question as rubric DATA. Metadata keys match the ``RubricSpec.params`` names."""
    return LLMTestCase(input=question.question_text, metadata=dict(question_case_data(question)))


class _CodeScoredMetric(BaseMetric):
    """Judge states facts as JSON; the rubric's ``decide`` turns them into a verdict in code (D6)."""

    def __init__(self, rubric: CodeScoredRubric, judge: RouterJudge) -> None:
        self.rubric = rubric
        self.spec = rubric.spec
        self.judge = judge
        self.threshold = 1.0
        self.async_mode = True
        self.verdict: bool | None = None
        self.indeterminate = False

    @property
    def __name__(self) -> str:
        return self.spec.id

    def build_prompt(self, case: Mapping[str, str]) -> str:
        return build_code_scored_prompt(self.rubric, case)

    async def a_measure(self, test_case: LLMTestCase, *args: object, **kwargs: object) -> float:
        case = {str(k): str(v) for k, v in (test_case.metadata or {}).items()}
        reply = await self.judge.a_generate(self.build_prompt(case))
        data, problem = parse_json_object(reply)
        verdict, reason = (None, problem) if data is None else self.rubric.decide(data, case["key"])
        self.verdict = verdict
        self.indeterminate = verdict is None
        self.score = 1.0 if verdict else 0.0
        self.reason = f"indeterminate: {reason}" if verdict is None else reason
        self.success = verdict is True
        return self.score

    def measure(self, test_case: LLMTestCase, *args: object, **kwargs: object) -> float:
        return asyncio.run(self.a_measure(test_case))

    def is_successful(self) -> bool:
        return self.verdict is True


class BlindSolveMetric(_CodeScoredMetric):
    """R1: the judge solves the item without the key or explanation; code compares its answer to the key."""

    def __init__(self, judge: RouterJudge) -> None:
        super().__init__(BLIND_SOLVE, judge)


class ExactlyOneCorrectMetric(_CodeScoredMetric):
    """R2: the judge lists the defensibly correct options; code passes iff that list is exactly the key."""

    def __init__(self, judge: RouterJudge) -> None:
        super().__init__(EXACTLY_ONE_CORRECT, judge)
