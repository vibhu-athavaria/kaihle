# Logging and Observability

## Structured Logging
- All logs MUST be structured JSON via structlog. No `print()` or unstructured logging in production.

## Boundary Logging
All external boundary interactions MUST be logged at INFO level:
- DB transactions (high-level, not every query).
- Cache and message broker operations.
- Calls to external services and LLM providers.
- Sensitive data MUST NOT appear in logs.

## State Transitions
Significant state changes MUST log: actor, previous state, new state, correlation ID.

## Correlation ID
- A correlation ID MUST be generated per request or job and propagated through all layers.
- Every log entry MUST include this ID.
