"""Read-only summaries of production-evaluation results for the Kaihle Admin Quality view.

MLH-T18 slice 6. Reads `eval_results` / `eval_runs` only; never touches prompt or response text
(decision D9), so a response from here cannot leak any.

RULES THE NUMBERS FOLLOW
  * Pass rate = passed / (passed + failed). Indeterminate results are reported separately and
    are NOT in the denominator (an unparseable verdict is neither a pass nor a fail).
  * Every rate carries n and a Wilson interval; n == 0 yields no rate at all.
  * Rows are grouped by rubric status, so an INDICATIVE rubric is never blended with a trusted
    one and the caller can label it.
  * One aggregate statement per summary call (no per-row lookups), filtered on
    `idx_eval_results_created`.

Access control (KAIHLE_ADMIN only) is enforced at the route boundary; these queries are
deliberately platform-wide (CONSTITUTION Rule 12 explicit bypass).
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.eval_metrics import rate
from app.core.config import Settings
from app.models.eval_results import EvalResult, EvalRun
from app.schemas.quality import (
    QualityBucket,
    QualityBudgetResponse,
    QualityFailureItem,
    QualityFailuresResponse,
    QualityRateRow,
    QualitySummaryResponse,
)
from app.services.eval_prod.budget import month_spend_usd, unpriced_call_cost
from app.services.platform_settings_service import PlatformSettingsService

MAX_WINDOW_DAYS = 366
MAX_SUMMARY_ROWS = 2000
MAX_FAILURES_PAGE_SIZE = 100
DEFAULT_FAILURES_PAGE_SIZE = 50
INDICATIVE_STATUS = "INDICATIVE"
DEFAULT_WINDOW_DAYS = 28


class QualityQueryError(ValueError):
    """The requested window or page is out of bounds. Safe to show; routes map it to 422."""


def resolve_window(
    window_start: datetime | None, window_end: datetime | None, now: datetime
) -> tuple[datetime, datetime]:
    """Fill in a missing window: ends now, starts DEFAULT_WINDOW_DAYS before its end."""
    end = window_end or now
    return window_start or end - timedelta(days=DEFAULT_WINDOW_DAYS), end


def _validate_window(window_start: datetime, window_end: datetime) -> None:
    if window_start.tzinfo is None or window_end.tzinfo is None:
        raise QualityQueryError("window bounds must include a timezone")
    if window_end <= window_start:
        raise QualityQueryError("window end must be after window start")
    if (window_end - window_start).days > MAX_WINDOW_DAYS:
        raise QualityQueryError(f"window must not exceed {MAX_WINDOW_DAYS} days")


def _conditions(window_start: datetime, window_end: datetime, task: str | None) -> list[ColumnElement[bool]]:
    conditions = [EvalResult.created_at >= window_start, EvalResult.created_at < window_end]
    if task is not None:
        conditions.append(EvalRun.task == task)
    return conditions


def _rate_row(row: Any, week_start: datetime | None) -> QualityRateRow:
    n = row.passed + row.failed
    measured = rate(row.passed, n) if n else None
    return QualityRateRow(
        week_start=week_start,
        task=row.task,
        check_name=row.check_name,
        kind=row.kind,
        rubric_status=row.rubric_status,
        is_indicative=row.rubric_status == INDICATIVE_STATUS,
        passed=row.passed,
        failed=row.failed,
        indeterminate=row.indeterminate,
        n=n,
        pass_rate=measured.point if measured else None,
        ci_low=measured.low if measured else None,
        ci_high=measured.high if measured else None,
    )


class QualitySummaryService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def summary(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
        task: str | None = None,
        bucket: QualityBucket = "week",
    ) -> QualitySummaryResponse:
        """Pass rates per task and check, optionally bucketed by UTC ISO week. Read-only."""
        _validate_window(window_start, window_end)
        by_week = bucket == "week"
        # Bucket in UTC explicitly: date_trunc on a timestamptz would follow the session zone.
        week = func.date_trunc("week", func.timezone("UTC", EvalResult.created_at))
        group_columns: list[Any] = [EvalRun.task, EvalResult.check_name, EvalResult.kind, EvalResult.rubric_status]
        select_columns: list[Any] = [*group_columns]
        if by_week:
            group_columns.insert(0, week)
            select_columns.insert(0, week.label("week_start"))
        statement = (
            select(
                *select_columns,
                func.count().filter(EvalResult.passed.is_(True)).label("passed"),
                func.count().filter(EvalResult.passed.is_(False)).label("failed"),
                func.count().filter(EvalResult.indeterminate.is_(True)).label("indeterminate"),
            )
            .join(EvalRun, EvalRun.id == EvalResult.run_id)
            .where(and_(*_conditions(window_start, window_end, task)))
            .group_by(*group_columns)
            .order_by(*group_columns)
            .limit(MAX_SUMMARY_ROWS + 1)
        )
        rows = (await self._db.execute(statement)).all()

        return QualitySummaryResponse(
            window_start=window_start,
            window_end=window_end,
            bucket=bucket,
            rates=[
                _rate_row(row, row.week_start.replace(tzinfo=UTC) if by_week else None)
                for row in rows[:MAX_SUMMARY_ROWS]
            ],
            truncated=len(rows) > MAX_SUMMARY_ROWS,
        )

    async def failures(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
        task: str | None = None,
        check_name: str | None = None,
        page: int = 1,
        page_size: int = DEFAULT_FAILURES_PAGE_SIZE,
    ) -> QualityFailuresResponse:
        """Failed checks as (usage_event_id, check name) pairs, newest first. Never any text.

        Results whose usage event was purged (NULL id) are excluded: there is nothing to open.
        """
        _validate_window(window_start, window_end)
        if page < 1 or not 1 <= page_size <= MAX_FAILURES_PAGE_SIZE:
            raise QualityQueryError(f"page must be >= 1 and page_size between 1 and {MAX_FAILURES_PAGE_SIZE}")
        conditions = [
            *_conditions(window_start, window_end, task),
            EvalResult.passed.is_(False),
            EvalResult.usage_event_id.is_not(None),
        ]
        if check_name is not None:
            conditions.append(EvalResult.check_name == check_name)

        # One page query plus one count: two statements regardless of page size.
        rows = (
            await self._db.execute(
                select(EvalResult.usage_event_id, EvalResult.check_name, EvalRun.task, EvalResult.created_at)
                .join(EvalRun, EvalRun.id == EvalResult.run_id)
                .where(and_(*conditions))
                .order_by(EvalResult.created_at.desc(), EvalResult.id)
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()
        total = await self._db.scalar(
            select(func.count())
            .select_from(EvalResult)
            .join(EvalRun, EvalRun.id == EvalResult.run_id)
            .where(and_(*conditions))
        )
        return QualityFailuresResponse(
            failures=[
                QualityFailureItem(
                    usage_event_id=row.usage_event_id,
                    check_name=row.check_name,
                    task=row.task,
                    created_at=row.created_at,
                )
                for row in rows
            ],
            total=total or 0,
            page=page,
            page_size=page_size,
        )

    async def budget_status(self, config: Settings, now: datetime) -> QualityBudgetResponse:
        """Budget, month-to-date spend and remaining budget, via the slice-4 budget helpers."""
        eval_settings = await PlatformSettingsService(self._db).get_eval_settings()
        spent = await month_spend_usd(self._db, now, unpriced_call_cost(config))
        remaining = max(eval_settings.monthly_budget_usd - spent, Decimal("0"))
        return QualityBudgetResponse(
            monthly_budget_usd=float(eval_settings.monthly_budget_usd),
            month_to_date_spend_usd=float(spent),
            remaining_usd=float(remaining),
        )
