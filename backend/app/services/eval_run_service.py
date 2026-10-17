"""Production-evaluation runner (MLH-T18 slice 5b-i): sample -> scrub -> check -> judge -> store.

`request_run` validates the admin's settings and creates (or returns) the run for a
(task, window, seed). `execute_run` evaluates it. Neither is a route or a Celery task; slice 5b-ii
wires those on top.

ORDER OF A RUN (each step can end it early)
  1. Refuse to start: task not enabled / student-text acknowledgement missing, or the budget guard
     refuses (budget 0, usage tracking off, no judge, judge unpriced). -> run `failed`.
  2. Sample (seeded, read-only). Nothing sampled -> `empty` plus a WARNING (Rule 17).
  3. Task has no registered evaluators or no `TaskSuite` -> every row counted `skipped_unsupported`.
  4. Drop rows the judge may not grade (own model or vendor) and count them.
  5. Per row, through the task's `TaskSuite` (eval_prod/task_suite.py): prepare the row (else
     `skipped_unsupported`); run the deterministic checks on its STORED form; run the judge rubrics on
     its SCRUBBED form only (the suite scrubs, and only when a rubric will run). If scrubbing fails the
     whole row is skipped and counted: nothing unscrubbed ever reaches the judge.
  6. Each judge call is authorised by the BudgetGuard first. When the next call would exceed the
     budget the run stops as `budget_exhausted` and keeps what it has.

STATUS SEMANTICS. A judge or other evaluation error ends the run `failed` with the exception CLASS
NAME in `error_type` (never the message, which could echo a prompt); results written so far are
kept. `execute_run` does not raise for evaluation errors, so a retry cannot repeat a half-finished
run: re-running means a new seed. A run that is not `pending` is returned untouched (idempotent).

COST ACCOUNTING. The router returns text only, so the guard is charged each call's worst-case
estimate (prompt tokens approximated from its length, a full-length completion), not the actual
cost. That over-counts within a run; the next run's month-to-date read uses the real
`estimated_cost_usd` rows and self-corrects.

NO TEXT IS STORED OR LOGGED. Outcomes are `CheckOutcome`s (ids and verdicts only); log lines carry
ids, counts and class names.
"""

import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.eval.judge_runner import Completion, router_completion
from app.ai.eval.question_checks import PER_QUESTION_CHECKS
from app.ai.eval.question_model import EvalQuestion
from app.ai.eval.question_rubrics import run_question_rubric, understanding_spec
from app.ai.eval.rubric_core import RubricSpec
from app.ai.llm_cost import estimate_cost
from app.core.config import Settings, settings
from app.models.eval_results import EvalRun
from app.services.eval_prod.budget import (
    BudgetExhaustedError,
    BudgetGuard,
    BudgetRefusedError,
    PriceEstimator,
    check_run_can_start,
    estimate_call_cost,
    month_spend_usd,
    unpriced_call_cost,
)
from app.services.eval_prod.grade_evaluators import GRADE_TASK
from app.services.eval_prod.grade_suite import GRADE_SUITE
from app.services.eval_prod.question_adapter import QUESTION_GENERATION_TASK, adapt_event, scrub_question
from app.services.eval_prod.question_evaluators import default_registry
from app.services.eval_prod.registry import (
    KIND_DETERMINISTIC,
    KIND_JUDGE,
    EvaluatorPlan,
    EvaluatorRegistry,
    SelectedEvaluator,
    StatusResolver,
    calibration_status_resolver,
    filter_independent,
    task_enablement_problem,
)
from app.services.eval_prod.sampler import (
    SampledEvent,
    SamplingActor,
    ScrubNames,
    load_scrub_names,
    sample_usage_events,
)
from app.services.eval_prod.scrub import ScrubFailedError
from app.services.eval_prod.task_suite import PreparedRow, ScrubContext, TaskSuite, UnsupportedRow
from app.services.eval_results_service import CheckOutcome, EvalResultsService, RunCounts
from app.services.platform_settings_service import EvalSettings, PlatformSettingsService

logger = structlog.get_logger()

EVAL_PROD_SAMPLE_COMPONENT = "eval_prod_sample"
_CHARS_PER_TOKEN = 4  # rough prompt-size estimate used only for the pre-call cost bound
_R6_PREFIX = "R6_"

