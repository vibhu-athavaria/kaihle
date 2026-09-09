"""LLM Logs schemas — one row per LLM call, for the Kaihle Admin per-call viewer.

Detail extends summary the same way `LlmLogDetail` extends `LlmLogSummary` in
`llm_log_service.py`: the list response deliberately excludes `prompt_text`/
`response_text` (can be arbitrarily long; a page of 50 calls has no reason to carry
all of them when only one row's text is ever shown at a time), and the detail response
adds them back for the single row a click actually asked for.
"""

from datetime import datetime

from pydantic import BaseModel


class LlmLogSummaryResponse(BaseModel):
    id: str
    created_at: datetime
    task: str
    model: str
    component: str | None
    run_id: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: int
    estimated_cost_usd: float | None
    succeeded: bool
    error_type: str | None


class LlmLogsResponse(BaseModel):
    logs: list[LlmLogSummaryResponse]
    total: int
    page: int
    page_size: int


class LlmLogFilterOptionsResponse(BaseModel):
    tasks: list[str]
    models: list[str]


class LlmLogDetailResponse(LlmLogSummaryResponse):
    prompt_text: str | None
    response_text: str | None
    error_detail: str | None
    correlation_id: str | None
    school_id: str | None
    streamed: bool
