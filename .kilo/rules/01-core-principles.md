# Core Programming Principles

## Normative Terms
- **MUST / MUST NOT / PROHIBITED** are binding — no exceptions.
- **SHOULD / AVOID** are strongly recommended but not binding.
- **MAY / OPTIONAL** are permissive.
- Where these rules conflict with softer language elsewhere, these rules win.

## Explicit Over Implicit
PROHIBITED without documented justification in code comments:
- Implicit ORM relationship loading that can trigger unbounded queries.
- Nullable columns without documented meaning of `NULL`.
- Implicit cascade behaviors (delete, update) without explicit configuration and tests.
- Silent fallback for missing critical config (auth, persistence, external providers).
- Convention-only "magic" field inference without explicit configuration.
- Wildcard imports (`from x import *`) in production code.
- Implicit enum widening without review and documentation updates.

## Error Handling
- Fail fast on invalid state or impossible conditions.
- Never swallow exceptions without logging.
- No generic `except` blocks without re-raising or structured handling.
- User-facing errors MUST map to explicit predictable responses — never leak internals.

## Side Effects
- Functions with side effects (I/O, DB writes, external calls) MUST be explicitly named and documented.
- Pure functions MUST NOT reach out to external systems, globals, or mutable shared state.

## Configuration
- All config MUST come from environment variables or config files. No hardcoding.
- Missing required config MUST cause startup failure — no silent defaults for critical systems.
- Dev environment MUST be started via Docker Compose before running backend or frontend code.
  Direct execution is only permitted for running tests or one-off scripts.