CompletionFactory = Callable[[str], Completion]
_REASON_NOT_ADAPTABLE = "event_not_adaptable"


class RunNotAllowedError(ValueError):
    """The task may not be evaluated under the current settings. Safe to show to the admin (422)."""


class ResultsStore(Protocol):
    """Structural type of the persistence calls the runner needs (satisfied by EvalResultsService)."""

    async def get_run(self, run_id: uuid.UUID) -> EvalRun | None: ...

    async def create_run(
        self,
        *,
        task: str,
        window_start: datetime,
        window_end: datetime,
        seed: str,
        trigger: str,
        requested_by: uuid.UUID | None = None,
        include_indicative: bool = False,
    ) -> tuple[EvalRun, bool]: ...

    async def mark_started(self, run_id: uuid.UUID, *, judge_model: str) -> None: ...

    async def finish_run(
        self, run_id: uuid.UUID, *, status: str, counts: RunCounts, spend_usd: Decimal, error_type: str | None = None
    ) -> None: ...

    async def record_results(
        self, run_id: uuid.UUID, usage_event_id: uuid.UUID, outcomes: list[CheckOutcome]
    ) -> int: ...


class SettingsSource(Protocol):
    async def get_eval_settings(self) -> EvalSettings: ...


@dataclass
class _Tally:
    sampled: int = 0
    evaluated: int = 0
    not_independent: int = 0
    scrub_failed: int = 0
    unsupported: int = 0
    unsupported_reasons: Counter[str] = field(default_factory=Counter)

    def count_unsupported(self, reason: str) -> None:
        self.unsupported += 1
        self.unsupported_reasons[reason] += 1

    def counts(self) -> RunCounts:
        return RunCounts(
            sampled=self.sampled,
            evaluated=self.evaluated,
            skipped_not_independent=self.not_independent,
            skipped_scrub_failed=self.scrub_failed,
            skipped_unsupported=self.unsupported,
        )


def _production_completion(run_id: str) -> Completion:
    return router_completion(run_id=run_id, component=EVAL_PROD_SAMPLE_COMPONENT)


def scheduled_window_and_seed(now: datetime, *, window_days: int) -> tuple[datetime, datetime, str]:
    """Window and seed for a scheduled run, stable within one UTC day so a repeat is the same run."""
    end = datetime(now.year, now.month, now.day, tzinfo=UTC)
    return end - timedelta(days=window_days), end, f"scheduled-{end.date().isoformat()}"


def _rubric_applies(spec: RubricSpec, question: EvalQuestion) -> bool:
    """R6 has two registered variants; only the one for the question's difficulty band runs."""
    return not spec.id.startswith(_R6_PREFIX) or spec.id == understanding_spec(question.difficulty_band).id


def _prepare_question(
    event: SampledEvent, seed: str, scrub: ScrubContext | None
) -> PreparedRow[EvalQuestion, EvalQuestion] | UnsupportedRow:
    question = adapt_event(event, seed=seed)
    if question is None:
        return UnsupportedRow(_REASON_NOT_ADAPTABLE)
    if scrub is None:
        return PreparedRow(stored=question, scrubbed=None)
    scrubbed = scrub_question(question, person_names=scrub.person_names, school_name=scrub.school_name)
    return PreparedRow(stored=question, scrubbed=scrubbed)


async def _run_question_rubric(spec: RubricSpec, question: EvalQuestion, completion: Completion) -> bool | None:
    return (await run_question_rubric(spec, question, completion)).verdict


_QUESTION_SUITE: TaskSuite[EvalQuestion, EvalQuestion] = TaskSuite(
    prepare=_prepare_question,
    deterministic=lambda name, question: PER_QUESTION_CHECKS[name](question).passed,
    rubric_applies=_rubric_applies,
    run_rubric=_run_question_rubric,
)
# Router task -> its suite. A task without one has no runnable suite (its rows count as unsupported).
_SUITES: dict[str, TaskSuite[Any, Any]] = {QUESTION_GENERATION_TASK: _QUESTION_SUITE, GRADE_TASK: GRADE_SUITE}


