"""Unit tests for the DeepEval-free question-quality suite in ``app/ai/eval`` and its registration (MLH-T18 slice 5a).

No LLM and no DeepEval: the completion function is a parameter. The golden hashes are the same ones
pinned in ``evals/tests/test_question_eval_surface.py``; both must hold so stored calibration files
stay valid.
"""

import hashlib
from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.eval import judge_runner
from app.ai.eval.judge_runner import router_completion
from app.ai.eval.question_checks import (
    PER_QUESTION_CHECKS,
    check_no_compliance_language,
    check_rendering_safe,
    check_self_contained,
    check_unique_options,
)
from app.ai.eval.question_model import EvalQuestion
from app.ai.eval.question_rubrics import (
    BLIND_SOLVE_SPEC,
    CODE_SCORED_RUBRICS,
    DISTRACTOR_PLAUSIBILITY_SPEC,
    EXACTLY_ONE_CORRECT_SPEC,
    explanation_spec,
    question_case_data,
    run_question_rubric,
    understanding_spec,
)
from app.services.eval_prod.question_evaluators import (
    QUESTION_GENERATION_TASK,
    QUESTION_RUBRIC_SPECS,
    default_registry,
)
from app.services.eval_prod.registry import EvaluatorRegistry

_SPEC_HASHES = {
    "R1_key_correctness": "9a3a35f5e65af6889ed99a5cdf17667621da1303ee539821e902bc4bac4d1eee",
    "R2_exactly_one_correct": "8e6801d65d0ce2e416aadcab6c15dccf868b77390852d72368291af43186ff79",
    "R3_distractor_plausibility": "b91728740a9cff7c2587c77f72ed15ad73f1c233f9894e0a75ebadd4de60ef09",
    "R6_understanding_not_recall_foundational": "fd045e901e74daa35c927a3d4fcd9926a22053f5a60dcb47d285d3cbc5681da2",
    "R6_understanding_not_recall_applied": "f875249072e03c6f94a8b3567686e06a02e4b6863ac50e6585c9378ecc12c85b",
    "R7_explanation_quality_bank": "394bf65f90d0ed2338446a34207778a7fc10588e4e2fa110c11361a4cdad9e15",
    "R7_explanation_quality_quiz": "0bea876f3d1a3cd93284b7420babcde660bd686bcdba3f98784957fc12f01d35",
}
_R3_PROMPT_HASH = "6b67ca2631a74f21195da6b2d6e3fd754873eb55aaa77312f5f60c9518418d64"
_R1_PROMPT_HASH = "8068ee22165b90ac52d82b3685590518c351959dc35f801f1be289c10398df2f"


def _question() -> EvalQuestion:
    return EvalQuestion(
        id="q1",
        subject_code="MATH",
        grade_level=7,
        subtopic_name="F",
        learning_objective="Add fractions",
        difficulty_band="developing",
        difficulty_level=None,
        question_text="What is 1/2 + 1/3?",
        options={"A": "2/5", "B": "5/6", "C": "1/6", "D": "2/6"},
        correct_answer="B",
        explanation="Because 3/6 + 2/6 = 5/6.",
    )


