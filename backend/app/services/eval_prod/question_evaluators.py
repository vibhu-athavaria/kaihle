"""Evaluators for production task ``question_generation`` (MCQ batches; MLH-T18 slice 5a, D14).

Registers the question-quality suite on the registry: the four deterministic per-question checks
and the judge rubrics R1-R7. Names become ``eval_results.check_name``: checks use their own name,
rubrics their spec id (so a rubric's stored calibration, keyed by spec id and hash, resolves).

R6 has two registered variants (foundational / applied) and the runner applies the one matching the
question's difficulty band: ``understanding_spec(band).id`` names it, and ``developing`` and
``advanced`` share the applied spec. R7 is the ``bank`` variant, the path this task generates.

``grade_open_answer`` is registered by ``grade_evaluators``.

NOT supported (no suite exists, so nothing is registered; the registry reports them unsupported):
``quiz_generation`` (single practice-quiz questions, out of scope here: the R7 quiz variant exists
but is deliberately unregistered), ``question_quality`` (it is itself a judge: auditing it is the
prod-judge meta-evaluation, not these rubrics), ``tutor_chat``, ``lesson_plan``,
``explain_this``, ``concept_guide`` and every other task: no suite exists for them yet (T11-T14).
"""

from app.ai.eval.question_checks import PER_QUESTION_CHECKS
from app.ai.eval.question_rubrics import (
    BLIND_SOLVE_SPEC,
    DISTRACTOR_PLAUSIBILITY_SPEC,
    EXACTLY_ONE_CORRECT_SPEC,
    GRADE_CALIBRATION_SPEC,
    OBJECTIVE_ALIGNMENT_SPEC,
    explanation_spec,
    understanding_spec,
)
from app.ai.eval.rubric_core import RubricSpec
from app.services.eval_prod.grade_evaluators import register_grade_open_answer
from app.services.eval_prod.registry import KIND_DETERMINISTIC, KIND_JUDGE, Evaluator, EvaluatorRegistry

QUESTION_GENERATION_TASK = "question_generation"

QUESTION_RUBRIC_SPECS: tuple[RubricSpec, ...] = (
    BLIND_SOLVE_SPEC,
    EXACTLY_ONE_CORRECT_SPEC,
    DISTRACTOR_PLAUSIBILITY_SPEC,
    OBJECTIVE_ALIGNMENT_SPEC,
    GRADE_CALIBRATION_SPEC,
    understanding_spec("foundational"),
    understanding_spec("developing"),  # the applied variant; "advanced" resolves to the same spec
    explanation_spec("bank"),
)


def register_question_generation(registry: EvaluatorRegistry) -> None:
    for name in PER_QUESTION_CHECKS:
        registry.register(QUESTION_GENERATION_TASK, Evaluator(name, KIND_DETERMINISTIC))
    for spec in QUESTION_RUBRIC_SPECS:
        registry.register(QUESTION_GENERATION_TASK, Evaluator(spec.id, KIND_JUDGE, rubric=spec))


def default_registry() -> EvaluatorRegistry:
    """The production registry: every suite that exists, registered."""
    registry = EvaluatorRegistry()
    register_question_generation(registry)
    register_grade_open_answer(registry)
    return registry
