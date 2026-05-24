# Data and Schema Governance

## Single Source of Truth
- Every persisted value MUST have exactly one canonical source.
- Derived or denormalized data MUST document: its origin, sync frequency, and failure modes.
- Exact column names, types, and constraints must be verified against both the ORM model and the canonical schema file. If they agree, proceed. If they conflict, surface the conflict and ask for clarification — never guess. The schema file is authoritative over model code.

## Nullability
- New columns MUST be NOT NULL by default unless there is an explicit semantic need for NULL.
- Any nullable column MUST include an explanation in the migration or code comment, plus NULL-path tests.

## Constraints
- Business invariants MUST be enforced at the DB level wherever possible.
- Code-level checks alone are NOT sufficient where the database can enforce the constraint.

## Enum Governance
- Enum values are part of the persistent contract.
- MUST NOT remove values still present in data — requires migration and compatibility strategy.
- MUST NOT reuse deprecated names or numeric codes.
- Adding a new value MUST include: an update in CONSTITUTION.md or the task file, and tests for all consumers.
- Deprecated values MUST be explicitly marked and handled predictably.

## Migrations
- Every structural change MUST go through an Alembic migration. Ad-hoc schema changes are PROHIBITED.
- Do NOT write migration SQL by hand — use `alembic revision --autogenerate -m "description"` and review the output.
- Every migration MUST include a downgrade path unless inherently irreversible (must be documented).
- Data-destructive operations MUST be preceded by a backup and clearly documented.
- Adding non-nullable columns MUST include a backfill strategy and pre/post-migration tests.
- Migrations MUST NOT embed application logic (no calling services from inside migrations).
