"""MCQ quality rubrics R1-R7 (DeepEval-free definitions; MLH-T18 slice 5a).

Moved from ``evals.question_rubrics`` so production code can run them; that module re-exports every
name and keeps the DeepEval metric classes, which delegate to the logic here. Spec text is
hashed (``RubricSpec.text_hash``) and stored calibration is keyed by that hash: do NOT reword
anything below without re-calibrating (characterization test: ``evals/tests/test_question_eval_surface.py``).

Two kinds of rubric:

* **Judge-verdict rubrics** (R3-R7) are ``RubricSpec``s whose judge replies ``{"pass","evidence"}``.
  R6 and R7 are parameterised (D7): ``understanding_spec(band)`` and ``explanation_spec(path)``. Each
  variant is a distinct spec id, so each has its own text hash and its own stored calibration.
* **Code-scored rubrics** (R1, R2) ask the judge a factual question and compare the reply with the
  answer key **in code** (D6): R1 never shows the judge the key or the explanation; R2 shows the key
  but scores the judge's per-option statement.

An unusable judge reply is verdict ``None`` and never a pass (D8). Wording says "curriculum-informed"
and names no model (Rule 23, SD-2).
"""

from collections.abc import Mapping
from typing import Any, Literal

from app.ai.eval.judge_runner import (
    CodeScoredRubric,
    Completion,
    RubricOutcome,
    run_binary_rubric,
    run_code_scored_rubric,
)
from app.ai.eval.question_model import OPTION_KEYS, DifficultyBand, EvalQuestion
from app.ai.eval.rubric_core import RubricSpec

QuestionPath = Literal["bank", "quiz"]

_NOT_SPECIFIED = "not specified"
_CASE_PARAMS = ("stem", "options", "key")

BLIND_SOLVE_SPEC = RubricSpec(
    id="R1_key_correctness",
    question="Does an independent solver, who is not shown the answer key, choose the keyed option?",
    instructions=(
        "You are a subject teacher. Solve the multiple-choice question below independently and choose the "
        "single best option. Work it out step by step before choosing. You are not told the intended "
        "answer; do not try to guess what the author intended."
    ),
    params=("stem", "options"),
)
EXACTLY_ONE_CORRECT_SPEC = RubricSpec(
    id="R2_exactly_one_correct",
    question="Is exactly one option, the keyed one, defensibly correct?",
    instructions=(
        "You are a subject teacher checking a multiple-choice item. For each option A-D decide whether a "
        "knowledgeable teacher could defend it as a correct answer to the question as worded, including "
        "values written in an equivalent form (for example 0.5 and 1/2). List every defensibly correct "
        "option. The key shown is the author's claim; do not assume it is right."
    ),
    params=_CASE_PARAMS,
)
DISTRACTOR_PLAUSIBILITY_SPEC = RubricSpec(
    id="R3_distractor_plausibility",
    question="Does every wrong option correspond to a plausible student misconception?",
    instructions=(
        "Judge the wrong options (every option except the keyed one). PASS only if each wrong option is "
        "something a student could plausibly choose because of a specific misconception or slip, such as "
        "a sign error, a wrong operation, a forgotten step or a common confusion. FAIL if any wrong "
        "option is absurd, incoherent, out of range, unrelated to the question, or duplicates another "
        "option. Good: an answer that results from adding instead of multiplying. Bad: a value that no "
        "reasoning could produce."
    ),
    params=_CASE_PARAMS,
)
OBJECTIVE_ALIGNMENT_SPEC = RubricSpec(
    id="R4_objective_alignment",
    question="Does the question test the stated learning objective rather than an adjacent skill?",
    instructions=(
        "Decide whether answering this question requires the skill named in the learning objective. PASS "
        "if the objective is what the question mainly tests. FAIL if it mainly tests a different or "
        "adjacent skill, or the objective is not needed to answer it. The objective is curriculum-informed "
        "context supplied by the school; do not judge the objective itself."
    ),
    params=("learning_objective", "stem", "options", "key"),
)
GRADE_CALIBRATION_SPEC = RubricSpec(
    id="R5_grade_calibration",
    question="Does the question require reasoning at the stated grade level, not below it?",
    instructions=(
        "Decide whether the question is pitched at the stated grade level. PASS if a typical student at "
        "that grade needs the reasoning expected at that grade (and the stated difficulty level, when "
        "given: 1 is easiest, 5 is hardest). FAIL if it would suit a clearly younger grade, or is far "
        "beyond the stated grade."
    ),
    params=("grade_level", "difficulty_level", "stem", "options", "key"),
)

