"""Characterization of the question-quality rubrics and checks (MLH-T18 slice 5a, SD-10).

Written against the code BEFORE the DeepEval-free parts moved into ``app/ai/eval/`` and kept
unchanged after: it imports only the old ``evals.*`` paths, so it proves the thin re-exports preserve
behaviour. The hashes are golden: stored calibration files are keyed by them, so any change here
silently invalidates every stored calibration.
"""

import asyncio
import hashlib
from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest

from evals import deterministic_checks as checks
from evals import question_rubrics as rubrics
from evals.judge import RouterJudge
from evals.question_model import EvalQuestion
from evals.rubric_core import BinaryRubricMetric, RubricSpec

_SPEC_HASHES = {
    "R1_key_correctness": "9a3a35f5e65af6889ed99a5cdf17667621da1303ee539821e902bc4bac4d1eee",
    "R2_exactly_one_correct": "8e6801d65d0ce2e416aadcab6c15dccf868b77390852d72368291af43186ff79",
    "R3_distractor_plausibility": "b91728740a9cff7c2587c77f72ed15ad73f1c233f9894e0a75ebadd4de60ef09",
    "R4_objective_alignment": "e63af07a05de594583673d37070b460f197281ca1ee9cd7b718d03cb84ad239b",
    "R5_grade_calibration": "cc9c6af1091abba32839dc6fd6e7c744b8cdf27c54aa65cba0d1951ed171b188",
    "R6_understanding_not_recall_foundational": "fd045e901e74daa35c927a3d4fcd9926a22053f5a60dcb47d285d3cbc5681da2",
    "R6_understanding_not_recall_applied": "f875249072e03c6f94a8b3567686e06a02e4b6863ac50e6585c9378ecc12c85b",
    "R7_explanation_quality_bank": "394bf65f90d0ed2338446a34207778a7fc10588e4e2fa110c11361a4cdad9e15",
    "R7_explanation_quality_quiz": "0bea876f3d1a3cd93284b7420babcde660bd686bcdba3f98784957fc12f01d35",
}
_PROMPT_HASHES = {
    "R1_key_correctness": "0ea1e817b17852d5b42920af4b4c83bdf51df1abdd9da905d161a47022d29c6f",
    "R2_exactly_one_correct": "c520d32150dc047578e0382abd26aeb1b2c34cbe775c1f0dc2d62677a1050873",
    "R3_distractor_plausibility": "6b67ca2631a74f21195da6b2d6e3fd754873eb55aaa77312f5f60c9518418d64",
    "R4_objective_alignment": "573817f58f3a76f720a5cd2ccc3e16059c1162ecd2425756a3ec6bcc0032d3c7",
    "R5_grade_calibration": "ac0588ea189a645a6c74d631c9eec7baf43e75a23b61a0b9472da98063fb4793",
    "R6_understanding_not_recall_foundational": "5c560cc9f4711b832653d3334a6a9532133ed761df64adb54f5586f06ebaf474",
    "R6_understanding_not_recall_applied": "5f3e6efbfba9ae3282245a550c768df344c1d29bf1ccaeb0d1a75f69dbf2b25c",
    "R7_explanation_quality_bank": "b6ecf93a39906a7f5de1c7205fa62535c7b886a75e218e821f8d838b8ce3d933",
    "R7_explanation_quality_quiz": "d0ca9f8fee140bddaea8857e84cc17ea05608d80e4e516e463fdbbcc9bec9a49",
}
# The code-scored prompts differ from the binary layout (no "Question:" line, own reply format).
_CODE_SCORED_PROMPT_HASHES = {
    "R1_key_correctness": "8068ee22165b90ac52d82b3685590518c351959dc35f801f1be289c10398df2f",
    "R2_exactly_one_correct": "00c9fa7e6fbe0dd28eb5d0e3963b7f28ba22f280254b021baac01c42e8f48416",
}


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


def _all_specs() -> list[RubricSpec]:
    return [
        rubrics.BLIND_SOLVE_SPEC,
        rubrics.EXACTLY_ONE_CORRECT_SPEC,
        rubrics.DISTRACTOR_PLAUSIBILITY_SPEC,
        rubrics.OBJECTIVE_ALIGNMENT_SPEC,
        rubrics.GRADE_CALIBRATION_SPEC,
        rubrics.understanding_spec("foundational"),
        rubrics.understanding_spec("developing"),
        rubrics.understanding_spec("advanced"),
        rubrics.explanation_spec("bank"),
        rubrics.explanation_spec("quiz"),
    ]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_rubric_specs_when_hashed_then_ids_and_hashes_match_golden_values() -> None:
    observed = {spec.id: spec.text_hash for spec in _all_specs()}
    assert observed == _SPEC_HASHES


def test_understanding_spec_when_developing_or_advanced_then_same_applied_spec() -> None:
    assert rubrics.understanding_spec("developing") == rubrics.understanding_spec("advanced")
    assert rubrics.understanding_spec("foundational") != rubrics.understanding_spec("developing")


def test_question_case_when_difficulty_unknown_then_metadata_has_not_specified() -> None:
    metadata = rubrics.question_case(_question()).metadata
    assert metadata == {
        "stem": "What is 1/2 + 1/3?",
        "options": "A. 2/5\nB. 5/6\nC. 1/6\nD. 2/6",
        "key": "B",
        "learning_objective": "Add fractions",
        "grade_level": "7",
        "difficulty_level": "not specified",
        "explanation": "Because 3/6 + 2/6 = 5/6.",
    }


