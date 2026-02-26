# AGENTS.md
# Kaihle Engineering Governance Constitution (v2)

This document defines the **non-negotiable engineering governance** for the Kaihle codebase.

- It applies to **all contributors** (humans and automated agents).
- It governs **how** software is designed, implemented, migrated, tested, and operated.
- It is **architecture-neutral** and **product-neutral**: domain models, endpoints, phases, and data shapes are defined in the **Product Plan** (e.g. `mvp_product_plan.md`), not here.
- It is a **living governance file**. Section 13 defines how it may evolve.

If this document and any other document conflict on engineering rules, **this document wins**.
If this document and the codebase conflict on domain details, the **Product Plan and codebase** win; this file MUST then be updated.

---

## 1. Scope and Relationship to Other Documents

1.1 **Scope**

- This constitution applies to:
  - All backend services.
  - All frontend applications.
  - All background/worker processes.
  - All data stores, queues, and external service integrations.
  - All CI/CD pipelines and automation that can modify the codebase or schema.

1.2 **Product Plan Relationship**

- The **Product Plan** defines:
  - Domain models, tables, fields, enums, and their semantics.
  - Endpoints, use cases, and acceptance criteria.
  - Build phases and delivery sequence.
- **AGENTS.md** defines:
  - Programming discipline.
  - Data, migration, and transaction rules.
  - Security, observability, performance, and CI failure conditions.
  - Governance evolution.

- No domain-specific rule (e.g., about a particular table, field, or business entity) MAY appear in this file.
  - Such rules MUST live in the Product Plan or domain-specific documentation.

1.3 **Applicability to Agents**

- Any coding agent or automation that can generate or modify code, schemas, or configuration:
  - **MUST** read this file in full before making changes.
  - **MUST** comply with all MUST/MUST NOT rules.
  - **MUST** abort rather than violate any rule in this document.

---

## 2. Language and Interpretation

2.1 **Normative Terms**

- **MUST / MUST NOT / SHALL / SHALL NOT / REQUIRED / PROHIBITED** are **binding**.
- **MAY / OPTIONAL** are permissive.
- **SHOULD / SHOULD NOT / PREFER / AVOID** are strongly recommended but not binding.

2.2 **Precedence**

- If any guideline elsewhere uses softer language (e.g., “should”) and conflicts with a **MUST** here, the rule in this document prevails.

---

## 3. Core Programming Principles

3.1 **Explicit Over Implicit**

The following are **PROHIBITED** unless an explicit, documented justification exists in code comments and/or design notes:

- Implicit or automatic ORM relationship loading that can trigger unbounded queries.
- Nullable columns without explicit justification and documented meaning of `NULL`.
- Implicit cascade behaviors (delete, update) without explicit configuration and tests.
- Silent fallback behavior (e.g., “if config missing, silently use default”) for critical paths.
- “Magic” field inference (convention-only behavior without explicit configuration).
- Wildcard imports (e.g., `from x import *`) in production code.
- Implicit enum widening (adding values without review or documentation updates).

3.2 **Error Handling and Fail-Fast**

- Code **MUST**:
  - Fail fast on invalid state or impossible conditions.
  - Avoid swallowing exceptions without logging.
  - Avoid generic `except` blocks without re-raising or structured handling.
- User-facing errors **MUST** be mapped to explicit, predictable responses without leaking sensitive details.

3.3 **Side Effects and Purity**

- Functions that perform side effects (I/O, DB writes, external calls) **MUST** be explicitly named and documented as such.
- Pure functions (no side effects) **MUST NOT** reach out to external systems, globals, or mutable shared state.

3.4 **Configuration**

- All configuration **MUST** be externalized (environment variables, config files) and **MUST NOT** be hardcoded in code.
- Missing required configuration **MUST** cause startup failure, not silent defaults for critical systems (auth, persistence, external providers).

---

## 4. Data and Schema Governance

4.1 **Single Source of Truth**

- Every persisted piece of information **MUST** have exactly one canonical source of truth.
- Derived or denormalized data **MUST** clearly document:
  - Its origin.
  - How and when it is synchronized.
  - Failure modes when synchronization fails.

4.2 **Nullability and Defaults**

- New columns **MUST**:
  - Be **NOT NULL** by default, unless there is a clear semantic need for `NULL`.
  - Use explicit defaults only where semantically correct and documented.
- Introducing a nullable column or nullable behavior **MUST** come with:
  - Explanation in a migration or code comment.
  - Tests covering `NULL` behavior.

4.3 **Constraints and Uniqueness**

- Business invariants **MUST** be enforced at the database level wherever possible (e.g., unique constraints, check constraints).
- Code-level checks **MUST NOT** be the only enforcement of uniqueness or invariants where the database can enforce them.

