# M5 Brief — Parent Portal
**Milestone:** 5 of 6
**Estimated duration:** 2 weeks
**Previous milestone:** M4 — Teacher Copilot
**Constitution version:** 2.0
**Last updated:** April 2026 — 4-band to 3-band mapping clarified; mastery formula noted

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

## Critical: 4-Band → 3-Band Mapping (April 2026)

The internal mastery system uses **4 bands** (Mastered / Approaching / Developing /
Critical Gap). The parent portal uses a **simplified 3-band display** for non-educator
audiences. The mapping is:

| Internal band | Score range | Parent label | Parent colour |
|---|---|---|---|
| Mastered | ≥ 0.85 | **Strong** | green |
| Approaching | 0.70–0.84 | **Developing** | amber |
| Developing | 0.40–0.69 | **Developing** | amber |
| Critical Gap | < 0.40 | **Needs Work** | red |

**Key design decision:** Approaching maps DOWN to "Developing" (not up to "Strong").
A student at 0.75 is close to mastery but not there yet. Telling a parent their child
is "Strong" when they have a 0.75 would be misleading. "Developing" is accurate and
encouraging without overstating progress.

**Where this mapping lives:** Exclusively in `backend/app/services/parent_service.py`
in a `_mastery_to_parent_label(score: float | None) -> str` function. It does NOT
live in `getMasteryStyle()`, the design system, or any frontend code.

```python
def _mastery_to_parent_label(score: float | None) -> str:
    """
    Maps internal 4-band mastery score to simplified 3-band parent label.
    Called only from ParentService — never from any other service or frontend.
    """
    if score is None:
        return "Not yet assessed"
    if score >= 0.85:
        return "Strong"
    if score >= 0.40:   # covers both Approaching (0.70–0.84) and Developing (0.40–0.69)
        return "Developing"
    return "Needs Work"
```

The `ParentGapMap` Pydantic schema has no `mastery_score` field — only the string
label. No numeric score ever reaches a parent endpoint. This is enforced at three
levels: schema (no field), service (converts before schema population), test (assert
no mastery_score key anywhere in response body).

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

Uses `new_event_loop()` Celery async pattern — not `asyncio.run()`.

**Parent portal API — stub replacement**

M0-10-T6 created `routes/parent.py` with stubs for all four parent endpoints. This
milestone replaces every stub body with real service and data calls. The frozen
contracts from M0-10 must not be changed. The critical constraint is that `mastery_score`
is never returned from any parent endpoint — the `ParentGapMap` schema has no such
field by design, and the conversion from raw `gap_states` to plain-language labels
happens entirely in `parent_service.py` using `_mastery_to_parent_label()` before the
schema is populated.

**Parent portal UI**

Built entirely in `apps/parent`. The dashboard shows the latest narrative card and
a quick overview of each subject as a traffic-light. The progress page shows the
full simplified gap map with expandable topic rows and the weekly report history as
an accordion. Mobile-first — parents primarily use phones.

The traffic-light colours map parent labels to design system tokens:
- "Strong" → `bg-brand-green-light text-brand-green`
- "Developing" → `bg-brand-amber-light text-brand-amber`
- "Needs Work" → `bg-brand-red-light text-brand-red`
- "Not yet assessed" → `bg-gray-50 text-brand-muted`

Do NOT use `getMasteryStyle()` in the parent app. That function uses internal 4-band
labels. The parent app always derives display styles from the string label returned
by the API using a local `parentLabelStyle()` helper.

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

---

## Critical: Stub Replacement Protocol

M5-1-T2 replaces stubs in `backend/app/api/v1/routes/parent.py` (created by
M0-10-T6). Open the file, find every function marked `# STUB — M0-10-T6`, and replace
only the function body. Add a `ParentService` with a `verify_parent_child_link()`
method that raises HTTP 403 if the `parent_student` table has no row linking the
requesting parent to the given `student_id`. Every parent endpoint must call this
check before returning any data.

Add `_mastery_to_parent_label()` to `ParentService`. This function is the sole
location where 4-band → 3-band mapping occurs. It is called before populating
any schema field. It is tested independently.

---

## The No-Scores Constraint

This constraint is first-class. Raw percentages without context cause anxiety and
misinterpretation in non-educator audiences. Plain-language labels combined with a
brief narrative give parents actionable information.

Enforced at three levels:
1. `ParentGapMap` Pydantic schema has no `mastery_score` field
2. `_mastery_to_parent_label()` converts all scores before the schema is populated
3. Unit test: `test_get_child_gap_map_response_contains_no_mastery_score_anywhere`
   asserts the response body contains no `mastery_score` key

---

## LiteLLM Usage in This Milestone

M5-1-T1 calls `app.ai.providers.router.complete()` with `task="gap_classification"`
(Gemini Flash). The 150-word limit is enforced inside the Jinja2 prompt template,
not as a `max_tokens` parameter. Uses `new_event_loop()` Celery async pattern.

---

## Frontend App Target

All parent portal UI builds in `apps/parent`. The `useMyChildren`, `useChildReports`,
and `useChildGapMap` hooks created in M0-10-T12 are the data layer. No parent UI
code goes into any other app.

The parent app uses Lora as the primary display font (unique to parents — see
DESIGN_SYSTEM.md §5.5). Do not use Fraunces or Inter in the parent app.

Do NOT import `getMasteryStyle` from `@kaihle/types` in the parent app. Use a
local `parentLabelStyle(label: string)` helper instead that maps the 3 parent
string labels to Tailwind classes.

---

## Definition of Done

- Weekly parent reports auto-generated every Sunday
- Parents receive email notification with link to report
- Parent can view simplified gap map — no numeric scores anywhere in the response
- Parent with two or more children can switch between them via a selector
- Mobile layout correct at 375px width
- Traffic-light labels correctly reflect the 4→3 band mapping (Approaching → Developing)
- All M5 tests pass

---

## Key Tables Used in This Milestone

`parent_report_snapshots`, `parent_student`, `gap_states`, `subtopics`,
`curriculum_topics`, `topics`, `users`, `student_profiles`

Full schema: `kaihle_v2_1_schema.sql`

---

## What M4 Delivered (Available to Use)

Lesson plans are being generated weekly. Celery beat is operational. Gap states are
being updated regularly. `student_learning_profiles` is fully populated for onboarded
students. Mastery scores use the 4-band weighted formula.

---

## What M6 Expects From M5

`parent_report_snapshots` table has real data so the analytics service in M6 can
count `parent_reports_sent`. The parent portal is fully functional in staging.
Celery beat is confirmed running both lesson plan generation (Monday) and parent
narrative generation (Sunday).

---

*M5 Brief v2.0 · April 2026*
*Key changes from v1.0: 4-band → 3-band parent mapping documented with explicit*
*implementation location (`_mastery_to_parent_label` in ParentService); Approaching*
*band confirmed to map to "Developing" not "Strong"; `getMasteryStyle()` explicitly*
*excluded from parent app; `new_event_loop()` async pattern noted.*
