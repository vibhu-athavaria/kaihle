# M4 Brief — Teacher Copilot (Lesson Planning)
**Milestone:** 4 of 6
**Estimated duration:** 2–3 weeks
**Previous milestone:** M3 — Smart Study Plans

> Load this brief alongside CONSTITUTION.md when working on any M4 task.
> Load the specific task file for the task you are implementing.

---

## Goal

Every Monday, each teacher automatically receives an AI-generated weekly lesson plan based on their class's current gap map. The plan groups students by mastery level and suggests differentiated activities. Teachers can view, edit, and mark plans as used.

## Exit Criteria

- Teacher receives lesson plan email every Monday
- Teacher views plan in dashboard, edits it, marks as used
- Regeneration works on demand

---

## What This Milestone Delivers

- Weekly lesson plan Celery beat task (Monday 06:00)
- Lesson plan JSON schema + storage
- Lesson plan API routes (fetch, edit, regenerate, mark status)
- Lesson plan UI in teacher app

---

## Tasks in This Milestone

| Task ID | File | Description |
|---|---|---|
| M4-1-T1 | `M4/M4-1-T1_lesson_plan_celery_task.md` | Celery beat: generate weekly lesson plans |
| M4-1-T2 | `M4/M4-1-T2_lesson_plan_schema_storage.md` | Lesson plan JSON schema + Pydantic model |
| M4-1-T3 | `M4/M4-1-T3_lesson_plan_routes.md` | Lesson plan API endpoints |
| M4-1-T4 | `M4/M4-1-T4_lesson_plan_ui.md` | Teacher lesson plan dashboard UI |

---

## Task Execution Order

```
M4-1-T2 (schema) ← first — defines the data shape everything else depends on
  → M4-1-T1 (Celery task) ← needs schema to store output
  → M4-1-T3 (routes) ← needs schema for response types
    → M4-1-T4 (UI) ← needs routes
```

---

## Definition of Done

- [ ] Weekly lesson plans auto-generated every Monday for all active classes
- [ ] Teacher receives email notification with link
- [ ] Teacher can view, edit (saves to `teacher_edits` column), and mark as used
- [ ] Regeneration works on demand
- [ ] All M4 tests pass

---

## Key Tables Used in This Milestone

`lesson_plans`, `gap_states`, `subtopics`, `curriculum_topics`, `classes`, `class_enrollments`, `users`, `curriculum_chunks`

Full schema: `kaihle_v2_1_schema.sql`

---

## Lesson Plan Generation Logic

The Celery beat task (`generate_weekly_lesson_plans`) does the following for each active class:

1. Load class gap map via `gap_service.get_class_gap_map(class_id)`
2. Identify **top 2 subtopics** with lowest average mastery across the class
3. Cluster students into 3 groups:
   - **Group A:** mastery < 0.4 (foundational support)
   - **Group B:** mastery 0.4–0.7 (developing)
   - **Group C:** mastery > 0.7 (extension)
4. Retrieve RAG context: 3 most relevant `curriculum_chunks` for the 2 focus subtopics (pgvector cosine similarity)
5. Build prompt — see template in `kaihle_product_plan_v2_1.md` Part 4
6. Call LLM: `task="lesson_plan"`, GPT-4.1, **15 second hard timeout**
7. On timeout: retry once → if still fails, log error, do NOT store partial plan, do NOT email teacher
8. On success: store in `lesson_plans`, send notification email via Resend

**Celery beat schedule:** `crontab(hour=6, minute=0, day_of_week=1)` (Monday)

---

## Lesson Plan JSON Structure

```json
{
  "week_start": "2026-03-02",
  "focus_subtopic_ids": ["uuid1", "uuid2"],
  "class_summary": "60% of students struggle with algebraic fractions...",
  "student_groups": {
    "A": { "count": 8, "focus": "Foundational — identifying numerator/denominator" },
    "B": { "count": 12, "focus": "Simplifying basic fractions" },
    "C": { "count": 5, "focus": "Extension — adding unlike fractions" }
  },
  "lesson_structure": {
    "starter_10min": "...",
    "main_activity_30min": {
      "group_A": "...",
      "group_B": "...",
      "group_C": "..."
    },
    "plenary_10min": "...",
    "homework": "..."
  },
  "teacher_notes": "..."
}
```

---

## What M3 Delivered (Available to Use)

- `gap_states` updated by study plan quiz submissions
- `gap_service.get_class_gap_map()` service method exists and is tested
- `subtopics.embedding` and `curriculum_chunks.embedding` in pgvector

## What M5 Expects From M4

- `lesson_plans` table exists and is populated with real data
- `gap_service` methods work correctly (M5 parent narrative also reads gap data)
- Celery beat infrastructure working (M5 adds another beat task)
