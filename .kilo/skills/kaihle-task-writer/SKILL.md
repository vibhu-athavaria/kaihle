---
name: kaihle-task-writer
description: Use when a Kaihle task file needs to be created, fixed, or retrofitted. Specifically: adding missing named test specifications, fixing incomplete acceptance criteria, splitting executor-mixed tasks, or patching tasks where the coding agent found a gap during implementation. Reference gold standard: docs/tasks/M1/M1-4-T1_gap_state_calculation_service.md
---

# Kaihle Task File Writer / Fixer

## When to Use This Skill

1. **Retrofitting** — A task file has checkbox acceptance criteria but no named test functions (pre-Rule 20 tasks). Must be upgraded before handing to coding agent.
2. **Gap patching** — Coding agent filed a doubt that revealed a missing decision. That decision must be added to the task file.
3. **New task** — A gap was identified that has no task file at all.
4. **Executor mismatch** — A task file has both human-action steps and coding-agent steps mixed together. Must be split.

---

## Required Task File Header

```markdown
# Task: {Task ID} — {Short Title}

**Milestone:** M{N} — {Milestone Name}
**Epic:** M{N}-{E}
**Executor:** Coding agent
**Status:** Draft | Ready | In Progress | Done
**Depends on:** {comma-separated task IDs or "none"}
**Blocks:** {comma-separated task IDs or "none"}
**Estimated effort:** {XS | S | M | L | XL}
```

`Executor: Coding agent` = zero human-action steps inside the task.
`Executor: Human ({name})` = human-readable instructions, no code generation.
Never mix both in one task file. If you need both, split into two tasks.

---

## Required Sections (in order)

### 1. Context
Why does this task exist? What problem does it solve? What milestone delivers it?
What came before it that this builds on?

### 2. Pre-Implementation Checklist
```
Before writing any code, verify:
- [ ] Check docs/API_ENDPOINT_TASK_MAP.md — confirm endpoint status (stub exists? already built?)
- [ ] Check if Files to Create / Modify already exist with conflicting content
- [ ] Pixel has reviewed this spec (frontend tasks only)
- [ ] All decisions below are final — no decision-making inside task files
```

### 3. Frozen Contracts (if replacing stubs)
```
This task replaces stubs created in M0-10-T{N}.
NEVER change: path, HTTP method, request schema, response schema.
ONLY replace: function bodies marked `# STUB — M0-10-T{N}`
```

### 4. Implementation Notes
Explicit instructions. Gotchas. Decisions already made.
Do not leave decisions open — a coding agent must be able to implement this without
making any design choices.

### 5. Files to Create / Modify
```
backend/app/services/{service_name}.py          [CREATE]
backend/app/api/v1/routes/{route_name}.py       [MODIFY — stub replacement]
backend/app/tests/unit/test_{service_name}.py   [CREATE]
backend/app/tests/integration/test_{route}.py   [CREATE]
```

### 6. Test Specifications (MANDATORY — Rule 20)

This is the most commonly missing section in pre-generated tasks.

```markdown
### Unit Tests
File: `backend/app/tests/unit/test_{service_name}.py`

#### `test_{what}_when_{condition}_then_{expected}`
- **Arrange:** {what mocks/fixtures are set up — be specific}
  - Mock `{module}.{function}` to return `{value}`
  - Create fixture: `{fixture_name} = {factory_call}()`
- **Act:** `result = await service.{method}({args})`
- **Assert:**
  - `assert result.{field} == {expected_value}`
  - `assert mock_{dep}.called_once_with({args})`

#### `test_{what}_when_{condition}_then_{expected}`
...

### Integration Tests
File: `backend/app/tests/integration/test_{route_file}.py`

#### `test_{endpoint}_when_{condition}_then_{http_status}`
- **Arrange:**
  - DB state: `{describe the required database rows}`
  - Auth: `headers = auth_headers(role="{ROLE}", school_id={school_id})`
- **Act:** `response = await client.{method}("{path}", json={body}, headers=headers)`
- **Assert:**
  - `assert response.status_code == {code}`
  - `assert response.json()["{field}"] == {value}`
```

**Minimum test coverage required:**
- Happy path (successful operation)
- Auth/role failure (403 for wrong role, 401 for no token)
- Not found (404 for non-existent resource)
- Business rule violation (409, 400, 422 as appropriate)
- school_id isolation (user from school A cannot access school B's data)

### 7. Acceptance Criteria
Named test functions ARE the acceptance criteria. A checkbox like "Users can log in" is not sufficient — it must be backed by a named test function that verifies it.

---

## Retrofitting Pre-Generated Tasks (Most Common Use)

When a task file has checkboxes but no named tests:

1. Read the task's acceptance criteria checkboxes
2. For each checkbox, write the named test function that would verify it
3. Add the test specs section following the format above
4. Cross-reference `docs/API_ENDPOINT_TASK_MAP.md` to verify endpoint status
5. Verify the task doesn't reference endpoints that don't exist yet
6. Add the "Pre-Implementation Checklist" section if missing

**Do not change** the task's decision content or implementation notes when retrofitting —
only add the missing test specs and structural sections.
