"""Live bank-generation eval orchestration (T10 slice 8).

Generate through the production path (``evals.question_generation``), run the deterministic checks on
EVERY MCQ and the judge rubrics on a seeded per-spec sample (cost bound), attach each rubric's stored
calibration status, and write the report. Quality figures are report-only (SD-8).

Rubric verdicts come from ``calibration_run.build_evaluators``, which checks ``metric.indeterminate``
explicitly. ``grade_run.measure_observed_pass`` must NOT be used for rubric metrics: it would score an
unparseable judge reply as a fail. Indeterminate is never a pass. Router exceptions propagate.
"""

import asyncio
import random
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import structlog

from app.ai.eval_metrics import Rate, rate
from evals.calibration import (
    DEFAULT_CALIBRATION_DIR,
    CalibrationResult,
    calibration_status,
    load_calibration,
)
from evals.calibration_run import CONCURRENCY, Evaluator, build_criterion_hashes, build_evaluators
from evals.deterministic_checks import (
    CheckResult,
    check_answer_not_in_stem,
    check_no_compliance_language,
    check_no_duplicate_questions_in_set,
    check_rendering_safe,
    check_self_contained,
    check_stem_opener_variety,
    check_true_false_share,
    check_unique_options,
    summarise_key_distribution,
)
from evals.judge import RouterJudge, check_judge_independence, require_judge_configured
from evals.question_generation import BANK_TASK, SPECS_PATH, BankOutcome, generate_bank_outcome, load_generation_specs
from evals.question_model import EvalQuestion
from evals.question_report import (
    GenerationSummary,
    RubricLine,
    render_generation_report,
    write_generation_report,
)
from evals.question_rubrics import (
    BLIND_SOLVE_SPEC,
    DISTRACTOR_PLAUSIBILITY_SPEC,
    EXACTLY_ONE_CORRECT_SPEC,
    GRADE_CALIBRATION_SPEC,
    OBJECTIVE_ALIGNMENT_SPEC,
    explanation_spec,
    understanding_spec,
)
from evals.report import utc_timestamp

logger = structlog.get_logger()

JUDGED_PER_SPEC = 6
SAMPLE_SEED = "bank-generation-v1"
_PER_QUESTION_CHECKS: dict[str, Callable[[EvalQuestion], CheckResult]] = {
    "unique_options": check_unique_options,
    "self_contained": check_self_contained,
    "rendering_safe": check_rendering_safe,
    "no_compliance_language": check_no_compliance_language,
    "answer_not_in_stem": check_answer_not_in_stem,
}


@dataclass(frozen=True)
class RubricTally:
    passes: int = 0
    fails: int = 0
    indeterminate: int = 0


@dataclass(frozen=True)
class BankRunResult:
    outcomes: list[BankOutcome]
    summary: GenerationSummary
    report_path: Path


def sample_for_judging(outcomes: Sequence[BankOutcome]) -> list[EvalQuestion]:
    """Seeded, reproducible sample of at most ``JUDGED_PER_SPEC`` MCQs per spec (cost bound)."""
    sample: list[EvalQuestion] = []
    for outcome in outcomes:
        rng = random.Random(f"{SAMPLE_SEED}:{outcome.spec_id}")
        pool = list(outcome.questions)
        sample.extend(rng.sample(pool, min(JUDGED_PER_SPEC, len(pool))))
    return sample


def rubric_criteria(question: EvalQuestion) -> list[str]:
    """Rubric ids that apply to a bank MCQ; R6 and R7 are parameterised by band and path (T10 D7)."""
    return [
        BLIND_SOLVE_SPEC.id,
        EXACTLY_ONE_CORRECT_SPEC.id,
        DISTRACTOR_PLAUSIBILITY_SPEC.id,
        OBJECTIVE_ALIGNMENT_SPEC.id,
        GRADE_CALIBRATION_SPEC.id,
        understanding_spec(question.difficulty_band).id,
        explanation_spec("bank").id,
    ]


async def score_rubrics(
    questions: Sequence[EvalQuestion],
    evaluators: Mapping[str, Evaluator],
    criteria_for: Callable[[EvalQuestion], list[str]] = rubric_criteria,
) -> dict[str, RubricTally]:
    """Run every applicable rubric on every question with bounded concurrency."""
    gate = asyncio.Semaphore(CONCURRENCY)

    async def one(question: EvalQuestion, criterion: str) -> tuple[str, bool | None]:
        async with gate:
            return criterion, await evaluators[criterion](question)

    results = await asyncio.gather(*(one(q, c) for q in questions for c in criteria_for(q)))
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for criterion, observed in results:
        counts[criterion]["indeterminate" if observed is None else "passes" if observed else "fails"] += 1
    return {c: RubricTally(n["passes"], n["fails"], n["indeterminate"]) for c, n in sorted(counts.items())}


