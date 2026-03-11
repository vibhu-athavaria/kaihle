# Kaihle Engineering Governance

This document defines the **non-negotiable engineering rules** for the Kaihle codebase.
It applies to all contributors — human and automated agents alike.
It governs **how** software is engineered. Domain models, tech stack, enums, and endpoints
are defined in `CONSTITUTION.md` and task files — not here.

**Precedence:** KiloCode loads rules in this order (highest → lowest):
`.kilocode/rules-{mode}/` → `.kilocode/rules/` → `AGENTS.md` → global rules.
If this document conflicts with a mode-specific rule file, the rule file wins.
If this document conflicts with `CONSTITUTION.md` on domain details, `CONSTITUTION.md` wins.
If this document conflicts with any other document on **engineering discipline**, this document wins.

---

## Scope and Agent Contract

This document applies to all backend services, frontend applications, background workers,
data stores, queues, external integrations, and CI/CD pipelines.

Any coding agent or automation that can generate or modify code, schemas, or configuration:

- **MUST** read this file in full before making any changes.
- **MUST** comply with all MUST/MUST NOT rules without exception.
- **MUST** abort rather than violate any rule in this document.
- **MUST** read `CONSTITUTION.md` §2 (Tech Stack) and §4 (Absolute Rules) before any task.
- **MUST NOT** include domain-specific rules (tables, fields, enums, endpoints) in this file —
  those belong in `CONSTITUTION.md` and task files.

---

## Core Programming Principles

### Explicit Over Implicit

The following are **PROHIBITED** unless an explicit, documented justification exists in code
comments or design notes:

- Implicit ORM relationship loading that can trigger unbounded queries.
- Nullable columns without explicit justification and documented meaning of `NULL`.
- Implicit cascade behaviors (delete, update) without explicit configuration and tests.
- Silent fallback behavior for critical paths (e.g. "if config missing, silently use default").
- Magic field inference — convention-only behavior without explicit configuration.
- Wildcard imports (`from x import *`) in production code.
- Implicit enum widening — adding values without review or documentation updates.

### Error Handling and Fail-Fast

- Code **MUST** fail fast on invalid state or impossible conditions.
- Swallowing exceptions without logging is **PROHIBITED**.
- Generic `except` blocks without re-raising or structured handling are **PROHIBITED**.
- User-facing errors **MUST** map to explicit, predictable responses without leaking internals.

### Side Effects and Purity

- Functions that perform side effects (I/O, DB writes, external calls) **MUST** be explicitly
  named and documented as such.
- Pure functions **MUST NOT** reach out to external systems, globals, or mutable shared state.

### Configuration

- All configuration **MUST** be externalized via environment variables or config files.
- Hardcoded configuration values are **PROHIBITED**.
- Missing required configuration **MUST** cause startup failure — not silent defaults —
  for critical systems (auth, persistence, external providers).
- The development environment **MUST** be started via Docker Compose from the project root
  before running any backend or frontend code locally:
  ```bash
  docker compose up -d
  ```
  Direct execution outside Docker Compose is permitted only for tests or one-off scripts.

### Frontend Design Governance

- All frontend work **MUST** treat `CONSTITUTION.md` as the single source of truth for
  tech stack choices (React, Vite, TypeScript, Tailwind).
- **TailAdmin (Free)** is the canonical UI shell and design baseline for Kaihle:
  - Dashboard-style apps (teacher, school admin, KaihleAdmin) **MUST** use TailAdmin-style
    layouts: left sidebar, top navbar, main content area with responsive grid/cards.
  - New pages **MUST** extend existing components in `packages/ui` — do not invent ad-hoc layouts.
- Agents **MUST NOT**:
  - Introduce additional UI kits (MUI, Chakra, shadcn, Flowbite, DaisyUI, Bootstrap) without
    a documented ADR explicitly approving the change.
  - Add CSS frameworks or design systems outside Tailwind CSS v3.
  - Mix visual paradigms within the same app (e.g. Material-style in a TailAdmin layout).
- When generating React components, agents **MUST**:
  - Use Tailwind utility classes compatible with TailAdmin (spacing, typography, colour tokens).
  - Keep layouts responsive using Tailwind grid/flex and the same breakpoints as TailAdmin.
  - Place shared elements in `packages/ui` — never duplicate markup across apps.
- Route-level pages **MUST** compose from `packages/ui` components and named layout wrappers
  (e.g. `DashboardLayout`, `AuthLayout`). Complex layout logic **MUST NOT** live in route files.