4.4 **Enum Governance**

- Enum values **MUST** be treated as part of the persistent contract.
- The following rules apply:
  - Enum values **MUST NOT** be removed while still present in data; removal requires a data migration and compatibility strategy.
  - Enum values **MUST NOT** be reused (no recycling of deprecated names or numeric codes).
  - Enum expansion (adding a new value) **MUST**:
    - Include an update in the Product Plan or equivalent domain documentation.
    - Include tests for all consumers (backend and frontend) that interpret the enum.
  - Deprecated enum values **MUST** be explicitly marked as deprecated and handled predictably.

4.5 **Schema References**

- Migrations **MUST NOT** embed application-specific logic (e.g., calling business services).
- Data shape, table, and column specifics **MUST** be described in the Product Plan, not in this document.

---

## 5. Migration Discipline

5.1 **General Rules**

- Every structural change to persisted data **MUST** go through a migration.
- Direct, ad-hoc schema modifications outside migrations are **PROHIBITED**.

5.2 **Downgrades and Reversibility**

- Every migration **MUST** include a downgrade path unless:
  - The change is inherently irreversible (e.g., data compaction), and
  - The migration explicitly documents why it is irreversible and what backup/rollback strategy exists.
- Data-destructive migrations (drops, truncations, transformations that lose information) **MUST**:
  - Clearly log and document the behavior.
  - Be preceded by a backup or equivalent safety mechanism.

5.3 **Compatibility Windows**

- Column renames, type changes, or restructuring **MUST**:
  - Provide a compatibility window where old and new representations can safely coexist.
  - Include explicit migration steps for both backend and frontend, where applicable.

5.4 **Default Values and Backfill**

- Adding non-nullable columns with defaults **MUST** have:
  - A clear backfill strategy for existing rows.
  - Tests that verify legacy data behaves correctly pre- and post-migration.

---

## 6. Transactions and Persistence

6.1 **Transaction Boundaries**

- All database write operations **MUST** occur within an explicit transactional context.
- Cross-layer code **MUST NOT** perform partial writes across multiple services without a well-defined transaction or compensation mechanism.

6.2 **Atomicity**

- Multi-step changes that must succeed or fail together **MUST** be implemented as a single transaction or as a clearly defined saga/compensation pattern.
- Implicit or auto-commit behavior for critical writes is **PROHIBITED**.

6.3 **Background Processing and Idempotency**

- Any write performed in a background process **MUST**:
  - Be idempotent or guarded by an idempotency key and uniqueness constraints.
  - Assume that tasks can be retried and potentially executed more than once.

---

## 7. Concurrency and Idempotency

7.1 **Idempotent Endpoints and Operations**

- All write operations (including APIs, CLI tools, and background jobs) **MUST** be:
  - Idempotent by design **OR**
  - Clearly reject duplicate intent with a deterministic, documented error.

7.2 **Uniqueness and Concurrency**

- Uniqueness and integrity **MUST** be enforced at the database level to prevent race-condition-induced duplication.
- Optimistic or pessimistic locking strategies **MUST** be used where concurrent updates can conflict.

7.3 **Retries and Failure Handling**

- Any operation that may be retried (due to network issues, worker restarts, or explicit retry mechanisms) **MUST** be safe under double execution.
- Side effects external to the primary data store (emails, external calls, etc.) **MUST**:
  - Use idempotency keys where supported.
  - Be logged and guarded to avoid duplicate user-visible actions when retried.

---

## 8. Testing and Quality Gates

8.1 **Coverage**

- Global test coverage **MUST** be ≥ 90% for the main application modules.
- New code **MUST** not reduce overall coverage below this threshold.

8.2 **Test Focus**

- Tests **MUST** assert behavior and observable outcomes, not incidental implementation details.
- Overreliance on fragile implementation-coupled tests is **PROHIBITED**.

8.3 **Model and Persistence Tests**

For any new persistent model or equivalent construct, the following **MUST** be covered:

- Creation and basic lifecycle.
- All uniqueness and integrity constraints.
- Cascade and relationship behavior (where defined).
- Failure paths and validation errors.

8.4 **Integration and Boundary Tests**

- Integration tests **MUST** exercise real persistence and boundary layers where feasible (database, queues, etc.).
- Over-mocking of the data layer in tests that are meant to validate integration behavior is **PROHIBITED**.

---

## 9. Logging and Observability

9.1 **Structured Logging**

- All logs from application code and workers **MUST** be structured (e.g., JSON or equivalent) to support querying and correlation.
- Use of ad-hoc `print` or unstructured logging in production code is **PROHIBITED**.