def _status(criterion: str, hashes: Mapping[str, str], calibration_dir: Path) -> str:
    stored = load_calibration(criterion, hashes[criterion], calibration_dir)
    if isinstance(stored, CalibrationResult):
        return calibration_status(stored, stored.subset).value
    return stored.value


def rubric_lines(
    tallies: Mapping[str, RubricTally], hashes: Mapping[str, str], calibration_dir: Path = DEFAULT_CALIBRATION_DIR
) -> list[RubricLine]:
    return [
        RubricLine(
            criterion,
            rate(t.passes, t.passes + t.fails),
            rate(t.indeterminate, t.passes + t.fails + t.indeterminate),
            _status(criterion, hashes, calibration_dir),
        )
        for criterion, t in tallies.items()
    ]


def summarise_bank(outcomes: Sequence[BankOutcome], rubrics: Sequence[RubricLine]) -> GenerationSummary:
    questions = [q for o in outcomes for q in o.questions]
    true_false = sum(o.true_false_count for o in outcomes)
    schema_failed = sum(len(o.schema_failures) for o in outcomes)
    results = {q.id: [check(q) for check in _PER_QUESTION_CHECKS.values()] for q in questions}
    deterministic: dict[str, Rate] = {
        name: rate(sum(check(q).passed for q in questions), len(questions))
        for name, check in _PER_QUESTION_CHECKS.items()
    }
    usable = [o for o in outcomes if o.questions]
    set_checks: dict[str, list[CheckResult]] = {
        "no_duplicate_questions_in_set": [check_no_duplicate_questions_in_set(o.questions) for o in usable],
        "stem_opener_variety": [check_stem_opener_variety(o.questions) for o in usable],
        "true_false_share": [
            check_true_false_share(true_false_count=o.true_false_count, total=len(o.questions) + o.true_false_count)
            for o in usable
        ],
    }
    deterministic.update({name: rate(sum(r.passed for r in rs), len(rs)) for name, rs in set_checks.items()})
    per_subject: dict[str, Rate] = {}
    for subject in sorted({q.subject_code for q in questions}):
        own = [q for q in questions if q.subject_code == subject]
        per_subject[subject] = rate(sum(all(r.passed for r in results[q.id]) for q in own), len(own))
    keys = summarise_key_distribution(questions)
    return GenerationSummary(
        path="bank",
        specs=len(outcomes),
        structural=dict(Counter(o.status for o in outcomes)),
        mcq=len(questions),
        true_false=true_false,
        schema_failures=rate(schema_failed, len(questions) + schema_failed),
        deterministic=deterministic,
        key_counts=keys.counts,
        key_max_share=keys.max_share,
        rubrics=list(rubrics),
        per_subject=per_subject,
    )


async def run_bank_generation_eval(
    specs_path: Path = SPECS_PATH, out_dir: Path | None = None, calibration_dir: Path = DEFAULT_CALIBRATION_DIR
) -> BankRunResult:
    """Full live run. Guards first: no generation call is made if the judge is missing or not independent."""
    require_judge_configured()
    check_judge_independence(BANK_TASK)
    specs = load_generation_specs(specs_path)
    run_id = str(uuid.uuid4())
    gate = asyncio.Semaphore(CONCURRENCY)

    async def generate(spec_index: int) -> BankOutcome:
        async with gate:
            return await generate_bank_outcome(specs[spec_index], run_id)

    outcomes = list(await asyncio.gather(*(generate(i) for i in range(len(specs)))))
    evaluators = build_evaluators(RouterJudge(run_id=run_id))
    tallies = await score_rubrics(sample_for_judging(outcomes), evaluators)
    lines = rubric_lines(tallies, build_criterion_hashes(), calibration_dir)
    summary = summarise_bank(outcomes, lines)
    timestamp = utc_timestamp()
    path = write_generation_report(render_generation_report(summary, timestamp), "bank", out_dir, timestamp)
    logger.info("eval_bank_generation_complete", specs=len(specs), mcq=summary.mcq, report=str(path))
    return BankRunResult(outcomes=outcomes, summary=summary, report_path=path)
