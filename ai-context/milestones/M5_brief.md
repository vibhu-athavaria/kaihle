# M5 Brief — Parent Portal
**Milestone:** 5 of 6
**Estimated duration:** 2 weeks
**Previous milestone:** M4 — Teacher Copilot

> Load this brief alongside CONSTITUTION.md when working on any M5 task.
> Load the specific task file for the task you are implementing.

---

## Goal

Parents receive weekly AI-generated plain-language progress narratives for their child and can view a simplified gap map. No jargon, no numbers — just clear traffic-light status and friendly summaries.

## Exit Criteria

- Parent logs in, sees their child's latest weekly narrative
- Parent can view simplified gap map (Strong / Developing / Needs Work labels, no scores)
- Parent with multiple children can switch between them

---

## What This Milestone Delivers

- Weekly parent narrative Celery beat task (Sunday 18:00)
- Parent portal API routes
- Parent portal UI (dashboard + child progress view)

---

## Tasks in This Milestone

| Task ID | File | Description |
|---|---|---|
| M5-1-T1 | `M5/M5-1-T1_parent_narrative_task.md` | Celery beat: generate weekly parent narratives |
| M5-1-T2 | `M5/M5-1-T2_parent_portal_api.md` | Parent portal API endpoints |
| M5-1-T3 | `M5/M5-1-T3_parent_portal_ui.md` | Parent portal UI (dashboard + progress view) |

---

## Task Execution Order

```
M5-1-T1 (Celery narrative task) ← can start immediately
M5-1-T2 (API routes) ← parallel with T1
  → M5-1-T3 (UI) ← needs routes
```

---

## Definition of Done

- [ ] Weekly parent reports auto-generated every Sunday 18:00
- [ ] Parents receive email with link to full report
- [ ] Parent can view simplified gap map (plain language only — no numeric scores)
- [ ] Parent with 2+ children can switch between them
- [ ] All M5 tests pass

---

## Key Tables Used in This Milestone

`parent_report_snapshots`, `parent_student`, `gap_states`, `subtopics`, `curriculum_topics`, `topics`, `users`, `student_profiles`

Full schema: `kaihle_v2_1_schema.sql`

---

## Parent Narrative Generation Logic

Celery beat task (`generate_parent_narratives`) runs every Sunday 18:00:

1. For each student with at least one `gap_state` updated in the last 7 days:
2. Load current `StudentGapMap` via `gap_service.get_student_gap_map(student_id)`
3. Load last week's `parent_report_snapshots` row (if exists) to compute delta
4. Calculate week-over-week change per subtopic — identify:
   - Top 2 **improvements** (largest positive mastery delta)
   - Top 2 **areas still needing work** (lowest current mastery)
5. Build prompt — see template in `kaihle_product_plan_v2_1.md` Part 4
6. Call LLM: Gemini Flash, **150-word hard limit enforced in prompt**
7. Store in `parent_report_snapshots` (`UNIQUE(student_id, week_start)` — upsert)
8. Send email to all parents linked via `parent_student` table (Resend)
9. If student has no linked parents → skip silently, no error

**Celery beat schedule:** `crontab(hour=18, minute=0, day_of_week=0)` (Sunday)

---

## Simplified Gap Map Rules (Parent-Facing)

The parent gap map must NEVER show:
- Numeric mastery scores (e.g. 0.62)
- Percentage scores
- Raw attempt counts

It MUST show:
- Traffic light colour per topic (Red / Amber / Green using same thresholds as §10 of CONSTITUTION)
- Plain-language label: "Strong", "Developing", "Needs Work"
- Topic name only — no subtopic breakdown for parents

---

## What M4 Delivered (Available to Use)

- `gap_service.get_student_gap_map()` exists and tested
- Celery beat infrastructure operational (just add new task to beat schedule)
- Resend email integration working (used by M4 for teacher notifications)

## What M6 Expects From M5

- `parent_report_snapshots` table populated with real narratives
- Parent API routes operational (M6 analytics references parent report counts)
- Email delivery tested end-to-end