class _Recorder:
    """A completion that records prompts and returns a canned reply."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    async def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.reply


def test_rubric_specs_when_hashed_in_app_module_then_match_golden_values() -> None:
    specs = [
        BLIND_SOLVE_SPEC,
        EXACTLY_ONE_CORRECT_SPEC,
        DISTRACTOR_PLAUSIBILITY_SPEC,
        understanding_spec("foundational"),
        understanding_spec("advanced"),
        explanation_spec("bank"),
        explanation_spec("quiz"),
    ]
    assert {spec.id: spec.text_hash for spec in specs} == _SPEC_HASHES


@pytest.mark.asyncio
async def test_run_question_rubric_when_binary_pass_then_verdict_true_and_prompt_is_golden() -> None:
    completion = _Recorder('{"pass": true, "evidence": "fine"}')
    outcome = await run_question_rubric(DISTRACTOR_PLAUSIBILITY_SPEC, _question(), completion)
    assert (outcome.verdict, outcome.detail) == (True, "fine")
    assert hashlib.sha256(completion.prompts[0].encode()).hexdigest() == _R3_PROMPT_HASH


@pytest.mark.asyncio
async def test_run_question_rubric_when_binary_fail_then_verdict_false() -> None:
    outcome = await run_question_rubric(
        DISTRACTOR_PLAUSIBILITY_SPEC, _question(), _Recorder('{"pass": false, "evidence": "absurd"}')
    )
    assert (outcome.verdict, outcome.detail) == (False, "absurd")


@pytest.mark.asyncio
@pytest.mark.parametrize("reply", ["not json", '{"pass": "yes"}', "[]", ""])
async def test_run_question_rubric_when_binary_reply_unusable_then_indeterminate_not_pass(reply: str) -> None:
    outcome = await run_question_rubric(DISTRACTOR_PLAUSIBILITY_SPEC, _question(), _Recorder(reply))
    assert outcome.verdict is None


@pytest.mark.asyncio
async def test_run_question_rubric_when_blind_solve_matches_key_then_pass_and_prompt_is_golden() -> None:
    completion = _Recorder('{"answer": "b", "working": "w"}')
    outcome = await run_question_rubric(BLIND_SOLVE_SPEC, _question(), completion)
    assert (outcome.verdict, outcome.detail) == (True, "solver chose B, matching the key")
    assert hashlib.sha256(completion.prompts[0].encode()).hexdigest() == _R1_PROMPT_HASH
    assert "5/6" in completion.prompts[0]  # the options are shown ...
    assert "Because 3/6" not in completion.prompts[0]  # ... the explanation never is
    assert "[key]" not in completion.prompts[0]


@pytest.mark.asyncio
async def test_run_question_rubric_when_blind_solve_differs_from_key_then_fail() -> None:
    outcome = await run_question_rubric(BLIND_SOLVE_SPEC, _question(), _Recorder('{"answer": "A"}'))
    assert (outcome.verdict, outcome.detail) == (False, "solver chose A but the key is B")


@pytest.mark.asyncio
@pytest.mark.parametrize("reply", ['{"answer": "Z"}', "nope", '{"answer": 3}'])
async def test_run_question_rubric_when_blind_solve_reply_unusable_then_indeterminate_not_pass(reply: str) -> None:
    outcome = await run_question_rubric(BLIND_SOLVE_SPEC, _question(), _Recorder(reply))
    assert outcome.verdict is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reply", "verdict"),
    [
        ('{"correct_options": ["B"], "evidence": "e"}', True),
        ('{"correct_options": ["A", "b"], "evidence": "e"}', False),
        ('{"correct_options": []}', False),
        ('{"correct_options": "B"}', None),
        ('{"correct_options": ["Q"]}', None),
    ],
)
async def test_run_question_rubric_when_exactly_one_correct_reply_then_decided_in_code(
    reply: str, verdict: bool | None
) -> None:
    outcome = await run_question_rubric(EXACTLY_ONE_CORRECT_SPEC, _question(), _Recorder(reply))
    assert outcome.verdict is verdict


@pytest.mark.asyncio
async def test_run_question_rubric_when_completion_raises_then_error_propagates() -> None:
    failing = AsyncMock(side_effect=RuntimeError("router down"))
    with pytest.raises(RuntimeError, match="router down"):
        await run_question_rubric(DISTRACTOR_PLAUSIBILITY_SPEC, _question(), failing)


@pytest.mark.asyncio
async def test_run_code_scored_rubric_when_case_lacks_key_then_raises_value_error() -> None:
    case = {k: v for k, v in question_case_data(_question()).items() if k != "key"}
    with pytest.raises(ValueError, match="lacks the answer key"):
        await judge_runner.run_code_scored_rubric(CODE_SCORED_RUBRICS[BLIND_SOLVE_SPEC.id], case, _Recorder("{}"))


@pytest.mark.asyncio
async def test_router_completion_when_called_then_uses_eval_judge_task_at_temperature_zero() -> None:
    with patch("app.ai.eval.judge_runner.complete", new=AsyncMock(return_value="reply")) as mocked:
        reply = await router_completion("run-1")("the prompt")
    assert reply == "reply"
    assert mocked.await_args is not None
    kwargs = mocked.await_args.kwargs
    assert kwargs["task"] == "eval_judge"
    assert kwargs["temperature"] == 0.0
    assert kwargs["messages"] == [{"role": "user", "content": "the prompt"}]


def test_deterministic_checks_when_question_defective_then_each_check_fails_with_its_name() -> None:
    bad = replace(
        _question(),
        question_text="Refer to the diagram: what is $x^2$ for Cambridge compliant work?",
        options={"A": "same", "B": "Same ", "C": "c", "D": "d"},
    )
    assert [fn(bad).passed for fn in PER_QUESTION_CHECKS.values()] == [False, False, False, False]
    assert check_unique_options(bad).detail == "duplicate options: A,B"
    assert check_self_contained(bad).name == "self_contained"
    assert check_rendering_safe(bad).detail == "question_text contains '$x^2$'"
    assert check_no_compliance_language(bad).detail == "banned phrases: Cambridge compliant"


def test_per_question_checks_when_listed_then_names_match_their_results() -> None:
    q = _question()
    assert {name: fn(q).name for name, fn in PER_QUESTION_CHECKS.items()} == {n: n for n in PER_QUESTION_CHECKS}


def test_default_registry_when_built_then_question_generation_has_checks_and_all_rubrics() -> None:
    registry = default_registry()
    plan = registry.plan_for(QUESTION_GENERATION_TASK, include_indicative=False, status_of=lambda spec: "CALIBRATED")
    names = [s.evaluator.name for s in plan.selected]
    assert registry.supports(QUESTION_GENERATION_TASK)
    assert names[:4] == list(PER_QUESTION_CHECKS)
    assert names[4:] == [spec.id for spec in QUESTION_RUBRIC_SPECS]
    assert "R7_explanation_quality_quiz" not in names


def test_default_registry_when_rubric_not_calibrated_then_it_is_excluded_but_checks_still_run() -> None:
    plan = default_registry().plan_for(QUESTION_GENERATION_TASK, include_indicative=True, status_of=lambda s: "STALE")
    assert [s.evaluator.name for s in plan.selected] == list(PER_QUESTION_CHECKS)
    assert len(plan.excluded) == len(QUESTION_RUBRIC_SPECS)


@pytest.mark.parametrize("task", ["quiz_generation", "question_quality", "tutor_chat", "lesson_plan", "explain_this"])
def test_default_registry_when_task_has_no_suite_then_unsupported(task: str) -> None:
    registry = default_registry()
    assert not registry.supports(task)
    assert not registry.plan_for(task, include_indicative=True, status_of=lambda s: "CALIBRATED").supported


def test_registry_when_new_then_still_empty() -> None:
    assert not EvaluatorRegistry().supports(QUESTION_GENERATION_TASK)
