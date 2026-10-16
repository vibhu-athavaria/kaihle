"""Unit tests for the production-evaluation budget guard (MLH-T18 slice 4, decision D2/D3).

Pure logic: the price estimator and settings are injected. Month-to-date spend against a real
database is covered by `integration/test_eval_prod_budget_spend.py`.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.eval_prod import budget
from app.services.eval_prod.budget import (
    BudgetConfigError,
    BudgetExhaustedError,
    BudgetGuard,
    BudgetRefusedError,
    check_run_can_start,
    estimate_call_cost,
    finish_run_with_spend,
    month_bounds,
    unpriced_call_cost,
)
from app.services.eval_results_service import RunCounts

JUDGE = "vendor-j/judge-1"
UNPRICED = Decimal("2.50")


def _priced(model: str, prompt_tokens: int | None, completion_tokens: int | None) -> Decimal | None:
    return Decimal("0.01")


def _unpriced(model: str, prompt_tokens: int | None, completion_tokens: int | None) -> Decimal | None:
    return None


def _can_start(**overrides: Any) -> None:
    kwargs: dict[str, Any] = {
        "monthly_budget_usd": Decimal("10"),
        "tracking_enabled": True,
        "judge_model": JUDGE,
        "price_estimator": _priced,
    }
    kwargs.update(overrides)
    check_run_can_start(**kwargs)


def test_budget_when_budget_zero_then_run_refused_with_clear_reason() -> None:
    with pytest.raises(BudgetRefusedError, match="budget is 0"):
        _can_start(monthly_budget_usd=Decimal("0"))


def test_budget_when_usage_tracking_disabled_then_run_refused() -> None:
    with pytest.raises(BudgetRefusedError, match="LLM_USAGE_TRACKING_ENABLED"):
        _can_start(tracking_enabled=False)


def test_budget_when_judge_model_has_no_price_then_run_refused_at_start() -> None:
    with pytest.raises(BudgetRefusedError, match="no price"):
        _can_start(price_estimator=_unpriced)


def test_budget_when_judge_unset_then_run_refused_at_start() -> None:
    with pytest.raises(BudgetRefusedError, match="LLM_EVAL_JUDGE_MODEL"):
        _can_start(judge_model="")


def test_budget_when_all_preconditions_hold_then_run_may_start() -> None:
    _can_start()


def test_budget_when_spend_plus_estimate_exceeds_budget_then_next_call_refused() -> None:
    guard = BudgetGuard(Decimal("1.00"), month_spent_usd=Decimal("0.90"), unpriced_call_cost_usd=UNPRICED)
    guard.authorize(Decimal("0.10"))  # exactly reaches the budget: allowed
    with pytest.raises(BudgetExhaustedError):
        guard.authorize(Decimal("0.11"))


def test_budget_when_calls_recorded_then_later_authorisation_sees_run_spend() -> None:
    guard = BudgetGuard(Decimal("1.00"), month_spent_usd=Decimal("0"), unpriced_call_cost_usd=UNPRICED)
    guard.record(Decimal("0.60"))
    guard.record(Decimal("0.30"))
    assert guard.run_spend_usd == Decimal("0.90")
    assert guard.remaining_usd == Decimal("0.10")
    with pytest.raises(BudgetExhaustedError):
        guard.authorize(Decimal("0.20"))


def test_budget_when_cost_null_then_counted_at_configured_worst_case_not_zero() -> None:
    guard = BudgetGuard(Decimal("10"), month_spent_usd=Decimal("0"), unpriced_call_cost_usd=UNPRICED)
    guard.record(None)
    assert guard.run_spend_usd == UNPRICED


def test_budget_when_month_spent_already_over_budget_then_nothing_authorised() -> None:
    guard = BudgetGuard(Decimal("1"), month_spent_usd=Decimal("5"), unpriced_call_cost_usd=UNPRICED)
    assert guard.remaining_usd == Decimal("0")
    with pytest.raises(BudgetExhaustedError):
        guard.authorize(Decimal("0"))


def test_budget_when_month_rolls_over_then_bounds_move_to_new_calendar_month() -> None:
    start, end = month_bounds(datetime(2026, 10, 31, 23, 59, tzinfo=UTC))
    assert (start, end) == (datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 11, 1, tzinfo=UTC))
    start, end = month_bounds(datetime(2026, 12, 15, tzinfo=UTC))
    assert (start, end) == (datetime(2026, 12, 1, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC))


def test_month_bounds_when_datetime_naive_then_raises_value_error() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        month_bounds(datetime(2026, 10, 1))


def test_estimate_call_cost_when_priced_then_uses_estimator_with_worst_case_completion() -> None:
    seen: list[tuple[str, int | None, int | None]] = []

    def estimator(model: str, prompt_tokens: int | None, completion_tokens: int | None) -> Decimal | None:
        seen.append((model, prompt_tokens, completion_tokens))
        return Decimal("0.02")

    cost = estimate_call_cost(JUDGE, 500, unpriced_cost_usd=UNPRICED, price_estimator=estimator)
    assert cost == Decimal("0.02")
    assert seen == [(JUDGE, 500, budget.JUDGE_MAX_TOKENS)]


def test_estimate_call_cost_when_unpriced_then_falls_back_to_configured_cost() -> None:
    assert estimate_call_cost(JUDGE, 500, unpriced_cost_usd=UNPRICED, price_estimator=_unpriced) == UNPRICED


def test_budget_when_unpriced_cost_env_unset_then_uses_documented_conservative_default_and_warns() -> None:
    config = MagicMock(eval_unpriced_call_cost_usd=1.0, model_fields_set=set())
    with patch.object(budget, "logger") as logger:
        assert unpriced_call_cost(config) == Decimal("1.0")
    logger.warning.assert_called_once()
    assert logger.warning.call_args.args[0] == "eval_unpriced_call_cost_default_in_use"


def test_budget_when_unpriced_cost_env_invalid_then_raises_config_error() -> None:
    for bad in (-1.0, float("nan"), float("inf")):
        config = MagicMock(eval_unpriced_call_cost_usd=bad, model_fields_set={"eval_unpriced_call_cost_usd"})
        with pytest.raises(BudgetConfigError):
            unpriced_call_cost(config)


def test_unpriced_call_cost_when_set_then_returns_exact_decimal_without_warning() -> None:
    config = MagicMock(eval_unpriced_call_cost_usd=0.1, model_fields_set={"eval_unpriced_call_cost_usd"})
    with patch.object(budget, "logger") as logger:
        assert unpriced_call_cost(config) == Decimal("0.1")
    logger.warning.assert_not_called()


async def test_finish_run_with_spend_when_called_then_persists_run_spend_and_status() -> None:
    service = MagicMock()
    service.finish_run = AsyncMock()
    guard = BudgetGuard(Decimal("5"), month_spent_usd=Decimal("0"), unpriced_call_cost_usd=UNPRICED)
    guard.record(Decimal("0.75"))
    run_id = uuid.uuid4()
    counts = RunCounts(sampled=3, evaluated=2)

    await finish_run_with_spend(service, run_id, guard, status="budget_exhausted", counts=counts)

    service.finish_run.assert_awaited_once_with(
        run_id, status="budget_exhausted", counts=counts, spend_usd=Decimal("0.75"), error_type=None
    )
