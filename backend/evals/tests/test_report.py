"""Offline tests for the grading report renderer. No network, no LLM, no DB."""

import re
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from app.ai.eval_metrics import rate
from evals.grade_metrics import GradeOutcome, GradeSummary, summarise_grades
from evals.report import RubricResult, RunMeta, build_run_meta, render_report, utc_timestamp, write_report

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _meta() -> RunMeta:
    return RunMeta(
        timestamp_utc="2026-10-10T00:00:00Z",
        judge_model="placeholder/judge",
        graded_model="placeholder/graded",
        dataset_sha256="0" * 64,
        deepeval_version="0.0.0",
    )


def _summary() -> GradeSummary:
    outcomes = [
        GradeOutcome("a", "correct", "correct", False, True, ("terse_correct",)),
        GradeOutcome("b", "incorrect", "correct", False, True, ("prompt_injection",)),
        GradeOutcome("c", "incorrect", "incorrect", True, False, ()),
        GradeOutcome("d", "partial", "partial", False, True, ()),
    ]
    return summarise_grades(outcomes)


def _rubrics() -> list[RubricResult]:
    return [RubricResult(name="feedback_constructive_and_calibrated", passes=3, evaluated=4, errors=0)]


def test_render_report_when_summary_given_then_every_rate_shows_sample_size() -> None:
    text = render_report(_summary(), _meta(), _rubrics())

    rate_lines = [ln for ln in text.splitlines() if "%" in ln and "[" in ln and "–" in ln]
    assert len(rate_lines) >= 6
    assert all("n=" in ln for ln in rate_lines)


def test_render_report_when_rendered_then_states_labels_are_model_authored_and_unvalidated() -> None:
    text = render_report(_summary(), _meta(), _rubrics())

    assert "model-authored" in text.lower()
    assert "unvalidated" in text.lower()
    assert text.lower().index("model-authored") < text.index("Accuracy")


def test_render_report_when_rendered_then_false_credit_and_parse_failure_have_own_sections() -> None:
    text = render_report(_summary(), _meta(), _rubrics())

    headings = [ln for ln in text.splitlines() if ln.startswith("#")]
    assert any("False credit" in h for h in headings)
    assert any("Parse failure" in h for h in headings)
    assert any("False denial" in h for h in headings)
    assert any("tag" in h.lower() for h in headings)


def test_render_report_when_rendered_then_includes_run_meta_and_judge_variance_note() -> None:
    text = render_report(_summary(), _meta(), _rubrics())

    assert "2026-10-10T00:00:00Z" in text
    assert "placeholder/judge" in text and "placeholder/graded" in text
    assert "0" * 64 in text
    assert "judge variance not measured" in text
    assert rate(3, 4).format() in text


def test_render_report_when_no_rubric_results_then_says_not_run() -> None:
    text = render_report(_summary(), _meta(), [])

    assert "not run" in text.lower()


def test_write_report_when_default_dir_then_path_is_gitignored() -> None:
    path = write_report("body", timestamp_utc="2099-01-01T00-00-00Z")
    try:
        result = subprocess.run(["git", "check-ignore", "-q", str(path)], cwd=BACKEND_DIR, check=False)
        assert result.returncode == 0
        assert path.read_text(encoding="utf-8") == "body"
    finally:
        path.unlink(missing_ok=True)


def test_write_report_when_custom_dir_then_creates_it_and_names_file_by_timestamp(tmp_path: Path) -> None:
    path = write_report("x", out_dir=tmp_path / "nested", timestamp_utc="2026-10-10T01-02-03Z")

    assert path.name == "grade_open_answer_2026-10-10T01-02-03Z.md"
    assert path.parent == tmp_path / "nested"


def test_utc_timestamp_when_called_then_is_filename_safe() -> None:
    assert ":" not in utc_timestamp()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z", utc_timestamp())


def test_build_run_meta_when_called_then_timestamp_is_iso8601_utc(tmp_path: Path) -> None:
    dataset = tmp_path / "d.jsonl"
    dataset.write_text("x", encoding="utf-8")

    meta = build_run_meta(dataset)

    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", meta.timestamp_utc)


def test_write_report_when_timestamp_has_colons_then_filename_is_sanitised(tmp_path: Path) -> None:
    path = write_report("x", out_dir=tmp_path, timestamp_utc="2026-10-10T01:02:03Z")

    assert ":" not in path.name
    assert path.parent == tmp_path


@pytest.mark.parametrize("bad", ["../escape", "a/b", "a\\b", ".."])
def test_write_report_when_timestamp_has_path_parts_then_stays_inside_dir_or_raises(bad: str, tmp_path: Path) -> None:
    if ".." in bad:
        with pytest.raises(ValueError):
            write_report("x", out_dir=tmp_path, timestamp_utc=bad)
        return
    path = write_report("x", out_dir=tmp_path, timestamp_utc=bad)
    assert path.parent == tmp_path


def test_build_run_meta_when_models_unset_then_placeholder_rendered_and_warning_logged(tmp_path: Path) -> None:
    dataset = tmp_path / "d.jsonl"
    dataset.write_text("x", encoding="utf-8")
    with (
        patch("evals.report.TASK_MODEL_MAP", {}),
        patch("evals.report.settings") as cfg,
        patch("evals.report.logger") as log,
    ):
        cfg.llm_eval_judge_model = ""
        meta = build_run_meta(dataset)

    assert meta.judge_model == "(unset)"
    assert meta.graded_model == "(unset)"
    assert log.warning.called
    assert "(unset)" in render_report(_summary(), meta, [])
