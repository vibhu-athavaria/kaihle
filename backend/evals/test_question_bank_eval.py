"""Live question-bank generation eval (T10 slice 8). Spends real LLM calls: opt-in, never in default CI.

Skipped automatically (see ``evals/conftest.py``) unless the judge is configured. Run locally with
``uv run --group eval pytest evals/test_question_bank_eval.py``. Assertions are structural only (SD-8):
pass rates, calibration statuses and the findings are report-only and never gated here.
"""

import asyncio
from collections.abc import Iterator

import pytest

from evals.generation_run import BankRunResult, run_bank_generation_eval
from evals.question_generation import load_generation_specs

pytestmark = pytest.mark.live_eval

REPORT_HEADINGS = ("## Structural outcomes", "## Deterministic checks", "## Judge rubrics", "## Per-subject")


@pytest.fixture(scope="module")
def run_result() -> Iterator[BankRunResult]:
    """One live run shared by every test in the module (the run is the expensive part)."""
    yield asyncio.run(run_bank_generation_eval())


def test_question_bank_generation_when_specs_run_then_every_spec_yields_an_outcome(
    run_result: BankRunResult,
) -> None:
    assert [o.spec_id for o in run_result.outcomes] == [s.spec_id for s in load_generation_specs()]


def test_question_bank_generation_when_run_then_report_is_written_and_parseable(run_result: BankRunResult) -> None:
    text = run_result.report_path.read_text(encoding="utf-8")

    assert all(heading in text for heading in REPORT_HEADINGS)