---

## Data and Schema Governance

### Single Source of Truth

- Every persisted piece of information **MUST** have exactly one canonical source of truth.
- Derived or denormalized data **MUST** document its origin, sync mechanism, and failure modes.

### Nullability and Defaults

- New columns **MUST** be `NOT NULL` by default unless there is a clear semantic need for `NULL`.
- Nullable columns **MUST** include an explanation in the migration or code comment, plus tests
  covering `NULL` behaviour.

### Constraints and Uniqueness

- Business invariants **MUST** be enforced at the database level (unique constraints, check
  constraints) wherever possible.
- Code-level checks **MUST NOT** be the sole enforcement of uniqueness where the DB can enforce it.

### Enum Governance

- Enum values are part of the persistent contract.
- Removing an enum value still present in data is **PROHIBITED** without a data migration.
- Reusing deprecated enum names or numeric codes is **PROHIBITED**.
- Adding a new enum value **MUST** include an update in `CONSTITUTION.md` or the relevant task
  file, and tests for all consumers that interpret the enum.

### Schema References

- Migrations **MUST NOT** embed application-specific logic (e.g. calling business services).
- Table and column specifics **MUST** be sourced from `kaihle_v2_1_schema.sql` and
  `CONSTITUTION.md` — not inferred from this document.

---

## Migration Discipline

### General Rules

- Every structural change to persisted data **MUST** go through a migration.
- Direct, ad-hoc schema modifications outside migrations are **PROHIBITED**.

### Downgrades and Reversibility

- Every migration **MUST** include a downgrade path unless the change is inherently irreversible,
  in which case the migration **MUST** document why and what the rollback strategy is.
- Data-destructive migrations (drops, truncations) **MUST** be preceded by a backup or
  equivalent safety mechanism, and clearly documented.

### Compatibility Windows

- Column renames, type changes, or restructuring **MUST** provide a compatibility window
  where old and new representations can safely coexist.

### Default Values and Backfill

- Adding non-nullable columns with defaults **MUST** include a clear backfill strategy for
  existing rows, and tests that verify legacy data behaves correctly before and after migration.

---

## Transactions and Persistence

- All database write operations **MUST** occur within an explicit transactional context.
- Cross-layer code **MUST NOT** perform partial writes across multiple services without a
  well-defined transaction or compensation mechanism.
- Multi-step changes that must succeed or fail together **MUST** be a single transaction
  or a clearly defined saga/compensation pattern.
- Implicit or auto-commit behaviour for critical writes is **PROHIBITED**.
- Any write in a background process **MUST** be idempotent or guarded by an idempotency key,
  and **MUST** assume it can be retried and executed more than once.

---

## Concurrency and Idempotency

- All write operations (APIs, CLI tools, background jobs) **MUST** be idempotent by design,
  **OR** clearly reject duplicate intent with a deterministic, documented error.
- Uniqueness and integrity **MUST** be enforced at the database level to prevent
  race-condition-induced duplication.
- Optimistic or pessimistic locking **MUST** be used where concurrent updates can conflict.
- Side effects external to the primary data store (emails, external calls) **MUST** use
  idempotency keys where supported, and be logged to prevent duplicate user-visible actions.

---

## Testing and Quality Gates

- Tests **MUST** assert behaviour and observable outcomes — not implementation details.
- Fragile, implementation-coupled tests are **PROHIBITED**.
- Test naming: `test_<what>_when_<condition>_then_<expected>`.
- For any new persistent model, tests **MUST** cover: creation and lifecycle, all uniqueness
  and constraint behaviour, cascade behaviour, and failure/validation paths.
- Integration tests **MUST** exercise real persistence and boundary layers where feasible.
- Over-mocking the data layer in integration tests is **PROHIBITED**.

---

## Logging and Observability

- All application and worker logs **MUST** be structured JSON — `structlog` to stdout.
- Use of `print()` or unstructured logging in production code is **PROHIBITED**.
- All interactions with external boundaries (DB transactions at high level, cache, message
  broker, external service calls) **MUST** be logged at INFO level minimum.
- Sensitive data **MUST NOT** be logged.
- Significant state transitions (status changes, approvals, impersonation) **MUST** be logged
  with: actor, previous state, new state, and correlation ID.
- A correlation ID **MUST** be propagated through all layers for every request or job
  (incoming request → internal services → background work). Every log entry **MUST** include it.

---

## Security and Privacy

