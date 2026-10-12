"""Deterministic metrics for the grade_open_answer evaluation.

Pure logic over ``GradeOutcome`` records (no I/O, no judge call). Only ``GradeMatchMetric`` touches
DeepEval, so the exact-match score shows up in DeepEval's own reports.

Labels in the dataset are model-authored and unvalidated, so every figure here measures agreement
with those labels, not correctness.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from app.ai.eval_metrics import Rate, rate
from evals.loader import GRADES

PARSE_ERROR_KEY = "parse_error"


@dataclass(frozen=True)
class GradeOutcome:
    """One graded case: the label, what the production path predicted, and parser flags."""

    case_id: str
    expected: str
    predicted: str
    parse_error: bool
    grade_recognised: bool
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class GradeSummary:
    """All headline grading rates. Each is a ``Rate`` so its n and interval always travel with it."""

    total: int
    # Over cases with NO parse error: a parse failure is not a wrong grade, it is no grade.
    accuracy: Rate
    # Over ALL cases; deliberately never folded into accuracy.
    parse_failure_rate: Rate
    # Valid JSON carrying a grade outside correct/partial/incorrect, over parseable replies only.
    unrecognised_grade_rate: Rate
    # expected=incorrect predicted=correct, over all expected=incorrect (inflates mastery).
    false_credit_rate: Rate
    # expected=correct predicted=incorrect, over all expected=correct (discourages the student).
    false_denial_rate: Rate
    confusion: dict[tuple[str, str], int]
    # Accuracy per tag over parseable cases; a case with several tags counts once under each.
    per_tag_accuracy: dict[str, Rate]


def confusion_matrix(outcomes: Sequence[GradeOutcome]) -> dict[tuple[str, str], int]:
    """Counts keyed ``(expected, predicted)``; every grade pair is present, zero when unseen."""
    counts = Counter((o.expected, o.predicted) for o in outcomes)
    return {(e, p): counts.get((e, p), 0) for e in GRADES for p in GRADES}


def render_confusion_matrix(matrix: dict[tuple[str, str], int]) -> str:
    """Markdown table: rows are expected grades, columns are predicted grades."""
    lines = ["| expected \\ predicted | " + " | ".join(GRADES) + " |", "|---|" + "---|" * len(GRADES)]
    for e in GRADES:
        lines.append(f"| {e} | " + " | ".join(str(matrix.get((e, p), 0)) for p in GRADES) + " |")
    return "\n".join(lines)


def _accuracy(outcomes: Sequence[GradeOutcome]) -> Rate:
    parseable = [o for o in outcomes if not o.parse_error]
    return rate(sum(1 for o in parseable if o.predicted == o.expected), len(parseable))


def _confusion_rate(outcomes: Sequence[GradeOutcome], expected: str, predicted: str) -> Rate:
    pool = [o for o in outcomes if o.expected == expected]
    return rate(sum(1 for o in pool if o.predicted == predicted), len(pool))


def summarise_grades(outcomes: Sequence[GradeOutcome]) -> GradeSummary:
    """Summarise outcomes; empty input yields zero-denominator rates with the full [0, 1] interval."""
    tags = sorted({t for o in outcomes for t in o.tags})
    return GradeSummary(
        total=len(outcomes),
        accuracy=_accuracy(outcomes),
        parse_failure_rate=rate(sum(1 for o in outcomes if o.parse_error), len(outcomes)),
        # Denominator is parseable replies only: a parse failure cannot be an "unrecognised grade".
        unrecognised_grade_rate=rate(
            sum(1 for o in outcomes if not o.parse_error and not o.grade_recognised),
            sum(1 for o in outcomes if not o.parse_error),
        ),
        false_credit_rate=_confusion_rate(outcomes, "incorrect", "correct"),
        false_denial_rate=_confusion_rate(outcomes, "correct", "incorrect"),
        confusion=confusion_matrix(outcomes),
        per_tag_accuracy={t: _accuracy([o for o in outcomes if t in o.tags]) for t in tags},
    )


def grade_test_case(outcome: GradeOutcome) -> LLMTestCase:
    """Wrap an outcome for DeepEval: predicted grade is the output, the label is the expectation."""
    return LLMTestCase(
        input=outcome.case_id,
        actual_output=outcome.predicted,
        expected_output=outcome.expected,
        metadata={PARSE_ERROR_KEY: outcome.parse_error},
    )


class GradeMatchMetric(BaseMetric):
    """Exact-match grade metric: 1.0 when predicted equals expected, else 0.0. Makes no judge call."""

    def __init__(self, threshold: float = 1.0) -> None:
        self._pass_threshold: float = threshold
        self.threshold = threshold
        self.score = None
        self.reason = None
        self.success = None
        self.async_mode = False
        self.verbose_mode = False
        self.strict_mode = False
        self.include_reason = True
        self.error = None
        self.evaluation_model = None

    def measure(self, test_case: LLMTestCase, *args: object, **kwargs: object) -> float:
        expected = test_case.expected_output
        predicted = test_case.actual_output
        if (test_case.metadata or {}).get(PARSE_ERROR_KEY):
            self.score = 0.0
            self.reason = f"Parse error: reply was not parseable, so the fallback grade {predicted!r} is not a grade."
        elif predicted == expected:
            self.score = 1.0
            self.reason = f"Predicted grade {predicted!r} matches expected {expected!r}."
        else:
            self.score = 0.0
            self.reason = f"Predicted grade {predicted!r} differs from expected {expected!r}."
        self.success = self.score >= self._pass_threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: object, **kwargs: object) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "Grade Match"
