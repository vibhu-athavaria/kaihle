"""Offline tests for the question-suite calibration report renderer."""

from pathlib import Path

from evals.calibration import CalibrationResult, CalibrationVerdict, score_calibration
from evals.question_report import render_calibration_report, write_calibration_report

CRIT = "R2_exactly_one_correct"


def _result(criterion: str, detected: int, total_defects: int, false_alarms: int, clean: int) -> CalibrationResult:
    """Defects are 'detected' when the criterion fails them; a clean case is a false alarm when it fails."""
    verdicts = [
        CalibrationVerdict(f"d{i}", criterion, "wrong_key", False, i >= detected, "computed")
        for i in range(total_defects)
    ]
    verdicts += [
        CalibrationVerdict(f"k{i}", criterion, None, True, i >= false_alarms, "computed") for i in range(clean)
    ]
    return score_calibration(verdicts, rubric_hash="h" * 64)


def _good() -> CalibrationResult:
    return _result(CRIT, detected=20, total_defects=20, false_alarms=0, clean=40)


def _bad() -> CalibrationResult:
    return _result("R3_distractor_plausibility", detected=2, total_defects=20, false_alarms=0, clean=40)


def test_render_calibration_report_when_rubric_not_calibrated_then_labelled_accordingly() -> None:
    text = render_calibration_report({CRIT: _good(), "R3_distractor_plausibility": _bad()}, {}, "2026-10-15T00:00:00Z")

    row = next(line for line in text.splitlines() if line.startswith("| R3_distractor_plausibility"))
    assert "NOT_CALIBRATED" in row
    assert "CALIBRATED" in next(line for line in text.splitlines() if line.startswith(f"| {CRIT}"))


def test_render_calibration_report_when_rendered_then_states_synthetic_defects_make_recall_an_upper_bound() -> None:
    text = render_calibration_report({CRIT: _good()}, {}, "2026-10-15T00:00:00Z")

    assert "upper bound" in text
    assert "genuinely ambiguous" in text


def test_render_calibration_report_when_rendered_then_production_judge_table_follows_new_rubric_table() -> None:
    text = render_calibration_report({CRIT: _good()}, {CRIT: _good()}, "2026-10-15T00:00:00Z")

    assert text.index("## Rubric calibration") < text.index("## Production question_quality judge")


def test_render_calibration_report_when_rendered_then_every_rate_shows_sample_size() -> None:
    text = render_calibration_report({CRIT: _good()}, {}, "2026-10-15T00:00:00Z")

    row = next(line for line in text.splitlines() if line.startswith(f"| {CRIT}"))
    assert row.count("n=") == 3


def test_render_calibration_report_when_no_production_results_then_says_so() -> None:
    text = render_calibration_report({CRIT: _good()}, {}, "2026-10-15T00:00:00Z")

    assert "not run" in text


def test_write_calibration_report_when_written_then_file_exists_in_out_dir(tmp_path: Path) -> None:
    path = write_calibration_report("# x\n", tmp_path, "2026-10-15T00-00-00Z")

    assert path.parent == tmp_path
    assert path.read_text(encoding="utf-8") == "# x\n"
