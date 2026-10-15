"""Live question-quality calibration (T10 slice 7). Spends real LLM calls: opt-in, never in default CI.

Skipped automatically (see ``evals/conftest.py``) unless the judge is configured. Run locally with
``uv run --group eval pytest evals/test_question_calibration_eval.py``. Assertions are structural only
(SD-8): recall, false-alarm and status figures are report-only and never gated here.
"""

import asyncio
from collections.abc import Iterator

import pytest

from evals.calibration_run import CalibrationRunResult, run_calibration_eval, scheduled_criteria
from evals.calibration_set.build import load_calibration_cases

pytestmark = pytest.mark.live_eval

REPORT_HEADINGS = ("## Rubric calibration", "## Cross-talk", "## Production question_quality judge")


@pytest.fixture(scope="module")
def run_result() -> Iterator[CalibrationRunResult]:
    """One live run shared by every test in the module (the run is the expensive part)."""
    yield asyncio.run(run_calibration_eval())


def test_calibration_when_run_then_every_scheduled_case_and_criterion_has_a_verdict(
    run_result: CalibrationRunResult,
) -> None:
    expected = [(c.case_id, criterion) for c in load_calibration_cases() for criterion, _ in scheduled_criteria(c)]

    assert [(v.case_id, v.criterion) for v in run_result.verdicts] == expected


def test_calibration_when_run_then_report_is_written_and_parseable(run_result: CalibrationRunResult) -> None:
    text = run_result.report_path.read_text(encoding="utf-8")

    assert all(heading in text for heading in REPORT_HEADINGS)


def test_prod_question_quality_judge_when_run_on_calibration_set_then_recall_and_false_alarm_recorded(
    run_result: CalibrationRunResult,
) -> None:
    assert run_result.prod_results
    assert all(r.recall.denominator + r.false_alarm.denominator > 0 for r in run_result.prod_results.values())
