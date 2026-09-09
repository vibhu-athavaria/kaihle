"""Unit tests for `llm_usage_service` — the shared aggregation the CLI report and the
Kaihle Admin page both call.

`db.execute` is mocked (matching this codebase's `tests/unit/` convention — see
`test_analytics_service.py`), so these tests pin the service's own logic: how it turns
raw SQL rows into the two honesty indicators, and that it refuses to build a query from
an unvalidated `group_by` at all. The SQL's own correctness (real GROUP BY, real
FILTER clauses) is covered by the integration suite against a real database.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_usage_service import (
    InvalidGroupByError,
    compute_unit_costs,
    summarise_usage,
)

SINCE = datetime(2026, 8, 1, tzinfo=UTC)


def _totals(
    calls: int = 0,
    tokens: int = 0,
    cost: Decimal | None = None,
    unpriced: int = 0,
    successes: int = 0,
    unattributed: int = 0,
    failures: int = 0,
    p95: int = 0,
) -> dict[str, object]:
    return {
        "calls": calls,
        "tokens": tokens,
        "cost": cost,
        "unpriced": unpriced,
        "successes": successes,
        "unattributed": unattributed,
        "failures": failures,
        "p95": p95,
    }


def _mock_db(
    bucket_rows: list[dict[str, object]],
    bucket_count: int,
    totals: dict[str, object],
    unpriced_models: list[str],
) -> MagicMock:
    """Build a mock AsyncSession whose four sequential `execute` calls match the order
    `summarise_usage` issues them in: buckets, bucket count, totals, unpriced models.
    """
    db = MagicMock(spec=AsyncSession)

    bucket_result = MagicMock()
    bucket_result.mappings.return_value = bucket_rows

    count_result = MagicMock()
    count_result.scalar_one.return_value = bucket_count

    totals_result = MagicMock()
    totals_result.mappings.return_value.one.return_value = totals

    models_result = MagicMock()
    models_result.all.return_value = [(m,) for m in unpriced_models]

    db.execute = AsyncMock(side_effect=[bucket_result, count_result, totals_result, models_result])
    return db


class TestSummariseUsageEmptyWindow:
    async def test_summarise_usage_when_no_events_then_returns_zeroed_summary_not_error(self) -> None:
        db = _mock_db(bucket_rows=[], bucket_count=0, totals=_totals(), unpriced_models=[])

        report = await summarise_usage(db, SINCE, "component")

        assert report.buckets == []
        assert report.summary.calls == 0
        assert report.summary.cost is None
        assert report.summary.unpriced_percent == 0.0
        assert report.summary.unattributed_percent == 0.0


class TestSummariseUsageGrouping:
    async def test_summarise_usage_when_events_present_then_groups_by_requested_column(self) -> None:
        rows = [
            {
                "bucket": "test/model-a",
                "calls": 5,
                "failures": 1,
                "tokens": 1000,
                "cost": Decimal("0.500000"),
                "p50": 200.0,
                "p95": 800.0,
            }
        ]
        db = _mock_db(
            bucket_rows=rows,
            bucket_count=1,
            totals=_totals(calls=5, tokens=1000, cost=Decimal("0.5"), successes=4, failures=1),
            unpriced_models=[],
        )

        report = await summarise_usage(db, SINCE, "model")

        # The requested column, not the default, must be the one interpolated.
        first_call_sql = str(db.execute.call_args_list[0].args[0])
        assert "COALESCE(model," in first_call_sql

        assert len(report.buckets) == 1
        bucket = report.buckets[0]
        assert bucket.bucket == "test/model-a"
        assert bucket.calls == 5
        assert bucket.failures == 1
        assert bucket.tokens == 1000
        assert bucket.cost == Decimal("0.500000")
        assert bucket.p50_ms == 200
        assert bucket.p95_ms == 800


class TestUnpricedPercentage:
    async def test_summarise_usage_when_some_costs_null_then_unpriced_percentage_reported(self) -> None:
        db = _mock_db(
            bucket_rows=[],
            bucket_count=0,
            totals=_totals(calls=10, successes=10, unpriced=3),
            unpriced_models=["self-hosted/model-x"],
        )

        report = await summarise_usage(db, SINCE, "component")

        assert report.summary.unpriced_count == 3
        assert report.summary.unpriced_percent == pytest.approx(30.0)
        assert report.summary.unpriced_models == ["self-hosted/model-x"]

    async def test_summarise_usage_when_unpriced_denominator_then_excludes_failed_calls(self) -> None:
        # 10 calls total, 2 failed -> 8 successful. 4 of the successful calls are
        # unpriced. The percentage must be 4/8 (50%), never 4/10 (40%) — a failed call
        # has no tokens, so having no cost is correct, not a pricing gap.
        db = _mock_db(
            bucket_rows=[],
            bucket_count=0,
            totals=_totals(calls=10, successes=8, failures=2, unpriced=4),
            unpriced_models=[],
        )

        report = await summarise_usage(db, SINCE, "component")

        assert report.summary.unpriced_percent == pytest.approx(50.0)


class TestUnattributedPercentage:
    async def test_summarise_usage_when_some_components_null_then_unattributed_percentage_reported(self) -> None:
        db = _mock_db(
            bucket_rows=[],
            bucket_count=0,
            totals=_totals(calls=10, unattributed=5),
            unpriced_models=[],
        )

        report = await summarise_usage(db, SINCE, "component")

        assert report.summary.unattributed_count == 5
        assert report.summary.unattributed_percent == pytest.approx(50.0)


class TestDateRangeFiltering:
    async def test_summarise_usage_when_date_range_given_then_events_outside_excluded(self) -> None:
        db = _mock_db(bucket_rows=[], bucket_count=0, totals=_totals(), unpriced_models=[])

        await summarise_usage(db, SINCE, "component")

        # Every query in the aggregation must filter on the same cutoff, or the CLI
        # report and this page could disagree about which rows are "in window".
        for call in db.execute.call_args_list:
            params = call.args[1]
            assert params["since"] == SINCE


class TestGroupByValidation:
    async def test_summarise_usage_when_group_by_is_invalid_column_then_rejected_before_query(self) -> None:
        db = MagicMock(spec=AsyncSession)
        db.execute = AsyncMock()

        with pytest.raises(InvalidGroupByError):
            await summarise_usage(db, SINCE, "school_id; DROP TABLE llm_usage_events;--")

        db.execute.assert_not_called()


def _unit_cost_db(
    diagnostics_completed: int,
    generation_row: dict[str, object],
    mini_row: dict[str, object],
    run_rows: list[dict[str, object]],
) -> MagicMock:
    db = MagicMock(spec=AsyncSession)

    diagnostics_result = MagicMock()
    diagnostics_result.scalar_one.return_value = diagnostics_completed

    generation_result = MagicMock()
    generation_result.mappings.return_value.one.return_value = generation_row

    mini_result = MagicMock()
    mini_result.mappings.return_value.one.return_value = mini_row

    runs_result = MagicMock()
    runs_result.mappings.return_value = run_rows

    db.execute = AsyncMock(side_effect=[diagnostics_result, generation_result, mini_result, runs_result])
    return db


class TestComputeUnitCosts:
    async def test_compute_unit_costs_when_no_diagnostics_completed_then_reports_structural_zero(self) -> None:
        db = _unit_cost_db(
            diagnostics_completed=0,
            generation_row={"calls": 0, "cost": None, "unpriced": 0},
            mini_row={"calls": 0, "cost": None},
            run_rows=[],
        )

        results = await compute_unit_costs(db, SINCE)

        label, value = results[0]
        assert label == "Cost during a completed diagnostic (student-time only)"
        assert value.startswith("$0.00 marginal — 0 completed")

    async def test_compute_unit_costs_when_no_run_id_recorded_then_reports_unavailable_not_approximated(self) -> None:
        db = _unit_cost_db(
            diagnostics_completed=3,
            generation_row={"calls": 0, "cost": None, "unpriced": 0},
            mini_row={"calls": 0, "cost": None},
            run_rows=[],
        )

        results = await compute_unit_costs(db, SINCE)

        label, value = results[-1]
        assert label == "Batch run costs"
        assert "unavailable" in value
        assert "no run_id recorded" in value
