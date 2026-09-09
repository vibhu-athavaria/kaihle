"""LLM usage/cost schemas — the response shape `/platform/llm-usage` shares with
`scripts/llm_cost_report.py` (same underlying `UsageReport` from `llm_usage_service`)."""

from datetime import date

from pydantic import BaseModel


class LlmUsageBucket(BaseModel):
    bucket: str
    calls: int
    failures: int
    tokens: int
    cost: float | None  # None distinct from 0.0 — an unpriceable bucket, not a free one
    p50_ms: int
    p95_ms: int


class LlmUsageSummary(BaseModel):
    calls: int
    tokens: int
    cost: float | None
    unpriced_count: int
    unpriced_percent: float  # of SUCCESSFUL calls, matching the CLI report exactly
    unpriced_models: list[str]
    unattributed_count: int
    unattributed_percent: float
    failures: int
    p95_ms: int  # across the whole window, not just the current page of buckets


class LlmUsageResponse(BaseModel):
    since: date
    group_by: str
    buckets: list[LlmUsageBucket]
    summary: LlmUsageSummary
    unit_costs: list[tuple[str, str]]  # label, value
    page: int
    page_size: int
    total_buckets: int  # total distinct groups in this window — drives pagination
