# AGENTS.md
# Kaihle Engineering Governance — v1.1

This document defines the **non-negotiable engineering governance** for the Kaihle codebase.

- It applies to **all contributors** (humans and automated agents).
- It governs **how** software is designed, implemented, migrated, tested, and operated.
- Domain models, endpoints, enums, tech stack, and data shapes are defined in **CONSTITUTION.md** and task files — not here.

If this document and any other document conflict on **engineering rules**, **this document wins**.
If this document and the codebase conflict on **domain details**, **CONSTITUTION.md and the codebase** win; this file **MUST** then be updated.

---

## 1. Scope and Agent Contract

### 1.1 Scope

This constitution applies to:

- All backend services.
- All frontend applications.
- All background/worker processes.
- All data stores, queues, and external service integrations.
- All CI/CD pipelines and automation that can modify the codebase or schema.

### 1.2 Applicability to Agents

Any coding agent or automation that can generate or modify code, schemas, or configuration:

- **MUST** read this file in full before making any changes.
- **MUST** comply with all MUST/MUST NOT rules without exception.
- **MUST** abort rather than violate any rule in this document.
- Before implementing any frontend task, agents **MUST** read CONSTITUTION.md sections 2 (Locked Tech Stack) and 3 (Repository Structure) and comply with the Frontend Design Governance rules in this document.


---

## 2. Language and Interpretation

### 2.1 Normative Terms

- **MUST / MUST NOT / SHALL / SHALL NOT / REQUIRED / PROHIBITED** are **binding**.
- **MAY / OPTIONAL** are permissive.
- **SHOULD / SHOULD NOT / PREFER / AVOID** are strongly recommended but not binding.

### 2.2 Precedence

If any guideline elsewhere uses softer language (e.g., "should") and conflicts with a **MUST**
here, the rule in this document prevails.

---

## 3. Core Programming Principles

### 3.1 Explicit Over Implicit

The following are **PROHIBITED** unless an explicit, documented justification exists in code
comments and/or design notes:

- Implicit or automatic ORM relationship loading that can trigger unbounded queries.
- Nullable columns without explicit justification and documented meaning of `NULL`.
- Implicit cascade behaviors (delete, update) without explicit configuration and tests.
- Silent fallback behavior (e.g., "if config missing, silently use default") for critical paths.
- "Magic" field inference (convention-only behavior without explicit configuration).
- Wildcard imports (e.g., `from x import *`) in production code.
- Implicit enum widening (adding values without review or documentation updates).

### 3.2 Error Handling and Fail-Fast

- Code **MUST**:
  - Fail fast on invalid state or impossible conditions.
  - Avoid swallowing exceptions without logging.
  - Avoid generic `except` blocks without re-raising or structured handling.
- User-facing errors **MUST** be mapped to explicit, predictable responses without leaking
  sensitive details.

### 3.3 Side Effects and Purity

- Functions that perform side effects (I/O, DB writes, external calls) **MUST** be explicitly
  named and documented as such.
- Pure functions (no side effects) **MUST NOT** reach out to external systems, globals, or
  mutable shared state.

### 3.4 Configuration

- All configuration **MUST** be externalized (environment variables, config files) and
  **MUST NOT** be hardcoded in code.
- Missing required configuration **MUST** cause startup failure, not silent defaults for
  critical systems (auth, persistence, external providers).
- The development environment **MUST** be started via Docker Compose from the project root
  before running any backend or frontend code locally. Direct execution outside Docker Compose
  is permitted only for running tests or one-off scripts.


### 3.5 Frontend Design Governance

- All frontend work **MUST** treat CONSTITUTION.md as the single source of truth for:
  - Tech stack choices (React, Vite, TypeScript, Tailwind).
  - The approved UI library and layout system.

- TailAdmin (Free) is the canonical UI shell and design baseline for Kaihle:
  - Dashboard-style apps (teacher, school admin, KaihleAdmin) **MUST** reuse TailAdmin-style layouts:
    - Left sidebar navigation.
    - Top navbar / header region.
    - Main content area with responsive grid/cards.
  - New pages **MUST** extend existing TailAdmin-style components in `packages/ui` rather than inventing ad-hoc layouts.

- Agents and contributors **MUST** NOT:
  - Introduce additional UI kits (e.g. MUI, Chakra, shadcn, Flowbite, DaisyUI, Bootstrap) without a documented ADR explicitly approving the change.
  - Add global CSS frameworks or design systems outside Tailwind CSS v3 and TailAdmin-style components.
  - Mix visual paradigms (e.g. Material-style components in a TailAdmin layout) within the same app.

