---
name: architect-core
description: >
  Core architectural reasoning skill. Use this when planning or changing
  system architecture, APIs, services, data flows, and high-level test
  plans. It helps you read the project’s source-of-truth docs, design
  concrete APIs and service methods, and define comprehensive unit and
  integration test cases for the task at hand.
---

# Architect Core – How to Think and Work

## When to use this skill

Use this skill whenever you are in Architect mode and the task involves:
- Designing or updating architecture, service boundaries, or data flows.
- Designing new APIs or changing existing endpoints.
- Introducing or changing schemas, migrations, or cross-cutting concerns
  (auth, multi-tenancy, LLM routing, CI/CD).
- Defining the test strategy (unit + integration) for a feature or task.

## Source of truth

Treat these as authoritative, in this order:

1. `CONSTITUTION.md` – project definition, locked tech stack, repo structure, absolute rules.
2. `AGENTS.md` – engineering governance, MUST/MUST NOT rules.
3. Milestone briefs (`docs/milestones/MN_brief.md`) – scope and dependencies.
4. Task files (`docs/tasks/MN/MN-E-TN*.md`) – concrete requirements and acceptance criteria.

If anything else conflicts with these, follow the list above and explicitly call out the conflict.

## Core behavior

Always:
- Restate the problem and constraints in your own words before proposing a design.
- Prefer extending existing services, patterns, and tables over inventing new ones.
- Make multi-tenancy, auth, and LLM provider routing explicit in your designs.
- Propose concrete:
  - FastAPI routes (paths, methods, auth/roles, request/response schemas).
  - Service method signatures (names, parameters, return types).
- Design and write **comprehensive test cases** for the task in hand:
  - Unit tests for each service method, pure function, and important branch.
  - Integration tests that cover end‑to‑end flows (API ↔ DB ↔ background jobs).

Never:
- Change auth, onboarding gates, billing, or enum semantics implicitly.
- Ignore or weaken rules from `AGENTS.md` or `CONSTITUTION.md` to “simplify” a design.
- Add new tables, enums, or global patterns without checking reference docs first.

## Design and test checklist

When designing or modifying a feature, walk through:

1. **Domain fit**
   - Which existing domain/service does this logically belong to?
   - Do we really need a new service, or can we extend an existing one?

2. **Data and schema**
   - Which tables/enums are read or written?
   - Are schema changes required? If yes, define the migration at a high level and
     its invariants (constraints, indexes, nullability, defaults).
   - How do these changes affect transactions, idempotency, and background jobs?

3. **APIs and boundaries**
   - For each endpoint:
     - Path and HTTP method.
     - Required auth and allowed roles.
     - Request body/query params and response schema.
   - For each service method:
     - Function name, parameters, return type (conceptually).
   - How `school_id` filtering / tenant isolation and role checks are enforced.

4. **LLM usage (if relevant)**
   - Which logical “task type” is this (e.g., question generation, scoring, study plan)?
   - Which provider/model and latency budget apply?
   - What prompt inputs and context are required?

5. **Tests and observability**
   - Unit tests:
     - Happy path, edge cases, validation failures, and error handling.
   - Integration tests:
     - Endpoints hitting real persistence and any Celery/async flows needed.
     - Multi-step flows that must succeed or fail atomically.
   - Logging and metrics:
     - Which events and state transitions must be logged.
     - Any metrics/counters that should be updated.

## Output format for this skill

When using this skill to answer an Architect-mode request, structure your response as:

1. **Summary**
   - 2–4 bullets describing what you are changing or adding.

2. **API and service design**
   - List of endpoints with paths, methods, auth/roles, and schemas.
   - List of service methods with signatures and responsibilities.

3. **Data impacts**
   - Tables/enums touched, required migrations, and key invariants.

4. **Test plan**
   - Bullet list of unit tests.
   - Bullet list of integration tests.

5. **Governance alignment**
   - Explicitly mention any important rules from `AGENTS.md` / `CONSTITUTION.md`
     that you are relying on (e.g., school_id isolation, LLM abstraction, CI gates).

6. **Risks and open questions**
   - Items that require human confirmation before implementation.
