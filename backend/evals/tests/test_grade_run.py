"""Offline tests for the grade_open_answer run orchestrator. Grader and judge are mocked."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from deepeval.test_case import LLMTestCase

from evals.grade_run import (
    DATASET_PATH,
    measure_observed_pass,
    run_grade_eval,
    run_grade_rubrics,
    score_cases,
)
from evals.loader import GradeCase


def _case(case_id: str, expected: str, tags: list[str] | None = None) -> GradeCase:
    return GradeCase.model_validate(
        {
            "id": case_id,
            "subject": "Mathematics",
            "grade_level": 7,
            "subtopic_name": "Fractions",
            "learning_objective": None,
            "question_text": "What is 1/2 + 1/3?",
            "student_answer": "5/6",
            "expected_grade": expected,
            "tags": tags or [],
            "rationale": "synthetic",
            "label_source": "model-authored-unvalidated",
        }
    )


def _reply(grade: str) -> str:
    return json.dumps({"grade": grade, "feedback": "Keep going."})


def _metric(*, score_success: bool = True, error: Exception | None = None) -> MagicMock:
    metric = MagicMock()
    metric.a_measure = AsyncMock(side_effect=error, return_value=1.0)
    metric.is_successful = MagicMock(return_value=score_success)
    return metric


async def test_score_cases_when_replies_parse_then_one_outcome_per_case_with_tags() -> None:
    cases = [_case("A", "correct"), _case("B", "incorrect", ["off_topic"])]
    with patch("evals.grade_run.request_grade_completion", new_callable=AsyncMock) as grader:
        grader.side_effect = [_reply("correct"), _reply("correct")]
        graded = await score_cases(cases)

    assert [g.outcome.case_id for g in graded] == ["A", "B"]
    assert graded[1].outcome.predicted == "correct"
    assert graded[1].outcome.expected == "incorrect"
    assert graded[1].outcome.tags == ("off_topic",)


async def test_score_cases_when_reply_unparseable_then_outcome_flags_parse_error() -> None:
    with patch("evals.grade_run.request_grade_completion", new_callable=AsyncMock) as grader:
        grader.return_value = "not json"
        graded = await score_cases([_case("A", "correct")])

    assert graded[0].outcome.parse_error is True
    assert graded[0].outcome.predicted == "incorrect"


async def test_score_cases_when_grader_raises_then_exception_propagates() -> None:
    with patch("evals.grade_run.request_grade_completion", new_callable=AsyncMock) as grader:
        grader.side_effect = RuntimeError("router down")
        with pytest.raises(RuntimeError, match="router down"):
            await score_cases([_case("A", "correct")])


async def test_measure_observed_pass_when_metric_passes_then_true() -> None:
    result = await measure_observed_pass(_metric(score_success=True), LLMTestCase(input="i", actual_output="o"))

    assert result is True


async def test_measure_observed_pass_when_metric_fails_then_false() -> None:
    result = await measure_observed_pass(_metric(score_success=False), LLMTestCase(input="i", actual_output="o"))

    assert result is False


async def test_measure_observed_pass_when_judge_reply_unparseable_then_none_not_a_pass() -> None:
    metric = _metric(error=ValueError("Evaluation LLM outputted an invalid JSON"))
    with patch("evals.grade_run.logger") as logger:
        result = await measure_observed_pass(metric, LLMTestCase(input="i", actual_output="o"))

    assert result is None
    logger.warning.assert_called_once()


async def test_measure_observed_pass_when_router_raises_then_exception_propagates() -> None:
    metric = _metric(error=RuntimeError("router down"))

    with pytest.raises(RuntimeError, match="router down"):
        await measure_observed_pass(metric, LLMTestCase(input="i", actual_output="o"))


async def test_run_grade_rubrics_when_indeterminate_then_counted_as_error_excluded_from_evaluated() -> None:
    with patch("evals.grade_run.request_grade_completion", new_callable=AsyncMock) as grader:
        grader.side_effect = [_reply("correct"), _reply("correct")]
        graded = await score_cases([_case("A", "correct"), _case("B", "correct")])
    constructive = _metric()
    constructive.a_measure.side_effect = [1.0, ValueError("bad json")]
    constructive.is_successful.side_effect = [True]
    no_reveal = _metric()

    results = await run_grade_rubrics(graded, constructive, no_reveal)

    by_name = {r.name: r for r in results}
    assert (
        by_name["feedback_constructive_and_calibrated"].passes,
        by_name["feedback_constructive_and_calibrated"].evaluated,
    ) == (1, 1)
    assert by_name["feedback_constructive_and_calibrated"].errors == 1


async def test_run_grade_rubrics_when_graded_correct_then_no_reveal_rubric_not_applied() -> None:
    with patch("evals.grade_run.request_grade_completion", new_callable=AsyncMock) as grader:
        grader.side_effect = [_reply("correct"), _reply("partial")]
        graded = await score_cases([_case("A", "correct"), _case("B", "partial")])
    no_reveal = _metric()

    await run_grade_rubrics(graded, _metric(), no_reveal)

    assert no_reveal.a_measure.await_count == 1


async def test_run_grade_rubrics_when_parse_error_then_canned_feedback_not_judged() -> None:
    with patch("evals.grade_run.request_grade_completion", new_callable=AsyncMock) as grader:
        grader.return_value = "not json"
        graded = await score_cases([_case("A", "correct")])
    constructive = _metric()

    results = await run_grade_rubrics(graded, constructive, _metric())

    constructive.a_measure.assert_not_awaited()
    assert all(r.evaluated == 0 for r in results)


async def test_run_grade_eval_when_run_then_report_written_and_judge_guards_called(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(
        "\n".join(_case(f"C{i}", "correct").model_dump_json() for i in range(2)) + "\n", encoding="utf-8"
    )
    with (
        patch("evals.grade_run.request_grade_completion", new_callable=AsyncMock) as grader,
        patch("evals.grade_run.require_judge_configured") as configured,
        patch("evals.grade_run.check_judge_independence") as independence,
        patch("evals.grade_run.build_constructive_metric", return_value=_metric()),
        patch("evals.grade_run.build_no_reveal_metric", return_value=_metric()),
    ):
        grader.return_value = _reply("correct")
        result = await run_grade_eval(dataset, out_dir=tmp_path / "reports")

    configured.assert_called_once()
    independence.assert_called_once_with("grade_open_answer")
    assert len(result.graded) == 2
    text = result.report_path.read_text(encoding="utf-8")
    assert "## Accuracy" in text
    assert "feedback_constructive_and_calibrated" in text


def test_dataset_path_when_resolved_then_points_at_shipped_grade_dataset() -> None:
    assert DATASET_PATH.name == "grade_open_answer.jsonl"
    assert DATASET_PATH.exists()
