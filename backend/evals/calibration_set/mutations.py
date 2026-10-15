"""Deterministic defect mutations (T10 Step 6). Pure: each returns a NEW question and never edits its input.

Every mutation returns a ``MutationRecord`` mapping the defect onto criterion ids: deterministic
checks by their ``CheckResult.name`` and judge rubrics by their ``RubricSpec.id`` (R6 and R7 use the
variant ids, so ``R6_understanding_not_recall_*`` follows the question's band and both
``R7_explanation_quality_*`` variants are listed). ``must_pass`` is every other criterion EXCEPT the
knock-on ones in ``_KNOCK_ON``, whose verdict is genuinely ambiguous for that defect (for example a
wrong key leaves an explanation that now argues for a distractor). Ambiguous criteria are in neither list.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, replace

from evals.calibration_set.math_templates import equivalent_form, option_value
from evals.question_model import OPTION_KEYS, EvalQuestion
from evals.question_rubrics import (
    BLIND_SOLVE_SPEC,
    DISTRACTOR_PLAUSIBILITY_SPEC,
    EXACTLY_ONE_CORRECT_SPEC,
    GRADE_CALIBRATION_SPEC,
    OBJECTIVE_ALIGNMENT_SPEC,
    explanation_spec,
    understanding_spec,
)

DETERMINISTIC_CHECKS = ("unique_options", "self_contained", "rendering_safe", "no_compliance_language")
_DIAGRAM_PREFIX = "Refer to the diagram below. "
_MAX_GRADE = 12
_GRADE_SHIFT = 3
_ABSURD_FACTOR = 100
_ABSURD_OFFSET = 997
_UNRELATED_OBJECTIVES = (
    "Describe the stages of the water cycle",
    "Identify the main features of a persuasive text",
    "Explain how plants make food by photosynthesis",
    "Compare causes of a historical conflict",
)


@dataclass(frozen=True)
class MutationRecord:
    defect: str | None  # None marks a clean question
    must_fail: tuple[str, ...]
    must_pass: tuple[str, ...]


def all_criteria(q: EvalQuestion) -> tuple[str, ...]:
    return (
        *DETERMINISTIC_CHECKS,
        BLIND_SOLVE_SPEC.id,
        EXACTLY_ONE_CORRECT_SPEC.id,
        DISTRACTOR_PLAUSIBILITY_SPEC.id,
        OBJECTIVE_ALIGNMENT_SPEC.id,
        GRADE_CALIBRATION_SPEC.id,
        understanding_spec(q.difficulty_band).id,
        explanation_spec("bank").id,
        explanation_spec("quiz").id,
    )


_R7 = (explanation_spec("bank").id, explanation_spec("quiz").id)
_KNOCK_ON: dict[str, tuple[str, ...]] = {
    "wrong_key": _R7,
    "two_correct": (BLIND_SOLVE_SPEC.id, DISTRACTOR_PLAUSIBILITY_SPEC.id),
    "diagram_reference": (BLIND_SOLVE_SPEC.id, EXACTLY_ONE_CORRECT_SPEC.id),
}


def clean_record(q: EvalQuestion) -> MutationRecord:
    return MutationRecord(None, (), all_criteria(q))


def _record(defect: str, q: EvalQuestion, must_fail: tuple[str, ...]) -> MutationRecord:
    excluded = {*must_fail, *_KNOCK_ON.get(defect, ())}
    return MutationRecord(defect, must_fail, tuple(c for c in all_criteria(q) if c not in excluded))


def _distractor_keys(q: EvalQuestion) -> list[str]:
    return [k for k in OPTION_KEYS if k != q.correct_answer]


def _next_key(q: EvalQuestion) -> str:
    return OPTION_KEYS[(OPTION_KEYS.index(q.correct_answer) + 1) % len(OPTION_KEYS)]


def wrong_key(q: EvalQuestion) -> tuple[EvalQuestion, MutationRecord]:
    out = replace(q, correct_answer=_next_key(q))
    return out, _record("wrong_key", out, (BLIND_SOLVE_SPEC.id, EXACTLY_ONE_CORRECT_SPEC.id))


def two_correct(q: EvalQuestion) -> tuple[EvalQuestion, MutationRecord]:
    options = dict(q.options)
    options[_distractor_keys(q)[0]] = equivalent_form(q.options[q.correct_answer])
    out = replace(q, options=options)
    return out, _record("two_correct", out, (EXACTLY_ONE_CORRECT_SPEC.id,))


def duplicate_option(q: EvalQuestion) -> tuple[EvalQuestion, MutationRecord]:
    first, second = _distractor_keys(q)[:2]
    out = replace(q, options={**q.options, second: q.options[first]})
    return out, _record("duplicate_option", out, ("unique_options", DISTRACTOR_PLAUSIBILITY_SPEC.id))


def absurd_distractor(q: EvalQuestion) -> tuple[EvalQuestion, MutationRecord]:
    biggest = max(abs(option_value(v)) for v in q.options.values())
    absurd = -(int(biggest) * _ABSURD_FACTOR + _ABSURD_OFFSET)
    out = replace(q, options={**q.options, _distractor_keys(q)[-1]: str(absurd)})
    return out, _record("absurd_distractor", out, (DISTRACTOR_PLAUSIBILITY_SPEC.id,))


def diagram_reference(q: EvalQuestion) -> tuple[EvalQuestion, MutationRecord]:
    out = replace(q, question_text=_DIAGRAM_PREFIX + q.question_text)
    return out, _record("diagram_reference", out, ("self_contained",))


def latex_markup(q: EvalQuestion) -> tuple[EvalQuestion, MutationRecord]:
    out = replace(q, question_text=re.sub(r"\d+", lambda m: f"${m.group(0)}$", q.question_text))
    return out, _record("latex_markup", out, ("rendering_safe",))


def off_objective(q: EvalQuestion) -> tuple[EvalQuestion, MutationRecord]:
    objective = _UNRELATED_OBJECTIVES[sum(map(ord, q.id)) % len(_UNRELATED_OBJECTIVES)]
    out = replace(q, learning_objective=objective)
    return out, _record("off_objective", out, (OBJECTIVE_ALIGNMENT_SPEC.id,))


def grade_mismatch(q: EvalQuestion) -> tuple[EvalQuestion, MutationRecord]:
    grade = q.grade_level + _GRADE_SHIFT if q.grade_level + _GRADE_SHIFT <= _MAX_GRADE else q.grade_level - _GRADE_SHIFT
    out = replace(q, grade_level=grade)
    return out, _record("grade_mismatch", out, (GRADE_CALIBRATION_SPEC.id,))


def explanation_contradicts_key(q: EvalQuestion) -> tuple[EvalQuestion, MutationRecord]:
    other = _next_key(q)
    out = replace(q, explanation=f"The answer is option {other}: {q.options[other]}. This is the correct choice.")
    return out, _record("explanation_contradicts_key", out, _R7)


MUTATIONS: dict[str, Callable[[EvalQuestion], tuple[EvalQuestion, MutationRecord]]] = {
    fn.__name__: fn
    for fn in (
        wrong_key,
        two_correct,
        duplicate_option,
        absurd_distractor,
        diagram_reference,
        latex_markup,
        off_objective,
        grade_mismatch,
        explanation_contradicts_key,
    )
}
DEFECTS = tuple(MUTATIONS)
