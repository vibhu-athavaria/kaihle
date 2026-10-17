"""Evaluators for production task ``grade_open_answer`` (MLH-T18 slice 5c, D14).

Student-facing and high stakes, and it carries STUDENT-TYPED text (``TASKS_WITH_STUDENT_TEXT`` already
flags it, so enabling it needs the admin's acknowledgement). Everything here is pure: no I/O, no
scrubbing (callers pass already-scrubbed stored text), no logging of text.

Interface for the runner (wiring is a follow-up):

* ``build_grade_case(prompt_text, response_text)`` -> ``GradeCase`` or ``UnsupportedGradeRow`` (counted,
  never guessed). ``GradeCase.as_rubric_case()`` is the mapping ``run_binary_rubric`` takes.
* ``rubric_applies(spec_id, case)``: G2 (no-reveal) applies to partial/incorrect only.
* ``run_grade_checks(response_text)`` -> the deterministic ``CheckResult`` list; needs only the reply.

Deterministic checks use the PRODUCTION parser (``parse_grade_response``), so "does not parse" means
exactly what the product experienced (it showed canned fallback feedback). Known limit of that parser: a
reply whose ``grade`` key is absent defaults to ``incorrect`` and is indistinguishable from a real one.

Rubrics G1/G2 have NO stored calibration, so the registry reports them MISSING and does not run them
until a labelled grade set has been scored (then INDICATIVE: only with the include-indicative flag,
labelled indicative). Registering them does not make them run.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.ai.eval.grade_rubrics import (
    CONSTRUCTIVE_SPEC,
    GRADE_RUBRIC_SPECS,
    NO_REVEAL_SPEC,
    reveal_rubric_applies,
)
from app.ai.eval.question_checks import CheckResult, find_banned_phrases
from app.services.eval_prod.registry import KIND_DETERMINISTIC, KIND_JUDGE, Evaluator, EvaluatorRegistry
from app.services.mini_course_service import _GRADE_FALLBACK_FEEDBACK, GRADE_MAX_TOKENS, parse_grade_response

GRADE_TASK = "grade_open_answer"

# GRADE_MAX_TOKENS caps the reply at 200 tokens; ~4 characters per token bounds a reply that was not cut off.
MAX_FEEDBACK_CHARS = GRADE_MAX_TOKENS * 4

REASON_PROMPT_UNPARSEABLE = "prompt_unparseable"
REASON_REPLY_UNPARSEABLE = "reply_unparseable"

# Delimiters of app/ai/prompts/grade_open_answer.jinja2. Tests render the REAL template, so drift fails there.
_QUESTION_MARK = "## Question Asked\n"
_ANSWER_MARK = "\n\n## Student's Answer\n"
_TAIL_MARK = "\n\n## Your Task\nEvaluate the student's answer and respond with a JSON object only"


@dataclass(frozen=True)
class GradeCase:
    question: str
    student_answer: str
    grade: str
    feedback: str

    def as_rubric_case(self) -> dict[str, str]:
        return {
            "question": self.question,
            "student_answer": self.student_answer,
            "assigned_grade": self.grade,
            "feedback": self.feedback,
        }


@dataclass(frozen=True)
class UnsupportedGradeRow:
    reason: str  # REASON_*; the runner counts these


def _check_grade_reply_parses(reply: str) -> CheckResult:
    parsed = parse_grade_response(reply)
    return CheckResult(
        "grade_reply_parses", not parsed.parse_error, "reply is not a JSON object" if parsed.parse_error else ""
    )


def _check_grade_value_recognised(reply: str) -> CheckResult:
    recognised = parse_grade_response(reply).grade_recognised
    return CheckResult(
        "grade_value_recognised", recognised, "" if recognised else "grade is not correct/partial/incorrect"
    )


def _check_feedback_present(reply: str) -> CheckResult:
    feedback = parse_grade_response(reply).feedback.strip()
    ok = bool(feedback) and feedback != _GRADE_FALLBACK_FEEDBACK
    return CheckResult("feedback_present", ok, "" if ok else "feedback is blank or the production fallback text")


def _check_feedback_length_bounded(reply: str) -> CheckResult:
    length = len(parse_grade_response(reply).feedback)
    return CheckResult(
        "feedback_length_bounded", length <= MAX_FEEDBACK_CHARS, f"{length} chars (max {MAX_FEEDBACK_CHARS})"
    )


def _check_no_compliance_language(reply: str) -> CheckResult:
    found = find_banned_phrases(parse_grade_response(reply).feedback)
    return CheckResult("no_compliance_language", not found, "banned phrases: " + ", ".join(found) if found else "")


# Insertion order is the report order. Each takes the stored reply text only (never the student's answer).
GRADE_CHECKS: dict[str, Callable[[str], CheckResult]] = {
    "grade_reply_parses": _check_grade_reply_parses,
    "grade_value_recognised": _check_grade_value_recognised,
    "feedback_present": _check_feedback_present,
    "feedback_length_bounded": _check_feedback_length_bounded,
    "no_compliance_language": _check_no_compliance_language,
}


def run_grade_checks(response_text: str) -> list[CheckResult]:
    """All applicable checks. An unparseable reply yields ONLY the parse failure: the rest are not
    computable from it, and reporting them as passes or fails would both be invented."""
    first = _check_grade_reply_parses(response_text)
    if not first.passed:
        return [first]
    return [first, *(check(response_text) for name, check in GRADE_CHECKS.items() if name != first.name)]


def _extract_question_and_answer(prompt_text: str) -> tuple[str, str] | None:
    """Question and student answer from a rendered grading prompt, or None when not reliably parseable.

    Anchored on the template's own delimiters. Each must occur EXACTLY once and in order: a student
    answer (or question) that contains a delimiter makes the split ambiguous, so the row is declined
    rather than guessed.
    """
    if any(prompt_text.count(mark) != 1 for mark in (_QUESTION_MARK, _ANSWER_MARK, _TAIL_MARK)):
        return None
    q_start = prompt_text.index(_QUESTION_MARK) + len(_QUESTION_MARK)
    a_mark = prompt_text.index(_ANSWER_MARK)
    a_start = a_mark + len(_ANSWER_MARK)
    tail = prompt_text.index(_TAIL_MARK)
    if not q_start <= a_mark <= a_start <= tail:
        return None
    question, answer = prompt_text[q_start:a_mark], prompt_text[a_start:tail]
    if not question.strip() or not answer.strip():
        return None
    return question, answer


def build_grade_case(prompt_text: str, response_text: str) -> GradeCase | UnsupportedGradeRow:
    """Rubric case from one SCRUBBED usage event of task ``grade_open_answer`` (pure; no scrubbing here)."""
    extracted = _extract_question_and_answer(prompt_text)
    if extracted is None:
        return UnsupportedGradeRow(REASON_PROMPT_UNPARSEABLE)
    parsed = parse_grade_response(response_text)
    # An unrecognised grade is coerced to "incorrect" by the product; judging against that would be a guess.
    if parsed.parse_error or not parsed.grade_recognised or not parsed.feedback.strip():
        return UnsupportedGradeRow(REASON_REPLY_UNPARSEABLE)
    return GradeCase(question=extracted[0], student_answer=extracted[1], grade=parsed.grade, feedback=parsed.feedback)


def rubric_applies(spec_id: str, case: GradeCase) -> bool:
    """G2 (no-reveal) is meaningful for partial/incorrect only; G1 applies to every graded row."""
    if spec_id == NO_REVEAL_SPEC.id:
        return reveal_rubric_applies(case.grade)
    return spec_id == CONSTRUCTIVE_SPEC.id


def register_grade_open_answer(registry: EvaluatorRegistry) -> None:
    for name in GRADE_CHECKS:
        registry.register(GRADE_TASK, Evaluator(name, KIND_DETERMINISTIC))
    for spec in GRADE_RUBRIC_SPECS:
        registry.register(GRADE_TASK, Evaluator(spec.id, KIND_JUDGE, rubric=spec))
