# Kaihle Engineering Governance

This document defines the **non-negotiable engineering rules** for the Kaihle codebase.
It applies to all contributors — human and automated agents alike.
It governs **how** software is engineered. Domain models, tech stack, enums, and endpoints
are defined in `CONSTITUTION.md` and task files — not here.

**Precedence:** Rules are loaded in this order (highest → lowest):
`.kilo/rules/` → `AGENTS.md` → global rules.
If this document conflicts with a rule file, the rule file wins.
If this document conflicts with `CONSTITUTION.md` on domain details, `CONSTITUTION.md` wins.
If this document conflicts with any other document on **engineering discipline**, this document wins.

---

## Agent Contract

Any agent or automation that can generate or modify code, schemas, or configuration:

- **MUST** read this file in full before making any changes.
- **MUST** read `CONSTITUTION.md` §2 (Tech Stack) and §4 (Absolute Rules) before any task.
- **MUST** abort rather than violate any rule in this document.
- **MUST NOT** include domain-specific rules (tables, fields, enums, endpoints) in this file —
  those belong in `CONSTITUTION.md` and task files.
- **MUST NOT** make any code changes without explicit approval from the user.
  When asked to analyse or review, present findings first, then WAIT for approval.
- **MUST NOT** operate in "code mode" unless explicitly instructed by the user.

---

## Core Programming Principles

### Explicit Over Implicit

The following are **PROHIBITED** unless an explicit, documented justification exists:

- Implicit ORM relationship loading that can trigger unbounded queries.
- Nullable columns without explicit justification and documented meaning of `NULL`.
- Implicit cascade behaviours (delete, update) without explicit configuration and tests.
- Silent fallback behaviour for critical paths.
- Magic field inference — convention-only behaviour without explicit configuration.
- Wildcard imports (`from x import *`) in production code.
- Implicit enum widening — adding values without review or documentation updates.

### Error Handling and Fail-Fast

- Code **MUST** fail fast on invalid state or impossible conditions.
- Swallowing exceptions without logging is **PROHIBITED**.
- Generic `except` blocks without re-raising or structured handling are **PROHIBITED**.
- User-facing errors **MUST** map to explicit, predictable responses without leaking internals.

### Side Effects and Purity

- Functions that perform side effects (I/O, DB writes, external calls) **MUST** be explicitly named and documented.
- Pure functions **MUST NOT** reach out to external systems, globals, or mutable shared state.

### Configuration

- All configuration **MUST** be externalized via environment variables or config files.
- Hardcoded configuration values are **PROHIBITED**.
- Missing required configuration **MUST** cause startup failure — not silent defaults.
- The development environment **MUST** be started via Docker Compose from the project root:
  ```bash
  docker compose up -d
  ```

### Type Checking

- Inline `# type: ignore` comments **MUST NOT** be used in production code.
- Type issues **MUST** be resolved via `mypy.ini`, not inline ignores.

---

## Frontend Design Governance

**Read `docs/design/DESIGN_SYSTEM.md` before writing any frontend component.**
This section states the enforcement rules — full specs are in the design system file.

- All frontend work **MUST** treat `CONSTITUTION.md` as the source of truth for tech stack.
- **TailAdmin (Free)** is the canonical UI shell for dashboard apps (Teacher, School Admin, Kaihle Admin).
- No additional UI kits (MUI, Chakra, shadcn, Flowbite, DaisyUI, Bootstrap) without an ADR.
- All new layout components **MUST** live in `packages/ui/src/layouts/`.

### Five-Role Design System

| Role | Layout wrapper | Sidebar | Primary button | Heading font |
|---|---|---|---|---|
| Kaihle Admin | `AdminLayout` | White, gray borders | Green | Inter |
| School Admin | `DashboardLayout variant="school-admin"` | White, green borders | Green | Fraunces |
| Teacher | `DashboardLayout variant="teacher"` | White, gray borders | **Gold** | Fraunces |
| Student | `StudentLayout` | White sidebar (left) | Green | Fraunces |
| Parent | `ParentLayout` | White sidebar (left) | Text link | Lora |

### Color Rules (Memorise — Violations Are Silent Bugs)

- Teacher primary action buttons are **gold** (`bg-brand-gold`) — NEVER green.
- Mastery Strong = `#16a34a` (`brand-green`) — NOT `#10b981` (emerald-500).
- All mastery logic flows through `getMasteryStyle()` from `@kaihle/types`.
- All color classes use `brand-*` or `role-*` tokens. No raw `indigo-*`, `emerald-*`, `violet-*`.
- Hex values live ONLY in `tailwind.config.js` — everywhere else uses token names.
- Custom Tailwind tokens MUST be registered for non-standard sizes (9px, 10px, 11px).

### Component Rules

- Use `min-h-[44px]` on all interactive elements (touch targets).
- Add `focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2` to all interactive elements.
- Pair every color-only status indicator with `aria-label`.
- All modals **MUST** use `Modal` from `packages/ui` (Radix UI wrapper) — Rule 21.
- Loading states follow Rule 22: skeletons for page loads, spinners for button actions.

