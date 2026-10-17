"""Request/response schemas for Kaihle Admin production-evaluation runs (MLH-T18 slice 5b-ii).

A run response exposes metadata, counts and spend only. It can never carry prompt, response or
judge-evidence text (decision D9): the model has no such column and this schema adds none.
`spend_usd` is a Decimal, which Pydantic serialises to JSON as a string (no float rounding).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

MAX_TASK_LENGTH = 50  # eval_runs.task is String(50)
MAX_SEED_LENGTH = 64  # eval_runs.seed is String(64)


class EvalRunCreateRequest(BaseModel):
    """Start ("Run now") a production evaluation of one task.

    Omitted bounds default to the admin's saved window length ending now. An omitted seed is
    generated, so every click is a new run; send the same seed and window to make a repeat
    submit idempotent (the existing run is returned and nothing is enqueued again).
    """

    task: str = Field(min_length=1, max_length=MAX_TASK_LENGTH)
    window_start: datetime | None = None
    window_end: datetime | None = None
    seed: str | None = Field(default=None, min_length=1, max_length=MAX_SEED_LENGTH)


class EvalRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task: str
    window_start: datetime
    window_end: datetime
    seed: str
    trigger: str
    status: str
    include_indicative: bool
    judge_model: str | None
    sampled_count: int
    evaluated_count: int
    skipped_not_independent_count: int
    skipped_scrub_failed_count: int
    skipped_unsupported_count: int
    spend_usd: Decimal
    error_type: str | None
    requested_by: uuid.UUID | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class EvalRunListResponse(BaseModel):
    runs: list[EvalRunResponse]
    total: int
    page: int
    page_size: int
