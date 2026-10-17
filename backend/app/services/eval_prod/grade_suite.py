"""`TaskSuite` for production task ``grade_open_answer`` (MLH-T18 slice 5c).

Wires the pure pieces in ``grade_evaluators`` into the runner's seam. The rows carry STUDENT-TYPED text:

* Deterministic checks read the STORED reply only (``run_grade_checks`` needs nothing else), so they
  never touch the prompt, where the student's answer lives.
* A judge rubric needs the question, answer, grade and feedback, so when (and only when) one will run the
  prompt and the reply are both SCRUBBED first and the case is built from the scrubbed copies. If either
  scrub fails the row is skipped (`ScrubFailedError`) and no case exists to send.
* A prompt or reply that cannot be parsed reliably makes the row unsupported (reasons
  ``prompt_unparseable`` / ``reply_unparseable``); a missing prompt counts as unparseable.

Whether a rubric runs at all is the registry's decision (G1/G2 have no calibration today, so they do
not); ``rubric_applies`` only narrows per row (G2: partial/incorrect grades).
"""

from app.ai.eval.judge_runner import Completion, run_binary_rubric
from app.ai.eval.rubric_core import RubricSpec
from app.services.eval_prod.grade_evaluators import (
    REASON_PROMPT_UNPARSEABLE,
    GradeCase,
    UnsupportedGradeRow,
    build_grade_case,
    rubric_applies,
    run_grade_checks,
)
from app.services.eval_prod.sampler import SampledEvent
from app.services.eval_prod.scrub import scrub_text
from app.services.eval_prod.task_suite import PreparedRow, ScrubContext, TaskSuite, UnsupportedRow


def _prepare(
    event: SampledEvent, seed: str, scrub: ScrubContext | None
) -> PreparedRow[str, GradeCase] | UnsupportedRow:
    if scrub is None:
        return PreparedRow(stored=event.response_text, scrubbed=None)
    if event.prompt_text is None:
        return UnsupportedRow(REASON_PROMPT_UNPARSEABLE)
    prompt = scrub_text(event.prompt_text, person_names=scrub.person_names, school_name=scrub.school_name)
    reply = scrub_text(event.response_text, person_names=scrub.person_names, school_name=scrub.school_name)
    case = build_grade_case(prompt, reply)
    if isinstance(case, UnsupportedGradeRow):
        return UnsupportedRow(case.reason)
    return PreparedRow(stored=event.response_text, scrubbed=case)


async def _run_rubric(spec: RubricSpec, case: GradeCase, completion: Completion) -> bool | None:
    return (await run_binary_rubric(spec, case.as_rubric_case(), completion)).verdict


def _deterministic(name: str, reply: str) -> bool | None:
    """One check's verdict on the stored reply; None when it is not computable (see `run_grade_checks`:
    an unparseable reply yields only the parse failure, the other checks would be invented)."""
    return {result.name: result.passed for result in run_grade_checks(reply)}.get(name)


def _applies(spec: RubricSpec, case: GradeCase) -> bool:
    return rubric_applies(spec.id, case)


GRADE_SUITE: TaskSuite[str, GradeCase] = TaskSuite(
    prepare=_prepare,
    deterministic=_deterministic,
    rubric_applies=_applies,
    run_rubric=_run_rubric,
)
