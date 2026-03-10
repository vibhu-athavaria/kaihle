---
name: debug-core
description: >
  Core debugging skill for Debug mode. Use this when tracking down bugs,
  failing tests, or runtime errors. It helps you gather context, form
  hypotheses, design diagnostics, and propose precise, safe fixes
  aligned with project governance.
---

# Debug Core – How to Diagnose and Fix

## When to use this skill

Use this skill whenever you are in Debug mode and the task involves:
- A failing test, runtime error, or unexpected behaviour.
- An unclear or intermittent bug that needs investigation.
- Verifying that a recent change did not introduce regressions.

Debug mode prioritises **understanding and diagnosis** before implementation.

## Source of truth

Treat these as authoritative, in this order:

1. The current error signal:
   - Failing test output.
   - Stack trace, logs, or error message.
   - User-reported bug description and reproduction steps (if provided).
2. The current task file (`docs/tasks/MN/MN-E-TN*.md`) – what should be true.
3. `CONSTITUTION.md` – tech stack, repo structure, absolute rules.
4. `AGENTS.md` – engineering governance (MUST / MUST NOT).

If anything conflicts, follow this order and explicitly call out the conflict.

## Core debugging behaviour

Always:
- Start by **restating the problem**:
  - What is happening now?
  - What was expected instead?
- Gather minimal but sufficient context:
  - Identify and read only the most relevant files first.
  - Inspect failing tests, stack traces, and logs before changing code.
- Form explicit **hypotheses** about root cause and list them.
- Design a **diagnostic plan**:
  - Which tests to run or add.
  - Which logs or temporary instrumentation to add.
  - Which inputs or edge cases to probe.
- Only propose changes **after**:
  - You have a plausible root cause.
  - Diagnostics support that hypothesis.

Never:
- Start by rewriting large parts of the codebase.
- Make speculative changes without stating the hypothesis they test.
- Ignore project rules for logging, transactions, multi-tenancy, or LLM usage.

## Debugging checklist

Work through these steps systematically:

1. **Reproduction**
   - Can the issue be reproduced reliably?
   - What exact command or user action triggers it?
   - Under what environment or preconditions?

2. **Signal inspection**
   - Read the full stack trace or failing assertion, not just the top line.
   - Note which module, function, or component is implicated.
   - Check logs around the failure (request ID, correlation ID, user/school context).

3. **Narrow the scope**
   - Identify the minimal set of files and functions likely involved.
   - Distinguish between:
     - Symptom code (where it crashes).
     - Cause code (where wrong data or state comes from).

4. **Hypotheses and diagnostics**
   - Write 1–3 concrete hypotheses about the root cause.
   - For each hypothesis, define:
     - What observation would confirm or refute it.
     - Which test, log, or local run to use.

5. **Proposed fix (design, not implementation)**
   - Describe how you would fix the confirmed root cause:
     - What code should change, at a high level.
     - Any data migrations or backfills required.
     - Any implications for transactions, idempotency, or background jobs.
   - Ensure the design respects:
     - Multi-tenancy (school_id filters, role checks).
     - LLM abstraction (no direct provider calls).
     - Logging and error-handling standards.

6. **Regression and edge cases**
   - Identify similar paths that might also be affected.
   - Define tests that prevent this bug from reappearing.

## Tests and logging

As a debugger, you design the verification strategy:

- **Tests**
  - Identify or outline tests that:
    - Reproduce the current bug.
    - Verify the fix on the original scenario.
    - Cover important edge cases revealed during debugging.
- **Logging**
  - Suggest where to add structured logs (and what fields) to:
    - Observe critical state transitions.
    - Track correlation IDs across services.
  - Never log secrets or sensitive PII.

Implementation of the fix and tests will typically be carried out in Code mode.

## Output format for this skill

When using this skill to handle a Debug-mode request, structure your response as:

1. **Problem summary**
   - What is failing, under what conditions, and what was expected.

2. **Evidence and context**
   - Key lines from stack traces, failing tests, or logs.
   - Files and functions that appear most relevant.

3. **Hypotheses**
   - 1–3 numbered hypotheses about the root cause.

4. **Diagnostic plan**
   - Steps to confirm or refute each hypothesis (tests to run/add, logs to inspect/add).

5. **Proposed fix (design)**
   - High-level description of the change(s) to be made, including any data or transactional considerations.

6. **Verification plan**
   - Tests and checks that must pass before considering the bug resolved.