9.2 **Boundary Logging**

- All interactions with external boundaries **MUST** be logged at least at INFO level:
  - Database transactions (high level, not every query).
  - Cache and message broker interactions (high-level operations).
  - Calls to external services and providers.
- Sensitive data **MUST NOT** be logged.

9.3 **State Transitions**

- Significant state transitions (status changes, approvals, escalations, impersonation, etc.) **MUST** be logged with:
  - Actor (user or system).
  - Previous state.
  - New state.
  - Correlation ID for the request or job.

9.4 **Correlation**

- A correlation ID **MUST** be propagated through all layers for each request or job:
  - Incoming request → internal services → background work.
  - Logs **MUST** include this ID.

---

## 10. Security and Privacy

10.1 **Secrets and Credentials**

- Secrets **MUST NOT** be hardcoded in code or stored in version control.
- All secrets **MUST** be provided via secure configuration mechanisms.

10.2 **Authentication and Authorization**

- All entry points that mutate data or expose non-public information **MUST**:
  - Require authentication.
  - Apply role- or permission-based authorization checks at the boundary layer.
- Silent privilege escalation or implicit role upgrades are **PROHIBITED**.

10.3 **Sensitive Data Handling**

- Sensitive fields (passwords, tokens, secrets, PII beyond what is necessary) **MUST NOT**:
  - Be logged.
  - Be returned in API responses or UI views without explicit requirement and masking.
- Passwords **MUST** be stored only as secure hashes using modern algorithms; no plaintext or reversible encryption.

10.4 **Code and Query Safety**

- Raw query or string formatting that can lead to injection vulnerabilities is **PROHIBITED**.
- All external inputs **MUST** be validated and sanitized prior to use.

---

## 11. Performance and Scalability Guardrails

11.1 **Queries and Data Access**

- N+1 query patterns in hot paths are **PROHIBITED**.
- All list or search endpoints **MUST**:
  - Implement pagination or explicit bounds.
  - Avoid unbounded scans over large datasets.

11.2 **Indexes**

- Queries introduced in hot paths **MUST** be backed by appropriate indexes.
- Introducing a query that scans large tables without an index on filter conditions is **PROHIBITED** without documented justification and monitoring.

11.3 **Blocking Operations**

- Long-running or blocking operations **MUST NOT** execute in synchronous request/response paths when they can be offloaded to asynchronous or background processing.
- External calls (to third-party services, AI models, etc.) **MUST** have:
  - Reasonable timeouts.
  - Clear failure behavior and fallback where appropriate.

---

## 12. CI, Automation, and Failure Conditions

12.1 **Non-Negotiable CI Gates**

A change **MUST NOT** be merged, deployed, or considered successful if any of the following occur:

- Test suite fails or coverage **< 90%** for required modules.
- Linters or formatters fail.
- Schema drift detected between code and database migration history.
- Migrations fail to apply in a clean environment.
- Duplicate or conflicting model or migration files are detected.
- Static analysis or security checks report high-severity issues that are not explicitly waived with justification.

12.2 **Agent Behavior Under Failure**

- Automated agents that encounter any of the failure conditions above **MUST**:
  - Abort implementation or changes.
  - Surface the failure, its cause, and the failing command or check.
  - Refrain from “working around” governance rules by disabling tests, linters, or checks.

---

## 13. Governance Evolution Protocol

13.1 **Change Authority**

- Changes to this document **MUST** be:
  - Proposed via a formal change request (e.g., RFC or PR description).
  - Reviewed and approved by at least:
    - One designated engineering lead, and
    - One designated product or domain owner.

13.2 **Change Requirements**

- Every change to this file **MUST**:
  - Bump a visible version marker in the header (e.g., v2 → v2.1).
  - Include a rationale for the change.
  - Note whether any Product Plan or documentation updates are required.
  - Call out any breaking changes in governance expectations.

13.3 **Synchronization with Product Plan**

- Any governance change that affects:
  - Enum evolution.
  - Data retention or schema behavior.
  - Security posture.
- **MUST** be checked against the Product Plan for consistency and, where necessary, the Product Plan **MUST** be updated accordingly.

13.4 **Agent Re-Read Requirement**

- Whenever this file changes:
  - Coding agents **MUST** treat the updated version as authoritative.
  - Agents **MUST** re-read this document fully before generating or modifying code after a governance update.

---

## 14. Final Principles

- When in doubt, **do less and be explicit**: introduce the minimum necessary surface area with maximum clarity.
- If a required behavior is not covered here, the change **MUST** default to the most conservative, safe, and maintainable option and be followed by a governance or documentation update.
