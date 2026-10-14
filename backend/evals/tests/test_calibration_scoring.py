"""Offline tests for calibration scoring, thresholds and persistence. Pure; persistence uses tmp_path."""

import json
from pathlib import Path
from typing import Literal

import pytest

from evals import thresholds
from evals.calibration import (
    CalibrationResult,
    CalibrationStatus,
    CalibrationVerdict,
    calibration_status,
    crosstalk_matrix,
    load_calibration,
    save_calibration,
    score_calibration,
)

CRIT = "R2_exactly_one_correct"
OTHER = "R3_distractor_plausibility"
HASH = "a" * 64


def _v(
    case_id: str,
    observed: bool | None,
    *,
    defect: str | None = "wrong_key",
    expected: bool = False,
    criterion: str = CRIT,
    subset: Literal["computed", "authored"] = "computed",
) -> CalibrationVerdict:
    return CalibrationVerdict(case_id, criterion, defect, expected, observed, subset)


def _defects(
    n: int, observed: bool | None, subset: Literal["computed", "authored"] = "computed"
) -> list[CalibrationVerdict]:
    """n seeded-defect verdicts targeting CRIT (expected fail)."""
    return [_v(f"d{i}", observed, subset=subset) for i in range(n)]


def _clean(
    n: int, observed: bool | None, subset: Literal["computed", "authored"] = "computed"
) -> list[CalibrationVerdict]:
    """n clean-case verdicts (expected pass)."""
    return [_v(f"k{i}", observed, defect=None, expected=True, subset=subset) for i in range(n)]


def test_score_calibration_when_defect_detected_then_counts_towards_recall() -> None:
    result = score_calibration([_v("a", False), _v("b", False), _v("c", True)], rubric_hash=HASH)

    assert (result.recall.numerator, result.recall.denominator) == (2, 3)


def test_score_calibration_when_defect_missed_then_recall_numerator_not_incremented() -> None:
    result = score_calibration([_v("a", True), _v("b", True)], rubric_hash=HASH)

    assert (result.recall.numerator, result.recall.denominator) == (0, 2)


def test_score_calibration_when_clean_case_fails_then_false_alarm_counted() -> None:
    result = score_calibration([*_clean(1, False), _v("b", True, defect=None, expected=True)], rubric_hash=HASH)

    assert (result.false_alarm.numerator, result.false_alarm.denominator) == (1, 2)


def test_score_calibration_when_indeterminate_then_excluded_from_denominators_and_reported() -> None:
    verdicts = [
        _v("a", False),
        _v("b", None),
        _v("c", True, defect=None, expected=True),
        _v("d", None, defect=None, expected=True),
    ]

    result = score_calibration(verdicts, rubric_hash=HASH)

    assert (result.recall.numerator, result.recall.denominator) == (1, 1)
    assert (result.false_alarm.numerator, result.false_alarm.denominator) == (0, 1)
    assert (result.indeterminate.numerator, result.indeterminate.denominator) == (2, 4)


def test_score_calibration_when_crosstalk_present_then_matrix_counts_it_by_defect_and_criterion() -> None:
    r2 = [
        _v("a", False, defect="absurd_distractor", expected=True),
        _v("b", True, defect="absurd_distractor", expected=True),
    ]
    r3 = [_v("a", False, defect="absurd_distractor", criterion=OTHER)]

    results = {CRIT: score_calibration(r2, rubric_hash=HASH), OTHER: score_calibration(r3, rubric_hash=HASH)}

    assert results[CRIT].crosstalk == {"absurd_distractor": 1}
    assert results[OTHER].crosstalk == {}  # the defect targets it, so a fail is recall, not cross-talk
    assert crosstalk_matrix(results) == {"absurd_distractor": {CRIT: 1}}


def test_calibration_status_when_recall_lower_bound_below_threshold_then_not_calibrated() -> None:
    result = score_calibration([*_defects(20, True), *_clean(20, True)], rubric_hash=HASH)  # recall 0/20

    assert calibration_status(result, "computed") is CalibrationStatus.NOT_CALIBRATED


def test_calibration_status_when_false_alarm_upper_bound_above_threshold_then_not_calibrated() -> None:
    result = score_calibration([*_defects(40, False), *_clean(20, False)], rubric_hash=HASH)  # false alarm 20/20

    assert calibration_status(result, "computed") is CalibrationStatus.NOT_CALIBRATED