- When generating React components for any frontend app, agents MUST:
  - Use Tailwind utility classes and patterns compatible with TailAdmin examples (spacing, typography, color tokens, breakpoints).
  - Keep layouts responsive using Tailwind’s grid/flex utilities and the same breakpoint strategy as TailAdmin.
  - Place shared UI elements in `packages/ui` and import them into `apps/teacher`, `apps/student`, and `apps/parent` instead of duplicating markup.

- Route-level pages MUST:
  - Compose UI from shared `packages/ui` components plus TailAdmin-style layout wrappers.
  - Avoid embedding complex layout logic directly in route components; layout wrappers SHOULD be reusable and clearly named (e.g. `DashboardLayout`, `AuthLayout`).

- If a required UI pattern cannot be expressed cleanly using TailAdmin-style Tailwind components:
  - The agent **MUST** document the limitation in the relevant task or ADR.
  - The change **MUST** default to the most conservative option that keeps consistency with existing TailAdmin-based pages.


---

## 4. Data and Schema Governance

### 4.1 Single Source of Truth

- Every persisted piece of information **MUST** have exactly one canonical source of truth.
- Derived or denormalized data **MUST** clearly document:
  - Its origin.
  - How and when it is synchronized.
  - Failure modes when synchronization fails.

### 4.2 Nullability and Defaults

- New columns **MUST**:
  - Be **NOT NULL** by default, unless there is a clear semantic need for `NULL`.
  - Use explicit defaults only where semantically correct and documented.
- Introducing a nullable column or nullable behavior **MUST** come with:
  - Explanation in a migration or code comment.
  - Tests covering `NULL` behavior.

### 4.3 Constraints and Uniqueness

- Business invariants **MUST** be enforced at the database level wherever possible
  (e.g., unique constraints, check constraints).
- Code-level checks **MUST NOT** be the only enforcement of uniqueness or invariants
  where the database can enforce them.

### 4.4 Enum Governance

Enum values **MUST** be treated as part of the persistent contract.

- Enum values **MUST NOT** be removed while still present in data; removal requires a data
  migration and compatibility strategy.
- Enum values **MUST NOT** be reused (no recycling of deprecated names or numeric codes).
- Enum expansion (adding a new value) **MUST**:
  - Include an update in CONSTITUTION.md or the relevant task file.
  - Include tests for all consumers (backend and frontend) that interpret the enum.
- Deprecated enum values **MUST** be explicitly marked as deprecated and handled predictably.

### 4.5 Schema References

- Migrations **MUST NOT** embed application-specific logic (e.g., calling business services).
- Data shape, table, and column specifics **MUST** be sourced from `kaihle_v2_1_schema.sql`
  and CONSTITUTION.md — not inferred from this document.

---

## 5. Migration Discipline

### 5.1 General Rules

- Every structural change to persisted data **MUST** go through a migration.
- Direct, ad-hoc schema modifications outside migrations are **PROHIBITED**.

### 5.2 Downgrades and Reversibility

- Every migration **MUST** include a downgrade path unless:
  - The change is inherently irreversible (e.g., data compaction), **and**
  - The migration explicitly documents why it is irreversible and what backup/rollback
    strategy exists.
- Data-destructive migrations (drops, truncations, transformations that lose information)
  **MUST**:
  - Clearly log and document the behavior.
  - Be preceded by a backup or equivalent safety mechanism.

### 5.3 Compatibility Windows

- Column renames, type changes, or restructuring **MUST**:
  - Provide a compatibility window where old and new representations can safely coexist.
  - Include explicit migration steps for both backend and frontend, where applicable.

### 5.4 Default Values and Backfill

- Adding non-nullable columns with defaults **MUST** have:
  - A clear backfill strategy for existing rows.
  - Tests that verify legacy data behaves correctly pre- and post-migration.

---

## 6. Transactions and Persistence

### 6.1 Transaction Boundaries

- All database write operations **MUST** occur within an explicit transactional context.
- Cross-layer code **MUST NOT** perform partial writes across multiple services without
  a well-defined transaction or compensation mechanism.

### 6.2 Atomicity

- Multi-step changes that must succeed or fail together **MUST** be implemented as a single
  transaction or as a clearly defined saga/compensation pattern.
