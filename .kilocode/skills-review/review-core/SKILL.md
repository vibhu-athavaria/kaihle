---
name: review-core
description: >
  Core review skill for Review mode. Use this when reviewing code
  changes locally or in pull requests. It helps you analyse diffs for
  correctness, security, performance, and maintainability while
  providing clear, actionable feedback without modifying code.
---

# Review Core – How to Review Code

## When to use this skill

Use this skill whenever you are in Review mode and the task involves:
- Reviewing local changes before commit or push.
- Reviewing a pull/merge request.
- Giving structured feedback on code quality, safety, and alignment with project rules.

Review mode is **read-only**: it analyses and comments, but does not edit files or run commands.

## Source of truth

Treat these as authoritative, in this order:

1. The current change set:
   - Git diff, staged changes, or PR diff.
2. The relevant task file(s) – what the change is supposed to achieve.
3. `CONSTITUTION.md` – tech stack, repo structure, absolute rules.
4. `AGENTS.md` – governance rules (coding, migrations, security, CI).

If a change appears to violate these, call it out explicitly in the review.

## Core review behaviour

Always:
- Start with a **high-level summary** of what changed and why (as inferred from the diff).
- Separate feedback into:
  - Critical issues (correctness, security, data integrity, multi-tenancy).
  - Important improvements (design, performance, tests, readability).
  - Nice-to-haves (style, minor refactors, documentation).
- Be specific and actionable:
  - Point to files, functions, and lines or blocks.
  - Explain both the problem and a suggested direction for improvement.

Never:
- Assume intent without evidence; if unclear, phrase it as a question.
- Suggest changes that contradict `CONSTITUTION.md` or `AGENTS.md`.
- Attempt to directly modify files or run commands in Review mode.

## What to check during review

When reviewing a change, walk through:

1. **Correctness and behaviour**
   - Does the code do what the task file says it should?
   - Are there obvious logic errors, missing null/edge case handling, or incorrect assumptions?
   - Are error paths handled explicitly and mapped to predictable responses?

2. **Multi-tenancy and security**
   - Are queries on non‑curriculum data correctly scoped by tenant/school where required?
   - Are auth/role checks present at boundaries (routes, handlers)?
   - Are secrets, tokens, or PII kept out of logs and responses?

3. **Architecture and boundaries**
   - Does route code stay thin and delegate to services?
   - Are new responsibilities added to the correct service or module?
   - Are LLM calls going through the correct abstraction layer?

4. **Performance and reliability**
   - Any obvious N+1 queries, unbounded scans, or missing pagination?
   - Long-running work left in request/response path instead of moved to background tasks?
   - Reasonable timeouts and retry behaviour for external calls?

5. **Tests**
   - Do tests cover the main paths introduced by the change?
   - Are there tests for failure cases and edge conditions?
   - Does each acceptance criterion in the task file have at least one corresponding test?

6. **Readability and maintainability**
   - Is the code clear, well-structured, and following existing patterns?
   - Are names meaningful? Are functions/classes the right size?
   - Are comments used appropriately (explaining why, not what)?

## Style of feedback

Structure feedback to be helpful and focused:

- **Tone**
  - Be direct but constructive.
  - Prefer “Consider…” or “This may cause…” with explanation over blunt statements.

- **Structure**
  - Group comments by file and by severity.
  - Use short code excerpts or descriptions to anchor each point.

- **Suggestions**
  - When possible, suggest improved patterns that already exist elsewhere in the codebase.
  - Highlight positive aspects as well (good tests, nice abstractions, clear naming).

## Output format for this skill

When responding in Review mode using this skill, structure your response as:

1. **Summary**
   - 2–4 bullets describing what this change appears to do.

2. **Overall assessment**
   - Short paragraph on whether the change looks ready, needs work, or has major blockers.

3. **Major issues**
   - Numbered list of correctness, security, data integrity, or multi-tenancy problems.

4. **Tests**
   - Observations about test coverage and suggestions for missing tests.

5. **Improvements and suggestions**
   - List of design, performance, and readability improvements.

6. **Minor comments / nitpicks (optional)**
   - Small style or cleanup suggestions that are nice-to-have, not blockers.
