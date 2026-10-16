"""Integration tests for month-to-date evaluation spend (MLH-T18 slice 4). Real Postgres."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_usage import LlmUsageEvent
from app.services.eval_prod.budget import month_spend_usd

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
UNPRICED = Decimal("2.50")


async def _event(db: AsyncSession, **overrides: Any) -> None:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "task": "eval_judge",
        "model": "test/judge",
        "component": "eval_prod_sample",
        "latency_ms": 5,
        "created_at": datetime(2026, 10, 3, tzinfo=UTC),
        "succeeded": True,
        "estimated_cost_usd": Decimal("0.25"),
    }
    values.update(overrides)
    db.add(LlmUsageEvent(**values))
    await db.commit()


async def test_budget_spend_when_computed_then_only_counts_eval_prod_components(db_session: AsyncSession) -> None:
    await _event(db_session, estimated_cost_usd=Decimal("0.25"))
    await _event(db_session, component="eval_prod_other", estimated_cost_usd=Decimal("0.50"))
    await _event(db_session, component="eval_harness", estimated_cost_usd=Decimal("9"))
    await _event(db_session, component="evalXprodXsample", estimated_cost_usd=Decimal("9"))  # LIKE wildcard guard
    await _event(db_session, component=None, estimated_cost_usd=Decimal("9"))
    assert await month_spend_usd(db_session, NOW, UNPRICED) == Decimal("0.75")


async def test_budget_when_cost_null_then_counted_at_configured_worst_case_not_zero_in_month_spend(
    db_session: AsyncSession,
) -> None:
    await _event(db_session, estimated_cost_usd=None)
    await _event(db_session, estimated_cost_usd=Decimal("0.25"))
    assert await month_spend_usd(db_session, NOW, UNPRICED) == Decimal("2.75")


async def test_budget_when_month_rolls_over_then_spend_resets(db_session: AsyncSession) -> None:
    await _event(db_session, created_at=datetime(2026, 9, 30, 23, 59, tzinfo=UTC), estimated_cost_usd=Decimal("4"))
    await _event(db_session, created_at=datetime(2026, 10, 1, tzinfo=UTC), estimated_cost_usd=Decimal("1"))
    await _event(db_session, created_at=datetime(2026, 11, 1, tzinfo=UTC), estimated_cost_usd=Decimal("8"))
    assert await month_spend_usd(db_session, NOW, UNPRICED) == Decimal("1")
    assert await month_spend_usd(db_session, datetime(2026, 11, 2, tzinfo=UTC), UNPRICED) == Decimal("8")


async def test_budget_spend_when_no_events_then_zero(db_session: AsyncSession) -> None:
    assert await month_spend_usd(db_session, NOW, UNPRICED) == Decimal("0")
