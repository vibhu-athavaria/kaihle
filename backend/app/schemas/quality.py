"""Response schemas for the Kaihle Admin Quality view (MLH-T18 slice 6).

Nothing here can carry prompt, response or judge-evidence text (decision D9): the failure item
is a usage-event id plus a check name, and the admin opens the existing LLM Logs entry by id.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

QualityBucket = Literal["week", "none"]


class QualityRateRow(BaseModel):
    """Pass rate of one check on one task (optionally within one weekly bucket).

    `passed + failed` is the denominator `n`. `indeterminate` results (e.g. an unparseable
    judge verdict) are counted separately and are NOT in `n`. With `n == 0` the rate and its
    interval are None: "nothing measured" is not "0% passed".
    """

    # Start of the UTC ISO week; None when bucket="none" (whole window aggregated).
    week_start: datetime | None
    task: str
    check_name: str
    kind: Literal["deterministic", "judge"]
    # NULL for deterministic checks. A check re-run after a rubric status change appears once
    # per status so trusted and indicative results are never blended into one rate.
    rubric_status: str | None
    # True when rubric_status == "INDICATIVE": a judge rubric whose agreement with humans has
    # not been established, so this rate must be presented as indicative only.
    is_indicative: bool
    passed: int
    failed: int
    indeterminate: int
    n: int
    pass_rate: float | None
    ci_low: float | None
    ci_high: float | None


class QualitySummaryResponse(BaseModel):
    window_start: datetime
    window_end: datetime
    bucket: QualityBucket
    # Empty list (not an error) when no results exist in the window.
    rates: list[QualityRateRow]
    # True when the row cap was hit; narrow the window or filter by task.
    truncated: bool


class QualityFailureItem(BaseModel):
    """A failed check on a sampled event. Ids and names only, never text."""

    usage_event_id: uuid.UUID
    check_name: str
    task: str
    created_at: datetime


class QualityFailuresResponse(BaseModel):
    failures: list[QualityFailureItem]
    total: int
    page: int
    page_size: int


class QualityBudgetResponse(BaseModel):
    """Month-to-date evaluation spend against the admin-set budget (UTC calendar month).

    Spend counts unpriced calls at the configured worst case (D2), so it is an upper estimate.
    """

    monthly_budget_usd: float
    month_to_date_spend_usd: float
    remaining_usd: float
