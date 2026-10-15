"""Live calibration runner (T10 slice 7): schedule, judge, score, persist, report.

Scheduling (cost bound): a clean case runs ALL criteria; a mutated case runs its ``must_fail``
criteria plus its pre-sampled ``must_pass_sample`` (cross-talk). Deterministic checks never touch the
judge. A judge reply that cannot be parsed is indeterminate (``observed_pass=None``), never a pass;
router exceptions propagate. The production ``question_quality`` judge is scored on the same
questions via ``evals.prod_judge``. Quality figures are report-only (SD-8).
"""

import asyncio
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import structlog

from evals.calibration import (
    DEFAULT_CALIBRATION_DIR,
    CalibrationResult,
    CalibrationVerdict,
    save_calibration,
    score_calibration,
)
from evals.calibration_set.build import SHIPPED_PATH, CalibrationCase, load_calibration_cases
from evals.deterministic_checks import (
    CheckResult,
    check_no_compliance_language,
    check_rendering_safe,
    check_self_contained,
    check_unique_options,
)
from evals.judge import RouterJudge, check_judge_independence, require_judge_configured
from evals.prod_judge import map_prod_verdict, prod_verdicts_for_case, run_prod_judge
from evals.question_model import EvalQuestion
from evals.question_report import render_calibration_report, write_calibration_report
from evals.question_rubrics import (
    BLIND_SOLVE_SPEC,
    DISTRACTOR_PLAUSIBILITY_SPEC,
    EXACTLY_ONE_CORRECT_SPEC,
    GRADE_CALIBRATION_SPEC,
    OBJECTIVE_ALIGNMENT_SPEC,
    BlindSolveMetric,
    ExactlyOneCorrectMetric,
    explanation_spec,
    question_case,
    understanding_spec,
)
from evals.report import utc_timestamp
from evals.rubric_core import BinaryRubricMetric, RubricSpec

logger = structlog.get_logger()

# The judge must be independent of every model whose questions it grades or whose judge it audits.
CALIBRATION_JUDGED_TASKS = ("quiz_generation", "question_generation", "question_quality")
CONCURRENCY = 4

Evaluator = Callable[[EvalQuestion], Awaitable[bool | None]]
_RubricMetric = BinaryRubricMetric | BlindSolveMetric | ExactlyOneCorrectMetric
_DETERMINISTIC: dict[str, Callable[[EvalQuestion], CheckResult]] = {
    "unique_options": check_unique_options,
    "self_contained": check_self_contained,
    "rendering_safe": check_rendering_safe,
    "no_compliance_language": check_no_compliance_language,
}
_BINARY_SPECS: tuple[RubricSpec, ...] = (
    DISTRACTOR_PLAUSIBILITY_SPEC,
    OBJECTIVE_ALIGNMENT_SPEC,
    GRADE_CALIBRATION_SPEC,
    understanding_spec("foundational"),
    understanding_spec("developing"),  # same spec id as "advanced": the applied variant
    explanation_spec("bank"),
    explanation_spec("quiz"),
)
_CODE_SCORED_SPECS = (BLIND_SOLVE_SPEC, EXACTLY_ONE_CORRECT_SPEC)


@dataclass(frozen=True)
class CalibrationRunResult:
    verdicts: list[CalibrationVerdict]
    results: dict[str, CalibrationResult]
    prod_results: dict[str, CalibrationResult]
    report_path: Path


def scheduled_criteria(case: CalibrationCase) -> list[tuple[str, bool]]:
    """``(criterion, expected_pass)`` pairs to run for one case."""
    if case.defect is None:
        return [(c, True) for c in case.must_pass]
    return [(c, False) for c in case.must_fail] + [(c, True) for c in case.must_pass_sample]


def _subset(case: CalibrationCase) -> Literal["computed", "authored"]:
    if case.subset == "computed":
        return "computed"
    if case.subset == "authored":
        return "authored"
    raise ValueError(f"unknown calibration subset {case.subset!r} for case {case.case_id}")


def build_criterion_hashes() -> dict[str, str]:
    """Rubrics use their spec hash; deterministic checks have no text, so their name stands in."""
    hashes = {name: name for name in _DETERMINISTIC}
    hashes.update({spec.id: spec.text_hash for spec in (*_CODE_SCORED_SPECS, *_BINARY_SPECS)})
    return hashes


def _check_evaluator(check: Callable[[EvalQuestion], CheckResult]) -> Evaluator:
    async def evaluate(question: EvalQuestion) -> bool | None:
        return check(question).passed

    return evaluate


