"""Offline tests for deterministic grading metrics. No network, no LLM, no DB."""

from evals.grade_metrics import (
    GradeMatchMetric,
    GradeOutcome,
    confusion_matrix,
    grade_test_case,
    render_confusion_matrix,
    summarise_grades,
)


def _o(
    case_id: str,
    expected: str,
    predicted: str,
    *,
    parse_error: bool = False,
    recognised: bool = True,
    tags: tuple[str, ...] = (),
) -> GradeOutcome:
    return GradeOutcome(
        case_id=case_id,
        expected=expected,
        predicted=predicted,
        parse_error=parse_error,
        grade_recognised=recognised,
        tags=tags,
    )


def test_summarise_grades_when_all_correct_then_accuracy_one_with_nondegenerate_interval() -> None:
    outcomes = [_o(f"c{i}", "correct", "correct") for i in range(10)]

    summary = summarise_grades(outcomes)

    assert summary.accuracy.point == 1.0
    assert summary.accuracy.high == 1.0
    assert summary.accuracy.low < 1.0


def test_summarise_grades_when_incorrect_predicted_correct_then_false_credit_rate_counts_it() -> None:
    outcomes = [
        _o("a", "incorrect", "correct"),
        _o("b", "incorrect", "incorrect"),
        _o("c", "incorrect", "partial"),
        _o("d", "correct", "correct"),
    ]

    summary = summarise_grades(outcomes)

    assert (summary.false_credit_rate.numerator, summary.false_credit_rate.denominator) == (1, 3)
    assert summary.false_denial_rate.numerator == 0


def test_summarise_grades_when_correct_predicted_incorrect_then_false_denial_counted_separately() -> None:
    outcomes = [
        _o("a", "correct", "incorrect"),
        _o("b", "correct", "correct"),
        _o("c", "incorrect", "incorrect"),
    ]

    summary = summarise_grades(outcomes)

    assert (summary.false_denial_rate.numerator, summary.false_denial_rate.denominator) == (1, 2)
    assert summary.false_credit_rate.numerator == 0
    assert summary.false_credit_rate.denominator == 1


def test_summarise_grades_when_parse_errors_then_excluded_from_accuracy_but_reported() -> None:
    outcomes = [
        _o("a", "correct", "correct"),
        _o("b", "incorrect", "incorrect"),
        _o("c", "incorrect", "incorrect", parse_error=True, recognised=False),
        _o("d", "correct", "incorrect", parse_error=True, recognised=False),
    ]

    summary = summarise_grades(outcomes)

    assert (summary.accuracy.numerator, summary.accuracy.denominator) == (2, 2)
    assert (summary.parse_failure_rate.numerator, summary.parse_failure_rate.denominator) == (2, 4)


def test_summarise_grades_when_unrecognised_grades_then_reported_in_own_rate() -> None:
    outcomes = [
        _o("a", "correct", "correct"),
        _o("b", "incorrect", "incorrect", recognised=False),
        _o("c", "incorrect", "incorrect", parse_error=True, recognised=False),
    ]

    summary = summarise_grades(outcomes)

    assert summary.unrecognised_grade_rate.numerator == 1
    assert summary.unrecognised_grade_rate.denominator == 3
    assert summary.parse_failure_rate.numerator == 1


def test_summarise_grades_when_empty_then_rates_have_full_interval_and_do_not_raise() -> None:
    summary = summarise_grades([])

    for r in (
        summary.accuracy,
        summary.parse_failure_rate,
        summary.unrecognised_grade_rate,
        summary.false_credit_rate,
        summary.false_denial_rate,
    ):
        assert (r.low, r.high) == (0.0, 1.0)
        assert r.denominator == 0
    assert summary.total == 0


def test_confusion_matrix_when_mixed_predictions_then_keyed_by_expected_then_predicted() -> None:
    outcomes = [
        _o("a", "correct", "correct"),
        _o("b", "correct", "partial"),
        _o("c", "correct", "partial"),
        _o("d", "incorrect", "correct"),
    ]

    matrix = confusion_matrix(outcomes)

    assert matrix[("correct", "correct")] == 1
    assert matrix[("correct", "partial")] == 2
    assert matrix[("incorrect", "correct")] == 1
    assert matrix[("partial", "partial")] == 0
    assert "correct" in render_confusion_matrix(matrix)


def test_summarise_grades_when_tags_present_then_per_tag_accuracy_computed() -> None:
    outcomes = [
        _o("a", "incorrect", "correct", tags=("prompt_injection",)),
        _o("b", "incorrect", "incorrect", tags=("prompt_injection", "off_topic")),
        _o("c", "correct", "correct", tags=("off_topic",)),
        _o("d", "correct", "correct"),
    ]

    summary = summarise_grades(outcomes)

    inj = summary.per_tag_accuracy["prompt_injection"]
    off = summary.per_tag_accuracy["off_topic"]
    assert (inj.numerator, inj.denominator) == (1, 2)
    assert (off.numerator, off.denominator) == (2, 2)
    assert set(summary.per_tag_accuracy) == {"prompt_injection", "off_topic"}


def test_grade_match_metric_when_grade_matches_then_score_one_and_successful() -> None:
    metric = GradeMatchMetric()

    score = metric.measure(grade_test_case(_o("a", "partial", "partial")))

    assert score == 1.0
    assert metric.score == 1.0
    assert metric.is_successful()


def test_grade_match_metric_when_grade_differs_then_score_zero_and_reason_names_both_grades() -> None:
    metric = GradeMatchMetric()

    metric.measure(grade_test_case(_o("a", "incorrect", "partial")))

    assert metric.score == 0.0
    assert not metric.is_successful()
    assert metric.reason is not None
    assert "incorrect" in metric.reason and "partial" in metric.reason


def test_grade_match_metric_when_parse_error_then_fails_with_parse_error_reason() -> None:
    metric = GradeMatchMetric()

    metric.measure(grade_test_case(_o("a", "incorrect", "incorrect", parse_error=True, recognised=False)))

    assert metric.score == 0.0
    assert not metric.is_successful()
    assert metric.reason is not None
    assert "parse" in metric.reason.lower()


async def test_grade_match_metric_when_measured_async_then_matches_sync_result() -> None:
    metric = GradeMatchMetric()

    assert await metric.a_measure(grade_test_case(_o("a", "correct", "correct"))) == 1.0
