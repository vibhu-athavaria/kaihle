"""Integration tests for LLM usage persistence.

What needs a real database here is the schema's own guarantees — the nullable `school_id`
that CONSTITUTION Rule 2 would otherwise forbid, the CHECK constraints that keep a row from
claiming to have both succeeded and failed, and the NUMERIC column that must not drift when
costs are summed.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_usage import LlmUsageEvent
from app.models.school import School


def _event(**overrides: object) -> LlmUsageEvent:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "task": "question_generation",
        "model": "test/model-a",
        "component": "script:generate_gap_questions",
        "run_id": "run-1",
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "total_tokens": 300,
        "latency_ms": 1234,
        "estimated_cost_usd": Decimal("0.001500"),
        "streamed": False,
        "succeeded": True,
        "error_type": None,
        "correlation_id": "corr-1",
        "school_id": None,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return LlmUsageEvent(**defaults)


@pytest.mark.asyncio
class TestLlmUsageEventPersistence:
    async def test_usage_event_when_inserted_then_readable_with_null_school_id(self, db_session: AsyncSession) -> None:
        # The Rule 2 deviation, exercised: platform-level work has no school, and the row
        # must persist rather than being rejected.
        db_session.add(_event(school_id=None))
        await db_session.flush()

        found = await db_session.execute(select(LlmUsageEvent).where(LlmUsageEvent.run_id == "run-1"))
        row = found.scalar_one()
        assert row.school_id is None
        assert row.component == "script:generate_gap_questions"

    async def test_usage_event_when_school_id_supplied_then_foreign_key_enforced(
        self, db_session: AsyncSession, school: School
    ) -> None:
        db_session.add(_event(school_id=school.id))
        await db_session.flush()

        found = await db_session.execute(select(LlmUsageEvent).where(LlmUsageEvent.school_id == school.id))
        assert found.scalar_one().school_id == school.id

    async def test_usage_event_when_school_id_unknown_then_rejected(self, db_session: AsyncSession) -> None:
        db_session.add(_event(school_id=uuid.uuid4()))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_usage_event_when_failed_without_error_type_then_rejected(self, db_session: AsyncSession) -> None:
        # A row must not claim to have failed without naming the failure.
        db_session.add(_event(succeeded=False, error_type=None))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_usage_event_when_succeeded_with_error_type_then_rejected(self, db_session: AsyncSession) -> None:
        db_session.add(_event(succeeded=True, error_type="RateLimitError"))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_usage_event_when_latency_negative_then_rejected(self, db_session: AsyncSession) -> None:
        db_session.add(_event(latency_ms=-1))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_usage_event_when_cost_null_then_accepted(self, db_session: AsyncSession) -> None:
        # NULL is the designed answer for an unpriceable model, not a constraint violation.
        db_session.add(_event(estimated_cost_usd=None, run_id="unpriced"))
        await db_session.flush()

        found = await db_session.execute(select(LlmUsageEvent).where(LlmUsageEvent.run_id == "unpriced"))
        assert found.scalar_one().estimated_cost_usd is None

    async def test_usage_event_when_costs_summed_then_no_float_drift(self, db_session: AsyncSession) -> None:
        # The reason the column is NUMERIC: 0.1 + 0.2 in binary floating point is not 0.3,
        # and these are summed across millions of rows.
        for _ in range(3):
            db_session.add(_event(estimated_cost_usd=Decimal("0.100000"), run_id="sumtest"))
        await db_session.flush()

        total = await db_session.execute(
            select(func.sum(LlmUsageEvent.estimated_cost_usd)).where(LlmUsageEvent.run_id == "sumtest")
        )
        assert total.scalar_one() == Decimal("0.300000")

    async def test_usage_event_when_grouped_by_component_then_unpriced_share_computable(
        self, db_session: AsyncSession
    ) -> None:
        # The cost report's two honesty indicators must be derivable from the schema alone.
        db_session.add(_event(run_id="mix", estimated_cost_usd=Decimal("0.01"), component="api:x"))
        db_session.add(_event(run_id="mix", estimated_cost_usd=None, component=None))
        await db_session.flush()

        stats = await db_session.execute(
            select(
                func.count(),
                func.count().filter(LlmUsageEvent.estimated_cost_usd.is_(None)),
                func.count().filter(LlmUsageEvent.component.is_(None)),
            ).where(LlmUsageEvent.run_id == "mix")
        )
        total, unpriced, unattributed = stats.one()
        assert (total, unpriced, unattributed) == (2, 1, 1)

    async def test_usage_event_when_filtered_by_date_then_older_rows_excluded(self, db_session: AsyncSession) -> None:
        db_session.add(_event(run_id="recent", created_at=datetime.now(UTC)))
        db_session.add(_event(run_id="old", created_at=datetime.now(UTC) - timedelta(days=90)))
        await db_session.flush()

        cutoff = datetime.now(UTC) - timedelta(days=30)
        rows = await db_session.execute(select(LlmUsageEvent.run_id).where(LlmUsageEvent.created_at >= cutoff))
        run_ids = {r[0] for r in rows.all()}
        assert "recent" in run_ids
        assert "old" not in run_ids
