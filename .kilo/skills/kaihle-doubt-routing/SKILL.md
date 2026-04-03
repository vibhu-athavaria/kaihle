---
name: kaihle-doubt-routing
description: Use when the coding agent encounters a gap, conflict, or unclear decision in a Kaihle task file. Provides the protocol for routing doubts to the right persona subagent (@kramer, @pixel, @vidhya, @nancy) before escalating to the human. Trigger on any "I'm not sure about..." or "the task file doesn't specify..." situation.
---

# Kaihle Doubt Routing Protocol

## The Core Rule

**Do not guess. Do not "make a reasonable assumption" on anything that affects:**
- A frozen API contract (M0-10 paths, schemas, HTTP methods)
- Design system tokens or role-specific colors
- Curriculum data (subject/grade bindings, assessment model)
- Architecture patterns (service layer, Celery, auth flow)

These are irreversible or very expensive to fix. A wrong guess here costs more time than asking.

## Step 1: Classify Your Doubt

Ask: "What domain does this decision live in?"

| If the doubt is about... | Invoke |
|---|---|
| API design, service layer, database, Celery, tests, architecture, frozen contract conflict | `@kramer` |
| Component layout, Tailwind tokens, colors, UX behaviour, mockup interpretation, accessibility | `@pixel` |
| Curriculum scope (subject/grade), assessment question accuracy, learning objectives, questionnaire | `@vidhya` |
| Button labels, empty state copy, onboarding text, error messages, user-facing strings | `@nancy` |

**Multi-domain doubts** (e.g., "I need to know the right API endpoint shape AND how the component should display the data"): split into two invocations. Ask @kramer for the API shape first, then @pixel for the display.

## Step 2: How to Invoke a Persona

In the KiloCode chat, type:

```
@kramer [specific question with context]
```

**Good invocation — gives context, asks for a specific decision:**
> @kramer Task M1-4-T1 says to call `check_and_update_onboarding_complete` after attempt submit. The task file shows this in the route handler. But Rule 1 (service layer owns all logic) says routes should be thin. Should this call live in `attempt_service.submit_attempt()` instead, or is a route-level call acceptable here because it's triggering a side effect rather than business logic?

**Bad invocation — too vague, no context:**
> @kramer Where should I put this function?

## Step 3: After Getting the Persona Response

1. Implement based on the decision
2. Add a comment in the code referencing the decision:
   ```python
   # Decision: @kramer 2026-03-15 — side-effect call here is acceptable
   # because it's a post-completion notification, not business logic
   ```
3. If the decision changes what the task file specified, note the delta in your PR description

## Step 4: If the Persona Response Doesn't Resolve It

Some doubts require human judgment because:
- They involve a product decision (not just an engineering/design decision)
- They conflict with another already-implemented task
- They require a new ADR

Write a doubt file and stop:

```
docs/doubts/{task_id}_doubt_{YYYY-MM-DD}.md
```

```markdown
---
task: M{N}-{E}-T{N}
filed_by: coding-agent
date: YYYY-MM-DD
status: needs-human-resolution
persona_consulted: kramer
---

## Question
[One sentence: what decision is needed?]

## Context
[What the task says. What the conflict is. Which files are involved.]

## Persona Decision
[Exactly what @kramer / @pixel / @vidhya / @nancy said]

## Why Still Unresolved
[What the persona couldn't resolve and why human judgment is needed]

## Options
1. [Option A — consequence]
2. [Option B — consequence]

## Agent Recommendation
[What you would do. You must give one.]
```

Then **stop implementation** on the blocking item and notify the user.
You can continue implementing other non-blocking parts of the task.

---

## Known Kaihle Doubt Patterns and Their Answers

These are frequent doubts that have already been resolved. Check here first before invoking a persona.

### "Should I use asyncio.run() or new_event_loop() in Celery?"
**Resolved:** Always `new_event_loop()`. `asyncio.run()` raises "event loop is already running" inside Celery workers. See M0-8-T1 for the fix pattern.

### "The task says to return 501 for this write endpoint. Is that right?"
**Resolved:** Yes — stubs for write endpoints that queue significant async work return 501. Read endpoints return 200 with empty data. This is the M0-10 stub pattern.

### "Which Tailwind class for a gold button?"
**Resolved:** `bg-brand-gold text-white hover:bg-brand-gold-dark rounded-full` — Teacher app only. Kaihle Admin and School Admin use `bg-brand-primary` (green). Student app uses `bg-brand-primary`.

### "What's the mastery score boundary — is 0.7 Strong or Developing?"
**Resolved:** `score > 0.7` = Strong. Exactly 0.7 = Developing. See `getMasteryStyle()` in `packages/types/src/mastery.ts`.

### "Does SCI exist in IGCSE?"
**Resolved:** No. SCI (Integrated Science) is Cambridge Lower Secondary ONLY. IGCSE has BIO, CHEM, PHY separately.

### "The task wants me to put School Admin pages in apps/teacher — should I?"
**Resolved:** No. This was the v1.0 mistake corrected by ADR-001. School Admin pages go in `apps/school-admin/`. Invoke @pixel to confirm the exact route path.

### "Where does mastery color logic go — can I inline it?"
**Resolved:** Never. Always `getMasteryStyle()` from `@kaihle/types`. This is enforced so that threshold changes only require one file update.