class EvalRunService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        config: Settings = settings,
        registry: EvaluatorRegistry | None = None,
        status_of: StatusResolver | None = None,
        completion_factory: CompletionFactory | None = None,
        price_estimator: PriceEstimator = estimate_cost,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        results: ResultsStore | None = None,
        platform_settings: SettingsSource | None = None,
    ) -> None:
        self._db = db
        self._config = config
        self._registry = registry or default_registry()
        self._status_of = status_of or calibration_status_resolver(config.eval_calibration_dir)
        self._completion_factory = completion_factory or _production_completion
        self._price_estimator = price_estimator
        self._clock = clock
        self._results: ResultsStore = results or EvalResultsService(db)
        self._platform: SettingsSource = platform_settings or PlatformSettingsService(db)

    async def request_run(
        self,
        *,
        task: str,
        window_start: datetime,
        window_end: datetime,
        seed: str,
        trigger: str,
        requested_by: uuid.UUID | None = None,
    ) -> tuple[EvalRun, bool]:
        """Create the run for (task, window, seed), or return the existing one: `(run, created)`.

        Raises RunNotAllowedError when the task is not enabled or lacks its student-text
        acknowledgement (D5). Snapshots the admin's `include_indicative` onto the run.
        """
        eval_settings = await self._platform.get_eval_settings()
        problem = task_enablement_problem(task, eval_settings)
        if problem:
            raise RunNotAllowedError(problem)
        return await self._results.create_run(
            task=task,
            window_start=window_start,
            window_end=window_end,
            seed=seed,
            trigger=trigger,
            requested_by=requested_by,
            include_indicative=eval_settings.include_indicative,
        )

    async def execute_run(self, run_id: uuid.UUID, actor: SamplingActor) -> EvalRun:
        """Evaluate a pending run and return it in its terminal state. Writes results; calls the judge.

        Non-pending runs are returned as they are. Raises LookupError if the run does not exist.
        """
        run = await self._results.get_run(run_id)
        if run is None:
            raise LookupError(f"eval run {run_id} not found")
        if run.status != "pending":
            return run
        eval_settings = await self._platform.get_eval_settings()
        judge_model = self._config.llm_eval_judge_model
        try:
            problem = task_enablement_problem(run.task, eval_settings)
            if problem:
                raise RunNotAllowedError(problem)
            check_run_can_start(
                monthly_budget_usd=eval_settings.monthly_budget_usd,
                tracking_enabled=self._config.llm_usage_tracking_enabled,
                judge_model=judge_model,
                price_estimator=self._price_estimator,
            )
        except (RunNotAllowedError, BudgetRefusedError) as exc:
            logger.warning("eval_run.refused", run_id=str(run_id), task=run.task, reason=str(exc))
            return await self._finish(run_id, "failed", _Tally(), Decimal("0"), type(exc).__name__)

        await self._results.mark_started(run_id, judge_model=judge_model)
        unpriced = unpriced_call_cost(self._config)
        guard = BudgetGuard(
            eval_settings.monthly_budget_usd,
            month_spent_usd=await month_spend_usd(self._db, self._clock(), unpriced),
            unpriced_call_cost_usd=unpriced,
        )
        tally = _Tally()
        status, error_type = "completed", None
        try:
            status = await self._evaluate(run, actor, eval_settings, guard, unpriced, tally)
        except BudgetExhaustedError:
            status = "budget_exhausted"
        except Exception as exc:  # recorded as a failed run; only the class name is kept (see docstring)
            status, error_type = "failed", type(exc).__name__
            logger.error("eval_run.evaluation_failed", run_id=str(run_id), task=run.task, error_type=error_type)
        return await self._finish(run_id, status, tally, guard.run_spend_usd, error_type)

    async def _finish(
        self, run_id: uuid.UUID, status: str, tally: _Tally, spend: Decimal, error_type: str | None
    ) -> EvalRun:
        await self._results.finish_run(
            run_id, status=status, counts=tally.counts(), spend_usd=spend, error_type=error_type
        )
        finished = await self._results.get_run(run_id)
        if finished is None:
            raise LookupError(f"eval run {run_id} not found")
        return finished

    async def _evaluate(
        self,
        run: EvalRun,
        actor: SamplingActor,
        eval_settings: EvalSettings,
        guard: BudgetGuard,
        unpriced: Decimal,
        tally: _Tally,
    ) -> str:
        judge_model = self._config.llm_eval_judge_model
        events = await sample_usage_events(
            self._db,
            actor=actor,
            tasks=[run.task],
            window_start=run.window_start,
            window_end=run.window_end,
            limit_per_task=eval_settings.sample_size_per_task,
            seed=run.seed,
        )
        tally.sampled = len(events)
        if not events:
            logger.warning("eval_run.empty_sample", run_id=str(run.id), task=run.task)
            return "empty"
        plan = self._registry.plan_for(run.task, include_indicative=run.include_indicative, status_of=self._status_of)
        suite = _SUITES.get(run.task)
        if not plan.supported or suite is None:
            tally.unsupported = len(events)
            return "completed"
        split = filter_independent(events, judge_model)
        tally.not_independent = split.skipped_not_independent
        school_ids = {event.school_id for event in split.kept if event.school_id is not None}
        names = await load_scrub_names(self._db, actor, school_ids)
        completion = self._metered(self._completion_factory(str(run.id)), guard, judge_model, unpriced)
        for event in split.kept:
            await self._evaluate_event(run, event, suite, plan, names, completion, tally)
        if tally.unsupported_reasons:
            logger.info("eval_run.rows_unsupported", run_id=str(run.id), reasons=dict(tally.unsupported_reasons))
        return "completed"

    def _metered(self, inner: Completion, guard: BudgetGuard, judge_model: str, unpriced: Decimal) -> Completion:

        async def completion(prompt: str) -> str:
            estimate = estimate_call_cost(
                judge_model,
                len(prompt) // _CHARS_PER_TOKEN + 1,
                unpriced_cost_usd=unpriced,
                price_estimator=self._price_estimator,
            )
            guard.authorize(estimate)  # raises BudgetExhaustedError before the call is made
            reply = await inner(prompt)
            guard.record(estimate)
            return reply

        return completion

    async def _evaluate_event(
        self,
        run: EvalRun,
        event: SampledEvent,
        suite: TaskSuite[Any, Any],
        plan: EvaluatorPlan,
        names: dict[uuid.UUID, ScrubNames],
        completion: Completion,
        tally: _Tally,
    ) -> None:
        scrub: ScrubContext | None = None
        if any(selected.evaluator.kind == KIND_JUDGE for selected in plan.selected):
            school_names = names.get(event.school_id) if event.school_id is not None else None
            scrub = ScrubContext(
                person_names=school_names.person_names if school_names else (),
                school_name=school_names.school_name if school_names else None,
            )
        try:
            row = suite.prepare(event, run.seed, scrub)
        except ScrubFailedError:
            tally.scrub_failed += 1
            return
        if isinstance(row, UnsupportedRow):
            tally.count_unsupported(row.reason)
            return
        outcomes: list[CheckOutcome] = []
        try:
            for selected in plan.selected:
                outcome = await self._check(selected, suite, row, completion)
                if outcome is not None:
                    outcomes.append(outcome)
            tally.evaluated += 1
        finally:
            # Partial outcomes are kept when the budget runs out or the judge fails mid-row.
            if outcomes:
                await self._results.record_results(run.id, event.id, outcomes)

    @staticmethod
    async def _check(
        selected: SelectedEvaluator, suite: TaskSuite[Any, Any], row: PreparedRow[Any, Any], completion: Completion
    ) -> CheckOutcome | None:
        evaluator = selected.evaluator
        if evaluator.kind == KIND_DETERMINISTIC:
            # Runs locally on the stored form, so it needs no scrubbing (and scrub tokens would distort it).
            passed = suite.deterministic(evaluator.name, row.stored)
            return None if passed is None else CheckOutcome(evaluator.name, KIND_DETERMINISTIC, passed)
        if evaluator.rubric is None or row.scrubbed is None or not suite.rubric_applies(evaluator.rubric, row.scrubbed):
            return None
        verdict = await suite.run_rubric(evaluator.rubric, row.scrubbed, completion)
        # verdict None = unusable judge reply: stored as indeterminate, never a pass.
        return CheckOutcome(evaluator.name, KIND_JUDGE, verdict, selected.rubric_hash, selected.rubric_status)
