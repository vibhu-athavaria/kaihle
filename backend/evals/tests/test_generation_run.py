"""Offline tests for the bank-generation run orchestration. No network; evaluators are fakes."""

from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from evals.calibration import CalibrationStatus
from evals.calibration_set.build import SHIPPED_PATH, load_calibration_cases
from evals.generation_run import (
    JUDGED_PER_SPEC,
    rubric_criteria,
    run_bank_generation_eval,
    sample_for_judging,
    score_rubrics,
    summarise_bank,
)
from evals.judge import JudgeNotIndependentError
from evals.question_generation import BankOutcome, GenerationSpec
from evals.question_model import EvalQuestion

BASE = load_calibration_cases(SHIPPED_PATH)[0].question


def _questions(spec_id: str, count: int, subject: str = "MATH") -> list[EvalQuestion]:
    return [
        replace(BASE, id=f"{spec_id}-q{i:02d}", subject_code=subject, question_text=f"Stem {i}?") for i in range(count)
    ]


def test_sample_for_judging_when_spec_has_many_questions_then_capped_and_reproducible() -> None:
    outcomes = [
        BankOutcome("gen-001", "ok", _questions("gen-001", 15)),
        BankOutcome("gen-002", "ok", _questions("gen-002", 3)),
    ]

    first = sample_for_judging(outcomes)

    assert first == sample_for_judging(outcomes)
    assert len([q for q in first if q.id.startswith("gen-001")]) == JUDGED_PER_SPEC
    assert len([q for q in first if q.id.startswith("gen-002")]) == 3


def test_rubric_criteria_when_band_differs_then_understanding_rubric_variant_follows_band() -> None:
    foundational = rubric_criteria(replace(BASE, difficulty_band="foundational"))
    advanced = rubric_criteria(replace(BASE, difficulty_band="advanced"))

    assert foundational != advanced
    assert "R7_explanation_quality_bank" in foundational
    assert "R1_key_correctness" in foundational


async def test_score_rubrics_when_evaluator_is_indeterminate_then_counted_separately_and_never_a_pass() -> None:
    questions = _questions("gen-001", 4)
    replies = iter([True, False, None, None])

    async def evaluate(_: EvalQuestion) -> bool | None:
        return next(replies)

    tallies = await score_rubrics(questions, {"R1_key_correctness": evaluate}, lambda _: ["R1_key_correctness"])

    assert tallies["R1_key_correctness"].passes == 1
    assert tallies["R1_key_correctness"].fails == 1
    assert tallies["R1_key_correctness"].indeterminate == 2


def test_summarise_bank_when_outcomes_given_then_counts_set_aside_and_structural_failures_reported() -> None:
    outcomes = [
        BankOutcome("gen-001", "ok", _questions("gen-001", 5), true_false_count=2, schema_failures=["question 9: bad"]),
        BankOutcome("gen-002", "unparseable"),
        BankOutcome("gen-003", "ok", _questions("gen-003", 5, "SCI")),
    ]

    summary = summarise_bank(outcomes, [])

    assert summary.specs == 3
    assert summary.structural == {"ok": 2, "unparseable": 1}
    assert (summary.mcq, summary.true_false) == (10, 2)
    assert (summary.schema_failures.numerator, summary.schema_failures.denominator) == (1, 11)
    assert set(summary.per_subject) == {"MATH", "SCI"}
    assert summary.deterministic["unique_options"].denominator == 10
    assert summary.deterministic["no_duplicate_questions_in_set"].denominator == 2


def test_summarise_bank_when_two_questions_share_a_stem_then_set_duplicate_check_fails() -> None:
    dupes = [replace(q, question_text="Same stem?") for q in _questions("gen-001", 3)]

    summary = summarise_bank([BankOutcome("gen-001", "ok", dupes)], [])

    assert summary.deterministic["no_duplicate_questions_in_set"].numerator == 0


async def test_run_bank_generation_eval_when_judge_not_independent_then_no_generation_call_is_made(
    tmp_path: Path,
) -> None:
    with (
        patch("evals.generation_run.require_judge_configured"),
        patch("evals.generation_run.check_judge_independence", side_effect=JudgeNotIndependentError("same model")),
        patch("evals.generation_run.generate_bank_outcome", new_callable=AsyncMock) as generate,
        pytest.raises(JudgeNotIndependentError),
    ):
        await run_bank_generation_eval(out_dir=tmp_path)

    generate.assert_not_called()


async def test_run_bank_generation_eval_when_run_then_report_written_with_missing_calibration_flagged(
    tmp_path: Path,
) -> None:
    async def fake_outcome(spec: GenerationSpec, run_id: str | None = None) -> BankOutcome:
        return BankOutcome(spec.spec_id, "ok", _questions(spec.spec_id, 4, spec.subject_code))

    async def always_pass(_: EvalQuestion) -> bool | None:
        return True

    with (
        patch("evals.generation_run.require_judge_configured"),
        patch("evals.generation_run.check_judge_independence"),
        patch("evals.generation_run.generate_bank_outcome", side_effect=fake_outcome),
        patch("evals.generation_run.build_evaluators", return_value=dict.fromkeys(_ALL, always_pass)),
    ):
        result = await run_bank_generation_eval(out_dir=tmp_path, calibration_dir=tmp_path / "none")

    text = result.report_path.read_text(encoding="utf-8")
    assert result.report_path.parent == tmp_path
    assert CalibrationStatus.MISSING.value in text
    assert "UNCALIBRATED" in text
    assert result.summary.mcq == 48


_ALL = [
    "R1_key_correctness",
    "R2_exactly_one_correct",
    "R3_distractor_plausibility",
    "R4_objective_alignment",
    "R5_grade_calibration",
    "R6_understanding_not_recall_foundational",
    "R6_understanding_not_recall_applied",
    "R7_explanation_quality_bank",
]