- Implicit or auto-commit behavior for critical writes is **PROHIBITED**.

### 6.3 Background Processing and Idempotency

- Any write performed in a background process **MUST**:
  - Be idempotent or guarded by an idempotency key and uniqueness constraints.
  - Assume that tasks can be retried and potentially executed more than once.

---

## 7. Concurrency and Idempotency

### 7.1 Idempotent Endpoints and Operations

All write operations (including APIs, CLI tools, and background jobs) **MUST** be:

- Idempotent by design, **OR**
- Clearly reject duplicate intent with a deterministic, documented error.

### 7.2 Uniqueness and Concurrency

- Uniqueness and integrity **MUST** be enforced at the database level to prevent
  race-condition-induced duplication.
- Optimistic or pessimistic locking strategies **MUST** be used where concurrent updates
  can conflict.

### 7.3 Retries and Failure Handling

- Any operation that may be retried (due to network issues, worker restarts, or explicit
  retry mechanisms) **MUST** be safe under double execution.
- Side effects external to the primary data store (emails, external calls, etc.) **MUST**:
  - Use idempotency keys where supported.
  - Be logged and guarded to avoid duplicate user-visible actions when retried.

---

## 8. Testing and Quality Gates

### 8.1 Test Focus

- Tests **MUST** assert behavior and observable outcomes, not incidental implementation details.
- Overreliance on fragile implementation-coupled tests is **PROHIBITED**.
- Test naming convention: `test_<what>_when_<condition>_then_<expected>`.

### 8.2 Model and Persistence Tests

For any new persistent model or equivalent construct, the following **MUST** be covered:

- Creation and basic lifecycle.
- All uniqueness and integrity constraints.
- Cascade and relationship behavior (where defined).
- Failure paths and validation errors.

### 8.3 Integration and Boundary Tests

- Integration tests **MUST** exercise real persistence and boundary layers where feasible
  (database, queues, etc.).
- Over-mocking of the data layer in tests that are meant to validate integration behavior
  is **PROHIBITED**.

---

## 9. Logging and Observability

### 9.1 Structured Logging

- All logs from application code and workers **MUST** be structured (e.g., JSON or equivalent)
  to support querying and correlation.
- Use of ad-hoc `print` or unstructured logging in production code is **PROHIBITED**.

### 9.2 Boundary Logging

- All interactions with external boundaries **MUST** be logged at least at INFO level:
  - Database transactions (high level, not every query).
  - Cache and message broker interactions (high-level operations).
  - Calls to external services and providers.
- Sensitive data **MUST NOT** be logged.

### 9.3 State Transitions

Significant state transitions (status changes, approvals, escalations, impersonation, etc.)
**MUST** be logged with:

- Actor (user or system).
- Previous state.
- New state.
- Correlation ID for the request or job.

### 9.4 Correlation

- A correlation ID **MUST** be propagated through all layers for each request or job:
  - Incoming request → internal services → background work.
- Logs **MUST** include this ID on every entry.

---

## 10. Security and Privacy

### 10.1 Secrets and Credentials

- Secrets **MUST NOT** be hardcoded in code or stored in version control.
- All secrets **MUST** be provided via secure configuration mechanisms (environment
  variables, secrets managers).

### 10.2 Authentication and Authorization

- All entry points that mutate data or expose non-public information **MUST**:
  - Require authentication.
  - Apply role- or permission-based authorization checks at the boundary layer.
- Silent privilege escalation or implicit role upgrades are **PROHIBITED**.

### 10.3 Sensitive Data Handling

- Sensitive fields (passwords, tokens, secrets, PII beyond what is necessary) **MUST NOT**:
  - Be logged.
  - Be returned in API responses or UI views without explicit requirement and masking.
- Passwords **MUST** be stored only as secure hashes using a modern algorithm (e.g.,
  bcrypt or argon2). Plaintext or reversible encryption is **PROHIBITED**.

### 10.4 Code and Query Safety

- Raw query string formatting that can lead to injection vulnerabilities is **PROHIBITED**.
- All external inputs **MUST** be validated and sanitized prior to use.

---

## 11. Performance and Scalability Guardrails

### 11.1 Queries and Data Access

- N+1 query patterns in hot paths are **PROHIBITED**.
- All list or search endpoints **MUST**:
  - Implement pagination or explicit bounds.
  - Avoid unbounded scans over large datasets.

### 11.2 Indexes

