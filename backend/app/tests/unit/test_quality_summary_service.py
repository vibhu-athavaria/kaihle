"""Unit tests for `QualitySummaryService` (MLH-T18 slice 6). `db.execute` is mocked, as is the
`tests/unit/` convention; real-SQL behaviour (grouping, bucketing, statement count) is covered by
`tests/integration/test_quality_routes.py`."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.schemas.quality import QualityFailuresResponse
from app.services.platform_settings_service import EvalSettings
from app.services.quality_summary_service import (
    MAX_FAILURES_PAGE_SIZE,
    MAX_SUMMARY_ROWS,
    MAX_WINDOW_DAYS,
    QualityQueryError,
    QualitySummaryService,
)

START = datetime(2026, 10, 1, tzinfo=UTC)
END = datetime(2026, 10, 29, tzinfo=UTC)


def _agg(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "week_start": datetime(2026, 10, 5),
        "task": "question_generation",
        "check_name": "mcq_has_four_options",
        "kind": "deterministic",
        "rubric_status": None,
        "passed": 8,
        "failed": 2,
        "indeterminate": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _db(rows: list[Any], scalar: int | None = None) -> AsyncMock:
    result = MagicMock()
    result.all.return_value = rows
    db = AsyncMock()
    db.execute.return_value = result
    db.scalar.return_value = scalar
    return db


async def test_summary_when_results_exist_then_pass_rate_per_task_and_check_with_n_and_wilson_interval() -> None:
    response = await QualitySummaryService(_db([_agg()])).summary(window_start=START, window_end=END)

    row = response.rates[0]
    assert (row.task, row.check_name, row.n) == ("question_generation", "mcq_has_four_options", 10)
    assert row.pass_rate == 0.8
    assert row.ci_low is not None and row.ci_high is not None
    assert row.ci_low < 0.8 < row.ci_high
    assert row.week_start == datetime(2026, 10, 5, tzinfo=UTC)


async def test_summary_when_indeterminate_present_then_reported_separately_and_excluded_from_denominator() -> None:
    row = (
        await QualitySummaryService(_db([_agg(passed=3, failed=1, indeterminate=6)])).summary(
            window_start=START, window_end=END
        )
    ).rates[0]

    assert (row.passed, row.failed, row.indeterminate, row.n) == (3, 1, 6, 4)
    assert row.pass_rate == 0.75


async def test_summary_when_every_result_indeterminate_then_no_rate_not_zero_percent() -> None:
    row = (
        await QualitySummaryService(_db([_agg(passed=0, failed=0, indeterminate=5)])).summary(
            window_start=START, window_end=END
        )
    ).rates[0]

    assert row.n == 0
    assert (row.pass_rate, row.ci_low, row.ci_high) == (None, None, None)


@pytest.mark.parametrize(
    ("status", "indicative"), [("INDICATIVE", True), ("CALIBRATED", False), ("HUMAN_VALIDATED", False)]
)
async def test_summary_when_rubric_indicative_then_status_returned_with_each_rate(
    status: str, indicative: bool
) -> None:
    rows = [_agg(kind="judge", check_name="r1", rubric_status=status)]

    row = (await QualitySummaryService(_db(rows)).summary(window_start=START, window_end=END)).rates[0]

    assert row.rubric_status == status
    assert row.is_indicative is indicative


async def test_summary_when_bucket_none_then_no_week_start() -> None:
    response = await QualitySummaryService(_db([_agg(week_start=None)])).summary(
        window_start=START, window_end=END, bucket="none"
    )

    assert response.rates[0].week_start is None


async def test_summary_when_no_results_then_empty_list_not_error() -> None:
    response = await QualitySummaryService(_db([])).summary(window_start=START, window_end=END)

    assert response.rates == []
    assert response.truncated is False


async def test_summary_when_row_cap_exceeded_then_truncated_flag_set_and_rows_capped() -> None:
    rows = [_agg(check_name=f"c{i}") for i in range(MAX_SUMMARY_ROWS + 1)]

    response = await QualitySummaryService(_db(rows)).summary(window_start=START, window_end=END)

    assert response.truncated is True
    assert len(response.rates) == MAX_SUMMARY_ROWS


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (END, START),
        (START, START),
        (START.replace(tzinfo=None), END),
        (START, START + timedelta(days=MAX_WINDOW_DAYS + 1)),
    ],
    ids=["reversed", "empty", "naive", "too-long"],
)
async def test_summary_when_window_invalid_then_raises_query_error(start: datetime, end: datetime) -> None:
    with pytest.raises(QualityQueryError):
        await QualitySummaryService(_db([])).summary(window_start=start, window_end=end)


async def test_failures_when_called_then_returns_usage_event_ids_and_check_names_only() -> None:
    event_id = uuid.uuid4()
    row = SimpleNamespace(usage_event_id=event_id, check_name="no_banned_phrase", task="lesson_plan", created_at=START)

    response = await QualitySummaryService(_db([row], scalar=1)).failures(window_start=START, window_end=END)

    item = response.failures[0]
    assert item.usage_event_id == event_id
    assert set(item.model_dump()) == {"usage_event_id", "check_name", "task", "created_at"}
    assert response.total == 1


async def test_failures_when_no_rows_then_empty_page() -> None:
    response = await QualitySummaryService(_db([], scalar=None)).failures(window_start=START, window_end=END)

    assert isinstance(response, QualityFailuresResponse)
    assert (response.failures, response.total) == ([], 0)


@pytest.mark.parametrize(("page", "page_size"), [(0, 10), (1, 0), (1, MAX_FAILURES_PAGE_SIZE + 1)])
async def test_failures_when_page_out_of_bounds_then_raises_query_error(page: int, page_size: int) -> None:
    with pytest.raises(QualityQueryError):
        await QualitySummaryService(_db([])).failures(
            window_start=START, window_end=END, page=page, page_size=page_size
        )


async def test_failures_when_page_requested_then_limit_and_offset_applied() -> None:
    db = _db([], scalar=0)

    await QualitySummaryService(db).failures(window_start=START, window_end=END, page=3, page_size=20)

    statement = db.execute.call_args.args[0]
    assert statement._limit_clause.value == 20
    assert statement._offset_clause.value == 40


async def test_budget_status_when_spend_below_budget_then_remaining_is_difference() -> None:
    settings = EvalSettings(Decimal("10"), [], 50, 7, False, {}, None, None)
    with (
        patch("app.services.quality_summary_service.PlatformSettingsService") as service_cls,
        patch("app.services.quality_summary_service.month_spend_usd", AsyncMock(return_value=Decimal("2.5"))),
        patch("app.services.quality_summary_service.unpriced_call_cost", return_value=Decimal("1")),
    ):
        service_cls.return_value.get_eval_settings = AsyncMock(return_value=settings)
        response = await QualitySummaryService(AsyncMock()).budget_status(Settings(), START)

    assert (response.monthly_budget_usd, response.month_to_date_spend_usd, response.remaining_usd) == (10, 2.5, 7.5)


async def test_budget_status_when_spend_exceeds_budget_then_remaining_clamped_to_zero() -> None:
    settings = EvalSettings(Decimal("1"), [], 50, 7, False, {}, None, None)
    with (
        patch("app.services.quality_summary_service.PlatformSettingsService") as service_cls,
        patch("app.services.quality_summary_service.month_spend_usd", AsyncMock(return_value=Decimal("3"))),
        patch("app.services.quality_summary_service.unpriced_call_cost", return_value=Decimal("1")),
    ):
        service_cls.return_value.get_eval_settings = AsyncMock(return_value=settings)
        response = await QualitySummaryService(AsyncMock()).budget_status(Settings(), START)

    assert response.remaining_usd == 0
