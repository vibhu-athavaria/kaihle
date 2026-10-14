"""Live grade_open_answer evaluation (T9 slice 6). Spends real LLM calls: opt-in, never in default CI.

Skipped automatically (see ``evals/conftest.py``) unless the judge and graded models are configured.
This file lives outside ``evals/tests`` and ``pytest.ini`` limits default collection to ``app/tests``,
so neither the default run nor the offline CI job reaches it. Run locally with
``uv run --group eval pytest evals/test_grade_open_answer_eval.py``.

Assertions are structural only (SD-8): quality figures are report-only until a baseline is committed.
"""

import asyncio
from collections.abc import Iterator

import pytest

from evals.grade_run import DATASET_PATH, GradeRunResult, run_grade_eval
from evals.loader import load_grade_cases

pytestmark = pytest.mark.live_eval

REPORT_HEADINGS = ("## Accuracy", "## False credit", "## Parse failure", "## G-Eval feedback rubrics")


@pytest.fixture(scope="module")
def run_result() -> Iterator[GradeRunResult]:
    """One live run shared by every test in the module (the run is the expensive part)."""
    yield asyncio.run(run_grade_eval())


def test_grade_open_answer_when_golden_set_then_every_case_yields_an_outcome(run_result: GradeRunResult) -> None:
    expected_ids = [c.id for c in load_grade_cases(DATASET_PATH)]

    assert [g.outcome.case_id for g in run_result.graded] == expected_ids


def test_grade_open_answer_when_golden_set_then_report_is_written_and_parseable(run_result: GradeRunResult) -> None:
    text = run_result.report_path.read_text(encoding="utf-8")

    assert all(heading in text for heading in REPORT_HEADINGS)


def test_grade_feedback_when_any_grade_then_constructive_and_calibrated_scores_recorded(
    run_result: GradeRunResult,
) -> None:
    names = [r.name for r in run_result.rubric_results]

    assert "feedback_constructive_and_calibrated" in names


def test_grade_feedback_when_partial_or_incorrect_then_answer_not_revealed_scores_recorded(
    run_result: GradeRunResult,
) -> None:
    names = [r.name for r in run_result.rubric_results]

    assert "feedback_does_not_reveal_answer" in names