_RECALL_PERMITTED = (
    "The item is foundational, so recall is acceptable: PASS if it checks a core fact, term or "
    "procedure accurately. FAIL only if it is trivial because the stem gives the answer away."
)
_RECALL_NOT_PERMITTED = (
    "The item is not foundational, so it must not be answerable by recall alone: PASS only if the "
    "student has to apply, interpret, compare or reason with the idea. FAIL if remembering a fact, "
    "term or formula is enough."
)


def understanding_spec(band: DifficultyBand) -> RubricSpec:
    """R6, parameterised by difficulty band (D7a): ``foundational`` permits recall, the others do not."""
    foundational = band == "foundational"
    return RubricSpec(
        id="R6_understanding_not_recall_" + ("foundational" if foundational else "applied"),
        question="Does the question test understanding appropriate to its difficulty band?",
        instructions=(
            "Decide whether the question tests understanding at the level its difficulty band calls for. "
            + (_RECALL_PERMITTED if foundational else _RECALL_NOT_PERMITTED)
        ),
        params=_CASE_PARAMS,
    )


def explanation_spec(path: QuestionPath) -> RubricSpec:
    """R7, parameterised by generation path (D7b): the bank explains every option, the quiz explains the key."""
    bank = path == "bank"
    contract = (
        "The explanation must say why the keyed option is right and why each wrong option is wrong."
        if bank
        else "The explanation must say why the keyed option is right."
    )
    return RubricSpec(
        id=f"R7_explanation_quality_{path}",
        question="Does the explanation support the keyed answer and meet its contract?",
        instructions=(
            f"Judge the explanation. {contract} FAIL if it argues for a different option than the key, "
            "contradicts the question, or is too vague to teach anything."
        ),
        params=(*_CASE_PARAMS, "explanation"),
    )


def question_case_data(question: EvalQuestion) -> dict[str, str]:
    """Package a question as rubric DATA. Keys match the ``RubricSpec.params`` names."""
    return {
        "stem": question.question_text,
        "options": "\n".join(f"{key}. {question.options[key]}" for key in OPTION_KEYS),
        "key": question.correct_answer,
        "learning_objective": question.learning_objective,
        "grade_level": str(question.grade_level),
        "difficulty_level": _NOT_SPECIFIED if question.difficulty_level is None else str(question.difficulty_level),
        "explanation": question.explanation,
    }


def _letter(value: object) -> str | None:
    letter = value.strip().upper() if isinstance(value, str) else ""
    return letter if letter in OPTION_KEYS else None


def decide_blind_solve(data: Mapping[str, Any], key: str) -> tuple[bool | None, str]:
    """R1: the judge solved the item blind; pass iff its answer letter equals the key."""
    answer = _letter(data.get("answer"))
    if answer is None:
        return None, "reply lacked an answer letter A-D"
    if answer == key:
        return True, f"solver chose {answer}, matching the key"
    return False, f"solver chose {answer} but the key is {key}"


def decide_exactly_one_correct(data: Mapping[str, Any], key: str) -> tuple[bool | None, str]:
    """R2: the judge listed the defensibly correct options; pass iff that list is exactly the key."""
    listed = data.get("correct_options")
    letters = [_letter(item) for item in listed] if isinstance(listed, list) else [None]
    if any(letter is None for letter in letters):
        return None, "reply lacked a list of option letters A-D"
    found = sorted({letter for letter in letters if letter})
    evidence = str(data.get("evidence", ""))
    if found == [key]:
        return True, evidence
    return False, f"judge found correct options {found or 'none'} but the key is {key}. {evidence}".strip()


BLIND_SOLVE = CodeScoredRubric(
    BLIND_SOLVE_SPEC, '{"answer": "A, B, C or D", "working": "short working"}', decide_blind_solve
)
EXACTLY_ONE_CORRECT = CodeScoredRubric(
    EXACTLY_ONE_CORRECT_SPEC,
    '{"correct_options": ["letters A-D that are defensibly correct"], "evidence": "one sentence"}',
    decide_exactly_one_correct,
)
CODE_SCORED_RUBRICS: dict[str, CodeScoredRubric] = {r.spec.id: r for r in (BLIND_SOLVE, EXACTLY_ONE_CORRECT)}


async def run_question_rubric(spec: RubricSpec, question: EvalQuestion, completion: Completion) -> RubricOutcome:
    """Run one rubric on one question through ``completion``; code-scored rubrics are decided in code."""
    case = question_case_data(question)
    code_scored = CODE_SCORED_RUBRICS.get(spec.id)
    if code_scored is not None:
        return await run_code_scored_rubric(code_scored, case, completion)
    return await run_binary_rubric(spec, case, completion)
