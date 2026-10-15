"""Offline tests for the question-suite calibration report renderer."""

from pathlib import Path
from typing import Literal

from app.ai.eval_metrics import rate
from evals.calibration import CalibrationResult, CalibrationVerdict, score_calibration
from evals.question_report import (
    GenerationSummary,
    RubricLine,
    render_calibration_report,
    render_generation_report,
    write_calibration_report,
)

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


def _summary(path: Literal["bank", "quiz"] = "bank", status: str = "CALIBRATED") -> GenerationSummary:
    return GenerationSummary(
        path=path,
        specs=12,
        structural={"ok": 11, "unparseable": 1},
        mcq=150,
        true_false=20,
        schema_failures=rate(3, 153),
        deterministic={"unique_options": rate(150, 150), "rendering_safe": rate(140, 150)},
        key_counts={"A": 30, "B": 40, "C": 40, "D": 40},
        key_max_share=0.27,
        rubrics=[RubricLine("R2_exactly_one_correct", rate(60, 70), rate(2, 72), status)],
        per_subject={"MATH": rate(48, 50)},
    )


def test_render_generation_report_when_rubric_uncalibrated_then_banner_shown_beside_its_rate() -> None:
    text = render_generation_report(_summary(status="MISSING"), "2026-10-15T00:00:00Z")

    row = next(line for line in text.splitlines() if line.startswith("| R2_exactly_one_correct"))
    assert "UNCALIBRATED" in row
    assert "indicative only" in row
    assert "MISSING" in row


def test_render_generation_report_when_rubric_calibrated_then_no_banner() -> None:
    text = render_generation_report(_summary(status="CALIBRATED"), "2026-10-15T00:00:00Z")

    row = next(line for line in text.splitlines() if line.startswith("| R2_exactly_one_correct"))
    assert "UNCALIBRATED" not in row


def test_render_generation_report_when_rendered_then_deterministic_checks_precede_judge_rubrics() -> None:
    text = render_generation_report(_summary(), "2026-10-15T00:00:00Z")

    assert text.index("## Deterministic checks") < text.index("## Judge rubrics")


def test_render_generation_report_when_quiz_path_then_includes_f1_upper_bound_note() -> None:
    quiz = render_generation_report(_summary(path="quiz"), "2026-10-15T00:00:00Z")
    bank = render_generation_report(_summary(path="bank"), "2026-10-15T00:00:00Z")

    assert "upper bound" in quiz
    assert "F1" in quiz
    assert "F1" not in bank


def test_render_generation_report_when_rendered_then_every_rate_shows_sample_size() -> None:
    text = render_generation_report(_summary(), "2026-10-15T00:00:00Z")

    for prefix in ("| unique_options", "| rendering_safe", "| R2_exactly_one_correct", "| MATH"):
        row = next(line for line in text.splitlines() if line.startswith(prefix))
        assert "n=" in row
    rubric_row = next(line for line in text.splitlines() if line.startswith("| R2_exactly_one_correct"))
    assert rubric_row.count("n=") == 2
    assert "n=153" in text


def test_render_generation_report_when_true_false_present_then_counted_and_set_aside() -> None:
    text = render_generation_report(_summary(), "2026-10-15T00:00:00Z")

    assert "True/false questions set aside" in text
    assert "20" in text
