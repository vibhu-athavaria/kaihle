"""Run orchestrator for the grade_open_answer evaluation (T9 slice 6).

Pipeline per case, on the exact production path: ``render_grade_prompt`` -> ``request_grade_completion``
-> ``parse_grade_response``. Outcomes feed the deterministic grade metrics; the model's feedback text
then goes to the two G-Eval rubrics; everything is written to a gitignored Markdown report.

Failure policy: grader or router exceptions PROPAGATE (a swallowed failure would fabricate a score).
The one exception caught is GEval's ``ValueError`` for an unparseable judge reply, which is counted as
indeterminate (``observed_pass=None``) and is never a pass.
"""

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import structlog
from deepeval.test_case import LLMTestCase

from app.services.mini_course_service import (
    GradeParse,
    parse_grade_response,
    render_grade_prompt,
    request_grade_completion,
)
from evals.grade_metrics import GradeOutcome, GradeSummary, summarise_grades
from evals.judge import RouterJudge, check_judge_independence, require_judge_configured
from evals.loader import GradeCase, load_grade_cases
from evals.report import GRADED_TASK, RubricResult, build_run_meta, render_report, write_report
from evals.rubrics import (
    CONSTRUCTIVE_NAME,
    NO_REVEAL_NAME,
    build_constructive_metric,
    build_feedback_test_case,
    build_no_reveal_metric,
    reveal_rubric_applies,
)

logger = structlog.get_logger()

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "grade_open_answer.jsonl"


class JudgeUnusableError(RuntimeError):
    """Every verdict for a rubric was indeterminate: the judge or its prompt is broken, not the grader."""


class FeedbackMetric(Protocol):
    """The slice of a DeepEval metric the orchestrator uses; lets tests pass fakes."""

    async def a_measure(self, test_case: LLMTestCase) -> float: ...

    def is_successful(self) -> bool | None: ...


@dataclass(frozen=True)
class GradedCase:
    case: GradeCase
    parse: GradeParse
    outcome: GradeOutcome


@dataclass(frozen=True)
class GradeRunResult:
    graded: list[GradedCase]
    summary: GradeSummary
    rubric_results: list[RubricResult]
    report_path: Path


async def score_cases(cases: list[GradeCase]) -> list[GradedCase]:
    """Grade every case through the production prompt, completion call and parser, in order."""
    graded: list[GradedCase] = []
    for case in cases:
        prompt = render_grade_prompt(
            case.subtopic_name, case.learning_objective, case.question_text, case.student_answer
        )
        parse = parse_grade_response(await request_grade_completion(prompt))
        outcome = GradeOutcome(
            case_id=case.id,
            expected=case.expected_grade,
            predicted=parse.grade,
            parse_error=parse.parse_error,
            grade_recognised=parse.grade_recognised,
            tags=tuple(case.tags),
        )
        graded.append(GradedCase(case=case, parse=parse, outcome=outcome))
    return graded


async def measure_observed_pass(metric: FeedbackMetric, test_case: LLMTestCase) -> bool | None:
    """True/False from the metric, or None when the judge reply was unparseable (never a pass)."""
    try:
        await metric.a_measure(test_case)
    except ValueError as exc:
        logger.warning("eval_rubric_indeterminate", error=str(exc))
        return None
    return metric.is_successful() is True


async def _rubric_result(name: str, metric: FeedbackMetric, test_cases: list[LLMTestCase]) -> RubricResult:
    verdicts = [await measure_observed_pass(metric, tc) for tc in test_cases]
    decided = [v for v in verdicts if v is not None]
    return RubricResult(
        name=name, passes=sum(1 for v in decided if v), evaluated=len(decided), errors=len(verdicts) - len(decided)
    )


async def run_grade_rubrics(
    graded: list[GradedCase], constructive: FeedbackMetric, no_reveal: FeedbackMetric
) -> list[RubricResult]:
    """Run both feedback rubrics. Parse-error cases are skipped: their feedback is canned, not the model's.

    The no-reveal rubric applies only to partial/incorrect grades as predicted by the grader.
    """
    judged = [g for g in graded if not g.parse.parse_error]
    cases = [
        (g, build_feedback_test_case(g.case.question_text, g.case.student_answer, g.parse.grade, g.parse.feedback))
        for g in judged
    ]
    return [
        await _rubric_result(CONSTRUCTIVE_NAME, constructive, [tc for _, tc in cases]),
        await _rubric_result(
            NO_REVEAL_NAME, no_reveal, [tc for g, tc in cases if reveal_rubric_applies(g.parse.grade)]
        ),
    ]


def require_some_verdicts(rubric_results: list[RubricResult]) -> None:
    """Fail loudly when a rubric had inputs but not one usable verdict, instead of reporting all-errors."""
    unusable = [r.name for r in rubric_results if r.evaluated == 0 and r.errors > 0]
    if unusable:
        raise JudgeUnusableError(f"judge returned no usable verdict for: {', '.join(unusable)}")


async def run_grade_eval(dataset_path: Path = DATASET_PATH, out_dir: Path | None = None) -> GradeRunResult:
    """Full run: guards, grade, summarise, rubrics, write report. Raises if the judge is unusable."""
    require_judge_configured()
    check_judge_independence(GRADED_TASK)
    cases = load_grade_cases(dataset_path)
    graded = await score_cases(cases)
    summary = summarise_grades([g.outcome for g in graded])
    judge = RouterJudge(run_id=str(uuid.uuid4()))
    rubric_results = await run_grade_rubrics(graded, build_constructive_metric(judge), build_no_reveal_metric(judge))
    require_some_verdicts(rubric_results)
    path = write_report(render_report(summary, build_run_meta(dataset_path), rubric_results), out_dir=out_dir)
    logger.info("eval_grade_run_complete", cases=len(graded), report=str(path))
    return GradeRunResult(graded=graded, summary=summary, rubric_results=rubric_results, report_path=path)
