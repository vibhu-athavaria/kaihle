"""Budget guard for production evaluation (MLH-T18 slice 4, decisions D2 and D3).

Fail-closed and conservative: nothing runs while the admin-set monthly budget is 0, while
`LLM_USAGE_TRACKING_ENABLED` is off (no cost rows to account against), or while the judge model
has no price. A call with an unknown cost is charged at `EVAL_UNPRICED_CALL_COST_USD`, never zero.

HOW THE NUMBERS FIT TOGETHER
  * Month-to-date spend is read ONCE at run start from `llm_usage_events` (components
    `eval_prod_%`, current UTC calendar month; NULL costs counted at the unpriced cost). The run's
    own judge calls land in that table too, but they are added AFTER the read, so the guard tracks
    them in memory (`run_spend_usd`) instead of re-reading - no double counting.
  * `authorize()` runs BEFORE every judge call with that call's cost estimate; `record()` runs
    after it with the actual cost (None = unpriced). When `spent + estimate > budget` the run
    stops, keeps its partial results and is finished as `budget_exhausted`.
  * Two runs overlapping in time can each see the same month-to-date figure, so the guard can
    overshoot by up to one run's remaining allowance. Acceptable for a soft monthly cap on a
    single-admin tool; recorded rather than hidden.

Pure logic plus one read-only query. No prompt or response text is ever touched here.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.eval.judge_config import JUDGE_MAX_TOKENS
from app.ai.eval.judge_guards import JUDGE_UNSET_MESSAGE
from app.ai.llm_cost import estimate_cost
from app.core.config import Settings
from app.models.llm_usage import LlmUsageEvent
from app.services.eval_results_service import EvalResultsService, RunCounts

logger = structlog.get_logger()

EVAL_PROD_COMPONENT_PREFIX = "eval_prod_"
# Token count used only to probe whether the judge model HAS a price; the figure is not spent.
_PRICE_PROBE_TOKENS = 1000

PriceEstimator = Callable[[str, int | None, int | None], Decimal | None]


class BudgetRefusedError(RuntimeError):
    """The run must not start. The message is safe to show to the admin."""


class BudgetExhaustedError(RuntimeError):
    """The next judge call would exceed the monthly budget; the run should stop."""


class BudgetConfigError(ValueError):
    """`EVAL_UNPRICED_CALL_COST_USD` is not a usable non-negative finite number."""


def month_bounds(now: datetime) -> tuple[datetime, datetime]:
    """[start, end) of the UTC calendar month containing ``now``."""
    if now.tzinfo is None:
        raise ValueError("month_bounds needs a timezone-aware datetime")
    moment = now.astimezone(UTC)
    start = datetime(moment.year, moment.month, 1, tzinfo=UTC)
    end = datetime(moment.year + (moment.month == 12), moment.month % 12 + 1, 1, tzinfo=UTC)
    return start, end


def unpriced_call_cost(config: Settings) -> Decimal:
    """Cost charged for a call with no known price. Raises BudgetConfigError if unusable.

    Warns when the value was not set explicitly: the built-in default is deliberately high, so a
    deployment that forgot the env var over-counts spend rather than under-counting it.
    """
    raw = config.eval_unpriced_call_cost_usd
    try:
        value = Decimal(str(raw))
    except InvalidOperation as exc:
        raise BudgetConfigError("EVAL_UNPRICED_CALL_COST_USD must be a number") from exc
    if not value.is_finite() or value < 0:
        raise BudgetConfigError("EVAL_UNPRICED_CALL_COST_USD must be a finite number >= 0")
    if "eval_unpriced_call_cost_usd" not in config.model_fields_set:
        logger.warning("eval_unpriced_call_cost_default_in_use", cost_usd=str(value))
    return value


def check_run_can_start(
    *,
    monthly_budget_usd: Decimal,
    tracking_enabled: bool,
    judge_model: str,
    price_estimator: PriceEstimator = estimate_cost,
) -> None:
    """Raise BudgetRefusedError, with the reason, unless a run may start (D2, D3)."""
    if not judge_model:
        raise BudgetRefusedError(JUDGE_UNSET_MESSAGE)
    if monthly_budget_usd <= 0:
        raise BudgetRefusedError("The monthly evaluation budget is 0; set a budget in Quality settings to run.")
    if not tracking_enabled:
        raise BudgetRefusedError(
            "LLM_USAGE_TRACKING_ENABLED is false, so spend cannot be measured; enable it to run evaluations."
        )
    if price_estimator(judge_model, _PRICE_PROBE_TOKENS, _PRICE_PROBE_TOKENS) is None:
        raise BudgetRefusedError(
            "The judge model has no price (not in LiteLLM's table or the price override file); "
            "add one so spend can be budgeted."
        )


def estimate_call_cost(
    judge_model: str,
    prompt_tokens: int,
    *,
    unpriced_cost_usd: Decimal,
    price_estimator: PriceEstimator = estimate_cost,
) -> Decimal:
    """Worst-case cost of one judge call: the prompt as given plus a full-length completion."""
    priced = price_estimator(judge_model, prompt_tokens, JUDGE_MAX_TOKENS)
    return unpriced_cost_usd if priced is None else priced


async def month_spend_usd(db: AsyncSession, now: datetime, unpriced_cost_usd: Decimal) -> Decimal:
    """Read-only: evaluation spend so far this UTC month (NULL costs counted at the unpriced cost)."""
    start, end = month_bounds(now)
    total = await db.scalar(
        select(func.coalesce(func.sum(func.coalesce(LlmUsageEvent.estimated_cost_usd, unpriced_cost_usd)), 0)).where(
            LlmUsageEvent.component.startswith(EVAL_PROD_COMPONENT_PREFIX, autoescape=True),
            LlmUsageEvent.created_at >= start,
            LlmUsageEvent.created_at < end,
        )
    )
    return Decimal(total or 0)


class BudgetGuard:
    """In-memory budget accounting for one run. Not thread-safe; one instance per run."""

    def __init__(
        self, monthly_budget_usd: Decimal, *, month_spent_usd: Decimal, unpriced_call_cost_usd: Decimal
    ) -> None:
        self._budget = monthly_budget_usd
        self._month_spent = month_spent_usd
        self._unpriced = unpriced_call_cost_usd
        self._run_spend = Decimal("0")

    @property
    def run_spend_usd(self) -> Decimal:
        """Spend of this run only; the value stored in `eval_runs.spend_usd`."""
        return self._run_spend

    @property
    def remaining_usd(self) -> Decimal:
        return max(self._budget - self._month_spent - self._run_spend, Decimal("0"))

    def authorize(self, estimated_cost_usd: Decimal) -> None:
        """Raise BudgetExhaustedError when this call would push spend past the budget."""
        if self._month_spent + self._run_spend + estimated_cost_usd > self._budget:
            raise BudgetExhaustedError("The monthly evaluation budget would be exceeded by the next call.")

    def record(self, actual_cost_usd: Decimal | None) -> None:
        """Add a finished call's cost; None (unpriced) is charged at the configured worst case."""
        self._run_spend += self._unpriced if actual_cost_usd is None else actual_cost_usd


async def finish_run_with_spend(
    service: EvalResultsService,
    run_id: uuid.UUID,
    guard: BudgetGuard,
    *,
    status: str,
    counts: RunCounts,
    error_type: str | None = None,
) -> None:
    """Finish a run, storing the guard's run spend in `eval_runs.spend_usd` (writes, via the service)."""
    await service.finish_run(run_id, status=status, counts=counts, spend_usd=guard.run_spend_usd, error_type=error_type)
