"""Offline tests for the live-calibration scheduler/runner. Evaluators and the judge are fakes."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from evals import calibration_run
from evals.calibration import CalibrationVerdict
from evals.calibration_run import (
    CALIBRATION_JUDGED_TASKS,
    build_criterion_hashes,
    build_evaluators,
    run_calibration,
    run_calibration_eval,
    scheduled_criteria,
    score_verdicts,
)
from evals.calibration_set.build import SHIPPED_PATH, CalibrationCase, load_calibration_cases
from evals.judge import JudgeNotIndependentError


def _cases() -> list[CalibrationCase]:
    return load_calibration_cases(SHIPPED_PATH)


def _clean_and_mutated() -> tuple[CalibrationCase, CalibrationCase]:
    cases = _cases()
    return next(c for c in cases if c.defect is None), next(c for c in cases if c.defect == "wrong_key")


def test_scheduled_criteria_when_clean_case_then_every_criterion_expected_to_pass() -> None:
    clean, _ = _clean_and_mutated()

    scheduled = scheduled_criteria(clean)

    assert [c for c, _ in scheduled] == list(clean.must_pass)
    assert all(expected for _, expected in scheduled)


def test_scheduled_criteria_when_mutated_case_then_must_fail_plus_sampled_must_pass_only() -> None:
    _, mutated = _clean_and_mutated()

    scheduled = scheduled_criteria(mutated)

    assert scheduled == [(c, False) for c in mutated.must_fail] + [(c, True) for c in mutated.must_pass_sample]
    assert len(scheduled) < len(mutated.must_pass)


async def test_run_calibration_when_evaluator_returns_none_then_verdict_is_indeterminate_not_pass() -> None:
    clean, _ = _clean_and_mutated()
    evaluators = {c: AsyncMock(return_value=None) for c in clean.must_pass}

    verdicts = await run_calibration([clean], evaluators)

    assert len(verdicts) == len(clean.must_pass)
    assert all(v.observed_pass is None and v.expected_pass for v in verdicts)


async def test_run_calibration_when_mutated_case_then_verdicts_carry_defect_and_expectation() -> None:
    _, mutated = _clean_and_mutated()
    evaluators = {c: AsyncMock(return_value=False) for c in (*mutated.must_fail, *mutated.must_pass_sample)}

    verdicts = await run_calibration([mutated], evaluators)

    assert {(v.criterion, v.expected_pass) for v in verdicts} == set(scheduled_criteria(mutated))
    assert all(v.defect == "wrong_key" and v.case_id == mutated.case_id and v.subset == "computed" for v in verdicts)


async def test_run_calibration_when_evaluator_raises_then_exception_propagates() -> None:
    clean, _ = _clean_and_mutated()
    evaluators = {c: AsyncMock(side_effect=RuntimeError("router down")) for c in clean.must_pass}

    with pytest.raises(RuntimeError, match="router down"):
        await run_calibration([clean], evaluators)


async def test_run_calibration_when_criterion_has_no_evaluator_then_raises_key_error() -> None:
    clean, _ = _clean_and_mutated()

    with pytest.raises(KeyError):
        await run_calibration([clean], {})


async def test_build_evaluators_when_deterministic_criterion_then_runs_check_without_judge() -> None:
    judge = MagicMock()
    judge.a_generate = AsyncMock()
    clean, _ = _clean_and_mutated()

    result = await build_evaluators(judge)["unique_options"](clean.question)

    assert result is True
    judge.a_generate.assert_not_called()


async def test_build_evaluators_when_judge_reply_unparseable_then_none() -> None:
    judge = MagicMock()
    judge.a_generate = AsyncMock(return_value="not json at all")
    clean, _ = _clean_and_mutated()

    result = await build_evaluators(judge)["R3_distractor_plausibility"](clean.question)

    assert result is None


async def test_build_evaluators_when_judge_passes_rubric_then_true() -> None:
    judge = MagicMock()
    judge.a_generate = AsyncMock(return_value='{"pass": true, "evidence": "ok"}')
    clean, _ = _clean_and_mutated()

    assert await build_evaluators(judge)["R3_distractor_plausibility"](clean.question) is True


def test_build_evaluators_when_built_then_covers_every_criterion_the_shipped_set_schedules() -> None:
    scheduled = {c for case in _cases() for c, _ in scheduled_criteria(case)}

    assert scheduled <= set(build_evaluators(MagicMock()))
    assert scheduled <= set(build_criterion_hashes())


def test_score_verdicts_when_two_criteria_then_one_result_each_with_its_hash() -> None:
    verdicts = [
        CalibrationVerdict("a", "R3_distractor_plausibility", "wrong_key", False, False, "computed"),
        CalibrationVerdict("b", "unique_options", None, True, True, "computed"),
    ]
    hashes = {"R3_distractor_plausibility": "h3", "unique_options": "hu"}

    results = score_verdicts(verdicts, hashes)

    assert set(results) == {"R3_distractor_plausibility", "unique_options"}
    assert results["R3_distractor_plausibility"].rubric_hash == "h3"
    assert results["unique_options"].false_alarm.denominator == 1


def test_criterion_hashes_when_built_then_rubrics_use_spec_hash_and_checks_use_their_name() -> None:
    hashes = build_criterion_hashes()

    assert hashes["unique_options"] == "unique_options"
    assert len(hashes["R1_key_correctness"]) == 64


async def test_run_calibration_eval_when_judge_not_independent_then_raises_before_any_call(tmp_path: Path) -> None:
    with (
        patch.object(calibration_run, "require_judge_configured"),
        patch.object(calibration_run, "check_judge_independence", side_effect=JudgeNotIndependentError("same")),
        patch.object(calibration_run, "build_evaluators") as build,
        pytest.raises(JudgeNotIndependentError),
    ):
        await run_calibration_eval(out_dir=tmp_path)

    build.assert_not_called()


async def test_run_calibration_eval_when_run_then_checks_every_judged_task_and_writes_results_and_report(
    tmp_path: Path,
) -> None:
    all_ids = {c for case in _cases() for c, _ in scheduled_criteria(case)}
    fake = {c: AsyncMock(return_value=True) for c in all_ids}
    with (
        patch.object(calibration_run, "require_judge_configured"),
        patch.object(calibration_run, "check_judge_independence") as independence,
        patch.object(calibration_run, "build_evaluators", return_value=fake),
        patch.object(calibration_run, "run_prod_judge_calibration", new_callable=AsyncMock, return_value=[]),
    ):
        result = await run_calibration_eval(out_dir=tmp_path / "reports", calibration_dir=tmp_path / "cal")

    assert [c.args[0] for c in independence.call_args_list] == list(CALIBRATION_JUDGED_TASKS)
    assert set(CALIBRATION_JUDGED_TASKS) == {"quiz_generation", "question_generation", "question_quality"}
    assert (tmp_path / "cal" / "R1_key_correctness.json").is_file()
    assert set(result.results) == all_ids
    assert result.report_path.read_text(encoding="utf-8").startswith("# ")
