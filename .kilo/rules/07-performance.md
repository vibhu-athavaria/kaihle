# Performance Guardrails

## Queries
- N+1 query patterns in hot paths are PROHIBITED.
- All list/search endpoints MUST implement pagination or explicit bounds — no unbounded scans.
- Queries in hot paths MUST be backed by appropriate indexes.

## Blocking Operations
- Long-running operations MUST NOT run in synchronous request/response paths — offload to Celery.
- All external calls (third-party, LLM providers) MUST have explicitly configured timeouts and defined failure/fallback behavior.