@pytest.mark.parametrize("spec_id", sorted(_PROMPT_HASHES))
def test_binary_rubric_prompt_when_built_then_matches_golden_hash(spec_id: str) -> None:
    spec = next(s for s in _all_specs() if s.id == spec_id)
    case = {str(k): str(v) for k, v in (rubrics.question_case(_question()).metadata or {}).items()}
    assert _sha(BinaryRubricMetric(spec, RouterJudge()).build_prompt(case)) == _PROMPT_HASHES[spec_id]


@pytest.mark.parametrize(
    ("metric", "spec_id"),
    [
        (rubrics.BlindSolveMetric(RouterJudge()), "R1_key_correctness"),
        (rubrics.ExactlyOneCorrectMetric(RouterJudge()), "R2_exactly_one_correct"),
    ],
)
def test_code_scored_prompt_when_built_then_matches_golden_hash(metric: rubrics.BlindSolveMetric, spec_id: str) -> None:
    case = {str(k): str(v) for k, v in (rubrics.question_case(_question()).metadata or {}).items()}
    assert _sha(metric.build_prompt(case)) == _CODE_SCORED_PROMPT_HASHES[spec_id]


def _run(
    metric: rubrics.BlindSolveMetric | rubrics.ExactlyOneCorrectMetric, reply: str
) -> tuple[bool | None, bool, str | None, float | None]:
    with patch.object(RouterJudge, "a_generate", new=AsyncMock(return_value=reply)):
        asyncio.run(metric.a_measure(rubrics.question_case(_question())))
    return metric.verdict, metric.indeterminate, metric.reason, metric.score


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ('{"answer":"b","working":"x"}', (True, False, "solver chose B, matching the key", 1.0)),
        ('{"answer":"A"}', (False, False, "solver chose A but the key is B", 0.0)),
        ('{"answer":"Z"}', (None, True, "indeterminate: reply lacked an answer letter A-D", 0.0)),
        ("nope", (None, True, "indeterminate: reply was not JSON", 0.0)),
    ],
)
def test_blind_solve_metric_when_reply_given_then_outcome_matches_golden(
    reply: str, expected: tuple[bool | None, bool, str, float]
) -> None:
    assert _run(rubrics.BlindSolveMetric(RouterJudge()), reply) == expected


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ('{"correct_options":["B"],"evidence":"e"}', (True, False, "e", 1.0)),
        (
            '{"correct_options":["A","b"],"evidence":"e"}',
            (False, False, "judge found correct options ['A', 'B'] but the key is B. e", 0.0),
        ),
        ('{"correct_options":[]}', (False, False, "judge found correct options none but the key is B.", 0.0)),
        (
            '{"correct_options":"B"}',
            (None, True, "indeterminate: reply lacked a list of option letters A-D", 0.0),
        ),
        (
            '{"correct_options":["Q"]}',
            (None, True, "indeterminate: reply lacked a list of option letters A-D", 0.0),
        ),
    ],
)
def test_exactly_one_correct_metric_when_reply_given_then_outcome_matches_golden(
    reply: str, expected: tuple[bool | None, bool, str, float]
) -> None:
    assert _run(rubrics.ExactlyOneCorrectMetric(RouterJudge()), reply) == expected


def test_deterministic_checks_when_question_clean_then_all_pass() -> None:
    q = _question()
    for check in (
        checks.check_unique_options,
        checks.check_self_contained,
        checks.check_rendering_safe,
        checks.check_no_compliance_language,
        checks.check_answer_not_in_stem,
    ):
        assert check(q).passed
        assert check(q).detail == ""


def test_deterministic_checks_when_question_defective_then_names_and_details_match_golden() -> None:
    bad = replace(
        _question(),
        question_text="Refer to the diagram: what is $x^2$ for Cambridge compliant exam ready work?",
        options={"A": "same", "B": "Same ", "C": "the answer is here", "D": "see the table below"},
        correct_answer="C",
    )
    assert checks.check_unique_options(bad) == checks.CheckResult("unique_options", False, "duplicate options: A,B")
    assert checks.check_self_contained(bad) == checks.CheckResult(
        "self_contained",
        False,
        "question_text refers to 'Refer to the diagram'; option D refers to 'see the table'",
    )
    assert checks.check_rendering_safe(bad) == checks.CheckResult(
        "rendering_safe", False, "question_text contains '$x^2$'"
    )
    assert checks.check_no_compliance_language(bad) == checks.CheckResult(
        "no_compliance_language", False, "banned phrases: Cambridge compliant, exam ready"
    )


def test_set_level_checks_when_run_then_names_and_details_match_golden() -> None:
    q = _question()
    assert checks.check_no_duplicate_questions_in_set([q, replace(q, id="q2")]) == checks.CheckResult(
        "no_duplicate_questions_in_set", False, "duplicate stems: q1,q2"
    )
    assert checks.check_stem_opener_variety([q, q, q]) == checks.CheckResult(
        "stem_opener_variety", False, "'what is 1' x3"
    )
    assert checks.check_true_false_share(true_false_count=1, total=3) == checks.CheckResult(
        "true_false_share", False, "1/3 true_false (33%)"
    )
    assert checks.summarise_key_distribution([q]).counts == {"A": 0, "B": 1, "C": 0, "D": 0}
    assert checks.find_banned_phrases("Cambridge-aligned and IB compliant, mark scheme aligned") == [
        "Cambridge-aligned",
        "IB compliant",
        "mark scheme aligned",
    ]