def test_calibration_status_when_n_below_minimum_then_insufficient_n() -> None:
    result = score_calibration([*_defects(19, False), *_clean(40, True)], rubric_hash=HASH)

    assert calibration_status(result, "computed") is CalibrationStatus.INSUFFICIENT_N


def test_calibration_status_when_both_thresholds_met_then_calibrated() -> None:
    result = score_calibration([*_defects(60, False), *_clean(60, True)], rubric_hash=HASH)

    assert result.recall.low >= thresholds.RECALL_LOWER_MIN
    assert result.false_alarm.high <= thresholds.FALSE_ALARM_UPPER_MAX
    assert calibration_status(result, "computed") is CalibrationStatus.CALIBRATED


def test_calibration_status_when_authored_subset_then_never_calibrated_only_indicative() -> None:
    result = score_calibration([*_defects(60, False, "authored"), *_clean(60, True, "authored")], rubric_hash=HASH)

    assert calibration_status(result, "authored") is CalibrationStatus.INDICATIVE


def test_thresholds_when_imported_then_equal_the_preregistered_constants() -> None:
    assert thresholds.MIN_N == 20, "MIN_N is pre-registered (T10 D4); changing it needs an explicit PR statement"
    assert thresholds.RECALL_LOWER_MIN == 0.70, "pre-registered (T10 D4)"
    assert thresholds.FALSE_ALARM_UPPER_MAX == 0.15, "pre-registered (T10 D4)"


def test_calibration_result_when_computed_then_records_the_rubric_hash_it_was_computed_under() -> None:
    result = score_calibration([_v("a", False)], rubric_hash=HASH)

    assert result.rubric_hash == HASH
    assert result.criterion == CRIT


def test_save_calibration_when_written_then_file_contains_hash_rates_status_and_no_model_names(tmp_path: Path) -> None:
    result = score_calibration([*_defects(60, False), *_clean(60, True)], rubric_hash=HASH)

    path = save_calibration(result, tmp_path)

    text = path.read_text()
    data = json.loads(text)
    assert path == tmp_path / f"{CRIT}.json"
    assert data["rubric_hash"] == HASH
    assert data["status"] == "CALIBRATED"
    assert data["recall"]["denominator"] == 60
    assert data["false_alarm"]["denominator"] == 60
    assert data["saved_at"].endswith("+00:00")
    assert not any(name in text.lower() for name in ("model", "gpt", "claude", "gemini", "llama"))


def test_load_calibration_when_hash_matches_then_returns_the_stored_result(tmp_path: Path) -> None:
    result = score_calibration([*_defects(25, False), *_clean(25, True)], rubric_hash=HASH)
    save_calibration(result, tmp_path)

    loaded = load_calibration(CRIT, HASH, tmp_path)

    assert isinstance(loaded, CalibrationResult)
    assert loaded == result


def test_load_calibration_when_hash_differs_then_returns_stale_marker(tmp_path: Path) -> None:
    save_calibration(score_calibration([_v("a", False)], rubric_hash=HASH), tmp_path)

    assert load_calibration(CRIT, "b" * 64, tmp_path) is CalibrationStatus.STALE


def test_load_calibration_when_no_file_exists_then_returns_missing_marker(tmp_path: Path) -> None:
    assert load_calibration(CRIT, HASH, tmp_path) is CalibrationStatus.MISSING


def test_calibration_verdict_when_indeterminate_then_observed_pass_is_none_and_never_counted_as_pass() -> None:
    clean_indeterminate = _v("a", None, defect=None, expected=True)

    result = score_calibration([clean_indeterminate], rubric_hash=HASH)

    assert clean_indeterminate.observed_pass is None
    assert result.false_alarm.denominator == 0
    assert result.indeterminate.numerator == 1


def test_score_calibration_when_verdicts_mix_criteria_then_raises() -> None:
    with pytest.raises(ValueError, match="criterion"):
        score_calibration([_v("a", False), _v("b", False, criterion=OTHER)], rubric_hash=HASH)


def test_load_calibration_when_criterion_is_a_path_then_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="criterion"):
        load_calibration("../escape", HASH, tmp_path)