- Queries introduced in hot paths **MUST** be backed by appropriate indexes.
- Introducing a query that scans large tables without an index on filter conditions is
  **PROHIBITED** without documented justification and monitoring.

### 11.3 Blocking Operations

- Long-running or blocking operations **MUST NOT** execute in synchronous request/response
  paths when they can be offloaded to asynchronous or background processing.
- External calls (to third-party services, AI models, etc.) **MUST** have:
  - Reasonable, explicitly configured timeouts.
  - Clear failure behavior and fallback where appropriate.

---

## 12. CI, Automation, and Failure Conditions

### 12.1 Non-Negotiable CI Gates

A change **MUST NOT** be merged, deployed, or considered successful if any of the following occur:

- Test suite fails or service coverage drops below the threshold enforced by CI.
- Linters or formatters fail.
- Schema drift detected between code and database migration history.
- Migrations fail to apply in a clean environment.
- Duplicate or conflicting model or migration files are detected.
- Static analysis or security checks report high-severity issues that are not explicitly
  waived with documented justification.

### 12.2 Agent Behavior Under Failure

Automated agents that encounter any of the failure conditions above **MUST**:

- Abort implementation or changes immediately.
- Surface the failure, its cause, and the failing command or check output.
- **NOT** work around governance rules by disabling tests, linters, or checks.
- **NOT** proceed to the next task until the failure is resolved.

---

## 13. Git Workflow

### 13.1 Starting Any Task

Before writing any code, the following sequence **MUST** be executed in order:

```bash
git checkout main
git pull origin main
git checkout -b <branch-name>
```

- Working directly on `main` is **PROHIBITED**.
- Starting work on a stale local branch without pulling the latest `main` is **PROHIBITED**.
- Any code written before this sequence is executed **MUST NOT** be committed.

### 13.2 Branch Naming Convention

Branch names **MUST** follow this exact format:

```
M{N}-{E}-T{N}_{type}/{short-description}
```

Where:

- `M{N}` is the milestone number (e.g., `M0`, `M1`, `M6`).
- `{E}` is the epic number within the milestone (e.g., `1`, `4`).
- `T{N}` is the task number within the epic (e.g., `T1`, `T3`).
- `{type}` is one of: `feature`, `fix`, `chore`, `migration`.
- `{short-description}` is lowercase and hyphen-separated.

**Valid examples:**

```
M0-1-T1_feature/init-monorepo
M1-4-T3_feature/gap-state-calculation
M3-1-T1_feature/content-curator
M6-3-T2_fix/error-handler
M0-2-T1_migration/initial-schema
```

Branch names that do not follow this format **MUST NOT** be pushed to `origin`.
The branch name **MUST** match the task file being implemented — no ambiguity allowed.

### 13.3 Commit Hygiene

Commits **MUST** use conventional commit format:

- `feat(scope): description` — new functionality
- `fix(scope): description` — bug fix
- `chore(scope): description` — config, tooling, documentation
- `migration(scope): description` — schema migration only

Additional rules:

- Migration files **MUST** be committed together with the model changes they support.
  Committing them separately is **PROHIBITED**.
- Debug code, commented-out blocks, and `TODO` markers **MUST NOT** appear in committed
  production code.
- Unrelated changes **MUST NOT** be bundled into the same commit.
- Broken or untested code **MUST NOT** be committed at any point.

### 13.4 Task Completion and Pull Request

A task is **NOT** complete and **MUST NOT** be considered closed until all of the following
are true:

1. All acceptance criteria defined in the **task file** (`docs/tasks/M{N}/M{N}-{E}-T{N}_*.md`)
   are met. Acceptance criteria in task files are authoritative — not self-assessed.
2. Test coverage >= 90% on service files, enforced by the test runner — not self-assessed.
3. `git status` is clean — no uncommitted or untracked changes.
4. All new environment variables are documented in `.env.example`.
5. Branch is pushed to `origin`:

```bash
git push origin M{N}-{E}-T{N}_{type}/short-description
```

6. A Pull Request is opened against `main` with:
   - A title that matches the branch name and task ID.
   - A description covering: what was built, decisions made, and how to verify.

Merging directly to `main` without a Pull Request is **PROHIBITED**.

---

## 14. Final Principles

- When in doubt, **do less and be explicit**: introduce the minimum necessary surface area
  with maximum clarity.
- If a required behavior is not covered here, the change **MUST** default to the most
  conservative, safe, and maintainable option, followed by a governance or documentation
  update.