def _metric_evaluator(make_metric: Callable[[], _RubricMetric]) -> Evaluator:
    # A fresh metric per call: metrics hold per-call verdict state, so sharing one across concurrent
    # calls would let results overwrite each other. ``indeterminate`` is checked explicitly because
    # ``is_successful()`` is False for it too, which would otherwise read as a detected defect.
    async def evaluate(question: EvalQuestion) -> bool | None:
        metric = make_metric()
        await metric.a_measure(question_case(question))
        return None if metric.indeterminate else metric.verdict

    return evaluate


def _binary_factory(spec: RubricSpec, judge: RouterJudge) -> Callable[[], _RubricMetric]:
    return lambda: BinaryRubricMetric(spec, judge)


def build_evaluators(judge: RouterJudge) -> dict[str, Evaluator]:
    evaluators: dict[str, Evaluator] = {name: _check_evaluator(fn) for name, fn in _DETERMINISTIC.items()}
    evaluators[BLIND_SOLVE_SPEC.id] = _metric_evaluator(lambda: BlindSolveMetric(judge))
    evaluators[EXACTLY_ONE_CORRECT_SPEC.id] = _metric_evaluator(lambda: ExactlyOneCorrectMetric(judge))
    for spec in _BINARY_SPECS:
        evaluators[spec.id] = _metric_evaluator(_binary_factory(spec, judge))
    return evaluators


async def run_calibration(
    cases: Sequence[CalibrationCase], evaluators: Mapping[str, Evaluator]
) -> list[CalibrationVerdict]:
    """Run every scheduled (case, criterion) with bounded concurrency; input order is preserved."""
    gate = asyncio.Semaphore(CONCURRENCY)

    async def one(case: CalibrationCase, criterion: str, expected: bool) -> CalibrationVerdict:
        evaluate = evaluators[criterion]
        async with gate:
            observed = await evaluate(case.question)
        return CalibrationVerdict(case.case_id, criterion, case.defect, expected, observed, _subset(case))

    return list(await asyncio.gather(*(one(c, crit, exp) for c in cases for crit, exp in scheduled_criteria(c))))


def score_verdicts(verdicts: Sequence[CalibrationVerdict], hashes: Mapping[str, str]) -> dict[str, CalibrationResult]:
    grouped: dict[str, list[CalibrationVerdict]] = defaultdict(list)
    for verdict in verdicts:
        grouped[verdict.criterion].append(verdict)
    return {criterion: score_calibration(items, hashes[criterion]) for criterion, items in grouped.items()}


async def run_prod_judge_calibration(
    cases: Sequence[CalibrationCase], run_id: str | None = None
) -> list[CalibrationVerdict]:
    """Production judge, one call per case, scored on the criteria scheduled for that case."""
    gate = asyncio.Semaphore(CONCURRENCY)

    async def one(case: CalibrationCase) -> list[CalibrationVerdict]:
        async with gate:
            validations = await run_prod_judge(case.question, run_id)
        return prod_verdicts_for_case(
            case.case_id, case.defect, _subset(case), scheduled_criteria(case), map_prod_verdict(validations)
        )

    return [v for batch in await asyncio.gather(*(one(c) for c in cases)) for v in batch]


async def run_calibration_eval(
    dataset_path: Path = SHIPPED_PATH, out_dir: Path | None = None, calibration_dir: Path = DEFAULT_CALIBRATION_DIR
) -> CalibrationRunResult:
    """Full live run. Guards first: no call is made if the judge is missing or not independent."""
    require_judge_configured()
    for task in CALIBRATION_JUDGED_TASKS:
        check_judge_independence(task)
    cases = load_calibration_cases(dataset_path)
    run_id = str(uuid.uuid4())
    hashes = build_criterion_hashes()
    verdicts = await run_calibration(cases, build_evaluators(RouterJudge(run_id=run_id)))
    results = score_verdicts(verdicts, hashes)
    for result in results.values():
        save_calibration(result, calibration_dir)
    prod_results = score_verdicts(await run_prod_judge_calibration(cases, run_id), hashes)
    timestamp = utc_timestamp()
    path = write_calibration_report(render_calibration_report(results, prod_results, timestamp), out_dir, timestamp)
    logger.info("eval_calibration_complete", cases=len(cases), verdicts=len(verdicts), report=str(path))
    return CalibrationRunResult(verdicts=verdicts, results=results, prod_results=prod_results, report_path=path)
