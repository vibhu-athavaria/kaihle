# Transactions, Persistence, and Idempotency

## Transactions
- All DB write operations MUST occur within an explicit transactional context.
- Partial writes across services without a defined transaction or saga pattern are PROHIBITED.
- Multi-step changes that must succeed or fail together MUST be a single transaction or saga.
- Implicit auto-commit for critical writes is PROHIBITED.

## Background Jobs
- Any write in a background process MUST be idempotent or guarded by an idempotency key.
- Celery tasks MUST use `new_event_loop()` — never `asyncio.run()` inside a task.
- Assume any task can be retried and executed more than once.

## Idempotency
- All write operations (APIs, CLI, jobs) MUST be idempotent by design OR clearly reject duplicates with a deterministic documented error.
- Uniqueness and integrity MUST be enforced at the DB level to prevent race-condition duplication.
- Optimistic or pessimistic locking MUST be used where concurrent updates can conflict.
- Retried operations with external side effects (email, external calls) MUST use idempotency keys and be guarded against duplicate user-visible actions.