- Secrets **MUST NOT** be hardcoded in code or stored in version control.
- All secrets **MUST** be provided via environment variables or a secrets manager.
- All entry points that mutate data or expose non-public information **MUST** require
  authentication and apply role-based authorization checks at the boundary layer.
- Silent privilege escalation or implicit role upgrades are **PROHIBITED**.
- Sensitive fields (passwords, tokens, PII) **MUST NOT** be logged or returned in API
  responses without explicit requirement and masking.
- Passwords **MUST** be stored as secure hashes (bcrypt or argon2). Plaintext or reversible
  encryption is **PROHIBITED**.
- Raw query string formatting that enables injection vulnerabilities is **PROHIBITED**.
- All external inputs **MUST** be validated and sanitized before use.

---

## Performance and Scalability Guardrails

- N+1 query patterns in hot paths are **PROHIBITED**.
- All list or search endpoints **MUST** implement pagination or explicit bounds.
  Unbounded scans over large datasets are **PROHIBITED**.
- Queries in hot paths **MUST** be backed by appropriate indexes.
- Long-running or blocking operations **MUST NOT** execute in synchronous request/response
  paths when they can be offloaded to async or background processing.
- External calls (third-party services, AI models) **MUST** have explicitly configured
  timeouts and clear failure/fallback behaviour.

---

## CI, Automation, and Failure Conditions

### Non-Negotiable CI Gates

A change **MUST NOT** be merged, deployed, or considered successful if any of the following:

- Test suite fails or service coverage drops below the threshold enforced by CI.
- Linters or formatters fail.
- Schema drift detected between code and migration history.
- Migrations fail to apply in a clean environment.
- Duplicate or conflicting model or migration files are detected.
- Static analysis or security checks report high-severity issues not explicitly waived.

### Agent Behaviour Under Failure

Automated agents that encounter any failure condition above **MUST**:

- Abort immediately.
- Surface the failure, its cause, and the full failing command output.
- **NOT** work around governance by disabling tests, linters, or checks.
- **NOT** proceed to the next task until the failure is resolved.

---

## Git Workflow

### Starting Any Task

Before writing any code, execute in order:

```bash
git checkout main
git pull origin main
git checkout -b <branch-name>
```

- Working directly on `main` is **PROHIBITED**.
- Starting on a stale local branch without pulling latest `main` is **PROHIBITED**.
- Code written before this sequence **MUST NOT** be committed.

### Branch Naming

Branch names **MUST** follow:

```
M{N}-{E}-T{N}_{type}/{short-description}
```

- `M{N}` — milestone (e.g. `M0`, `M1`)
- `{E}` — epic number (e.g. `1`, `4`)
- `T{N}` — task number (e.g. `T1`, `T3`)
- `{type}` — one of: `feature`, `fix`, `chore`, `migration`
- `{short-description}` — lowercase, hyphen-separated

Valid examples:
```
M0-1-T1_feature/init-monorepo
M1-4-T3_feature/gap-state-calculation
M6-3-T2_fix/error-handler
M0-2-T1_migration/initial-schema
```

Branch names not matching this format **MUST NOT** be pushed to `origin`.

### Commit Hygiene

Commits **MUST** use conventional commit format:

- `feat(scope): description`
- `fix(scope): description`
- `chore(scope): description`
- `migration(scope): description`

- Migration files **MUST** be committed together with the model changes they support.
- Debug code, commented-out blocks, and `TODO` markers **MUST NOT** appear in committed code.
- Unrelated changes **MUST NOT** be bundled into the same commit.
- Broken or untested code **MUST NOT** be committed.

### Task Completion and Pull Request

A task is **NOT** complete until **all** of the following are true:

1. All acceptance criteria in the task file (`docs/tasks/M{N}/M{N}-{E}-T{N}_*.md`) are met —
   verified by tests, not self-assessed.
2. Test coverage ≥ 80% on service files, enforced by the test runner.
3. `git status` is clean — no uncommitted or untracked changes.
4. All new environment variables are documented in `.env.example`.
5. Branch is pushed to `origin`.
6. A Pull Request is opened against `main` with a title matching the branch name and a
   description covering: what was built, decisions made, and how to verify.

Merging directly to `main` without a Pull Request is **PROHIBITED**.

---

## Final Principles

- When in doubt, **do less and be explicit** — introduce the minimum necessary surface area
  with maximum clarity.
- If a required behaviour is not covered here, default to the most conservative, safe, and
  maintainable option, then raise a documentation update.