# M5 Brief — Parent Portal
**Milestone:** 5 of 6
**Estimated duration:** 2 weeks
**Previous milestone:** M4 — Teacher Copilot
**Constitution version:** 2.0

> Load this brief alongside CONSTITUTION.md when working on any M5 task.
> Load the specific task file for the task you are implementing.

---

## Goal

Parents receive a weekly plain-language narrative about their child's progress and
can view a simplified gap map. No jargon, no raw scores — just friendly traffic-light
labels and clear summaries that a non-educator parent can act on.

---

## Exit Criteria

- Parent logs in, sees their child's latest weekly narrative
- Parent can view simplified gap map (Strong / Developing / Needs Work — no numeric scores)
- Parent with multiple children can switch between them
- Weekly narratives auto-generated every Sunday at 18:00

---

## What This Milestone Delivers

**Narrative generation Celery beat task**

A `generate_parent_narratives()` function registered as a Celery beat task running
every Sunday at 18:00. For each student with at least one `gap_state` updated in the
last seven days, it loads the student gap map, calculates week-over-week mastery
delta by comparing to the previous `parent_report_snapshots` row, identifies the top
two improvements and the top two areas still needing work, builds a Jinja2 prompt,
and calls LiteLLM with `task="gap_classification"` (Gemini Flash, 150-word hard limit
enforced in the prompt). The result is stored in `parent_report_snapshots` as an
upsert on `UNIQUE(student_id, week_start)` and emailed to all parents linked via
the `parent_student` table.

**Parent portal API — stub replacement**

M0-10-T6 created `routes/parent.py` with stubs for all four parent endpoints. This
milestone replaces every stub body with real service and data calls. The frozen
contracts from M0-10 must not be changed. The critical constraint is that `mastery_score`
is never returned from any parent endpoint — the `ParentGapMap` schema has no such
field by design, and the conversion from raw `gap_states` to plain-language labels
happens entirely in the service layer before the schema is populated.

**Parent portal UI**

Built entirely in `apps/parent`. The dashboard shows the latest narrative card and
a quick overview of each subject as a traffic-light. The progress page shows the
full simplified gap map with expandable topic rows and the weekly report history as
an accordion. The UI is mobile-first because parents primarily use phones.

---

## Tasks in This Milestone

| Task ID | File | Description |
|---|---|---|
| M5-1-T1 | `M5/M5-1-T1_parent_narrative_task.md` | Celery beat: weekly parent narratives |
| M5-1-T2 | `M5/M5-1-T2_parent_portal_api.md` | Replace parent portal stubs with real logic |
| M5-1-T3 | `M5/M5-1-T3_parent_portal_ui.md` | Parent portal UI (apps/parent) |

---

## Task Execution Order

```
M5-1-T1 (Celery narrative task) ← can start immediately
M5-1-T2 (API routes)            ← parallel with T1, replace stubs
  → M5-1-T3 (UI)               ← apps/parent, needs real routes
```

T1 and T2 have no dependency on each other and can be worked in parallel.

---

## Critical: Stub Replacement Protocol

M5-1-T2 replaces stubs in `backend/app/api/v1/routes/parent.py` (created by
M0-10-T6). Open the file, find every function marked `# STUB — M0-10-T6`, and replace
only the function body. Add a `ParentService` with a `verify_parent_child_link()`
method that raises HTTP 403 if the `parent_student` table has no row linking the
requesting parent to the given `student_id`. Every parent endpoint must call this
check before returning any data. The frozen paths, auth, and schemas must not change.

---

## The No-Scores Constraint

This constraint is first-class and worth understanding deeply. The reason parents
never see numeric mastery scores is not just a UI decision — it is an educational
design principle. Raw percentages without context (e.g. "your child scored 0.42 on
algebraic fractions") cause anxiety and misinterpretation. A teacher who knows that
0.42 means "developing but has foundational understanding" reads this very differently
than a parent who sees it as a failing mark. Plain-language labels ("Developing")
combined with a brief narrative ("Emma is building confidence with fractions and
will be working on percentages next week") give parents actionable information without
the noise.

This constraint is enforced at three levels. First, the `ParentGapMap` Pydantic schema
in `schemas/parent.py` has no `mastery_score` field — a developer cannot accidentally
include a score because the schema doesn't allow it. Second, the `parent_service.py`
converts raw gap state scores to `TopicStatus` objects using `mastery_to_status()`
before the schema is populated. Third, the unit test for the parent gap map endpoint
asserts that the response body contains no `mastery_score` key anywhere.

---

## LiteLLM Usage in This Milestone

M5-1-T1 calls `app.ai.providers.router.complete()` with `task="gap_classification"`
(Gemini Flash). The 150-word limit is enforced inside the Jinja2 prompt template,
not as a `max_tokens` parameter — the model is instructed to stay within the limit.

---

## Frontend App Target

All parent portal UI builds in `apps/parent`. The `useMyChildren`, `useChildReports`,
and `useChildGapMap` hooks created in M0-10-T12 are the data layer. No parent UI
code goes into any other app.

---

## Definition of Done

- Weekly parent reports auto-generated every Sunday
- Parents receive email notification with link to report
- Parent can view simplified gap map — no numeric scores anywhere in the response
- Parent with two or more children can switch between them via a selector
- Mobile layout correct at 375px width
- All M5 tests pass

---

## Key Tables Used in This Milestone

`parent_report_snapshots`, `parent_student`, `gap_states`, `subtopics`,
`curriculum_topics`, `topics`, `users`, `student_profiles`

Full schema: `kaihle_v2_1_schema.sql`

---

## What M4 Delivered (Available to Use)

Lesson plans are being generated weekly. Celery beat is operational. Gap states are
being updated regularly from both Tier 1, Tier 2, and study plan quiz submissions.
The `student_learning_profiles` table is fully populated for onboarded students.

---

## What M6 Expects From M5

`parent_report_snapshots` table has real data so the analytics service in M6 can
count `parent_reports_sent`. The parent portal is fully functional in staging. Celery
beat is confirmed running both lesson plan generation (Monday) and parent narrative
generation (Sunday).