---

## Data and Schema Governance

- Every persisted piece of information **MUST** have exactly one canonical source of truth.
- New columns **MUST** be `NOT NULL` by default unless there is a clear semantic need for `NULL`.
- Nullable columns **MUST** include an explanation plus tests covering `NULL` behaviour.
- Business invariants **MUST** be enforced at the database level wherever possible.
- Enum values are part of the persistent contract. Removing an enum value still in data is **PROHIBITED**.
- Table and column specifics **MUST** be sourced from `kaihle_v2_1_schema.sql` and `CONSTITUTION.md`.

---

## Migration Discipline

- Every structural change to persisted data **MUST** go through a migration.
- Direct, ad-hoc schema modifications outside migrations are **PROHIBITED**.
- Every migration **MUST** include a downgrade path unless inherently irreversible (document why).
- Data-destructive migrations **MUST** be preceded by a backup or equivalent safety mechanism.
- Adding non-nullable columns with defaults **MUST** include a backfill strategy and tests.
- Migrations **MUST NOT** embed application-specific logic (e.g. calling business services).

---

## Transactions and Persistence

- All database write operations **MUST** occur within an explicit transactional context.
- Multi-step changes that must succeed or fail together **MUST** be a single transaction or a clearly defined saga/compensation pattern.
- Implicit or auto-commit behaviour for critical writes is **PROHIBITED**.
- Any write in a background process **MUST** be idempotent or guarded by an idempotency key.

---

## Concurrency and Idempotency

- All write operations **MUST** be idempotent by design, OR clearly reject duplicate intent with a deterministic error.
- Uniqueness and integrity **MUST** be enforced at the database level to prevent race-condition-induced duplication.
- Side effects external to the primary data store (emails, external calls) **MUST** use idempotency keys where supported.

---

## Testing and Quality Gates

- Tests **MUST** assert behaviour and observable outcomes — not implementation details.
- Test naming: `test_<what>_when_<condition>_then_<expected>`.
- For any new persistent model, tests **MUST** cover: creation, lifecycle, uniqueness/constraint behaviour, cascades, and failure paths.
- Integration tests **MUST** exercise real persistence and boundary layers where feasible.
- Over-mocking the data layer in integration tests is **PROHIBITED**.

---

## Logging and Observability

- All logs **MUST** be structured JSON via `structlog` to stdout.
- `print()` or unstructured logging in production code is **PROHIBITED**.
- All interactions with external boundaries **MUST** be logged at INFO level minimum.
- Sensitive data **MUST NOT** be logged.
- Significant state transitions **MUST** be logged with: actor, previous state, new state, correlation ID.
- A correlation ID **MUST** be propagated through all layers for every request or job.

---

## Security and Privacy

- Secrets **MUST NOT** be hardcoded or stored in version control.
- All entry points that mutate data **MUST** require authentication and role-based authorization.
- Silent privilege escalation or implicit role upgrades are **PROHIBITED**.
- Passwords **MUST** be stored as secure hashes (bcrypt or argon2). Plaintext is **PROHIBITED**.
- All external inputs **MUST** be validated and sanitized before use.

---

## Performance Guardrails

- N+1 query patterns in hot paths are **PROHIBITED**.
- All list or search endpoints **MUST** implement pagination or explicit bounds.
- Long-running operations **MUST NOT** execute in synchronous request/response paths.
- External calls (third-party services, AI models) **MUST** have explicitly configured timeouts.

---

## CI and Failure Conditions

A change **MUST NOT** be merged if any of the following:

- Test suite fails or coverage drops below threshold.
- Linters or formatters fail.
- Schema drift detected between code and migration history.
- Duplicate or conflicting model or migration files detected.
- Static analysis or security checks report high-severity issues.

Agents that encounter a CI failure **MUST** abort, surface the failure, and NOT work around governance by disabling tests or checks.

---

## Git Workflow

### Starting Any Task

```bash
git checkout main
git pull origin main
git checkout -b <branch-name>
```

Working directly on `main` is **PROHIBITED**.

### Branch Naming

```
M{N}-{E}-T{N}_{type}/{short-description}
```

Examples: `M1-4-T3_feature/gap-state-calculation`, `M6-3-T2_fix/error-handler`

### Commit Format

- `feat(scope): description`
- `fix(scope): description`
- `chore(scope): description`
- `migration(scope): description`

Debug code, commented-out blocks, and `TODO` markers **MUST NOT** appear in committed code.

### Task Completion

A task is **NOT** complete until ALL of the following are true:

1. All acceptance criteria in the task file are met — verified by tests, not self-assessed.
2. Test coverage ≥ 80% on service files.
3. `git status` is clean.
4. All new environment variables are documented in `.env.example`.
5. Branch is pushed to `origin`.
6. A Pull Request is opened against `main`.

Merging directly to `main` without a Pull Request is **PROHIBITED**.

---

## Final Principles

- When in doubt, **do less and be explicit** — introduce the minimum necessary surface area with maximum clarity.
- If a required behaviour is not covered here, default to the most conservative, safe, and maintainable option, then raise a documentation update.
