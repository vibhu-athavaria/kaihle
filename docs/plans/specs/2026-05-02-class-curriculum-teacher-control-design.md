# Class Curriculum & Teacher Control — Design Spec
**Date:** 2026-05-02
**Status:** Approved
**Mockups:** `docs/design/specs/mockups/2026-05-02-class-curriculum-teacher-control/`

---

## 1. Problem Statement

Currently, school admins create classes without enrolling students in the same flow, and teachers have no control over which topics their class covers or in what order. The Tier 1 diagnostic is auto-generated from the full curriculum, with no teacher input. Students are hard-gated from all class content until they complete the diagnostic, and lesson plans are planned as a weekly auto-generation job the teacher cannot influence.

This spec redesigns these four areas to give teachers meaningful control while keeping the system simple for school admins.

---

## 2. Scope

| Area | Change |
|---|---|
| Class creation dialog | Grade-first flow with inline student enrollment |
| Teacher setup wizard | Topic ordering + Tier 1 diagnostic builder |
| Student diagnostic gate | Soft gate — gap map pending state, content unlocked |
| Lesson plan generation | On-demand by subtopic, replaces weekly auto-gen |

---

## 3. Class Creation Dialog (School Admin)

**Approved design:** Option B — single dialog with inline student list.

**Mockup:** `mockups/2026-05-02-class-curriculum-teacher-control/class-creation-dialog.html`

### Flow

1. School admin opens "Create Class" dialog
2. Fills in: Class Name, Grade, Curriculum, Subject, Teacher, Academic Year
3. Selecting **Grade** dynamically loads the student checklist below the form fields via `GET /schools/{school_id}/students?grade_id={id}`
4. Students already enrolled in another class for the same subject/grade show a **"In another class"** badge and are disabled (cannot be selected)
5. Admin checks students to enroll, clicks **Create Class**
6. Backend creates the class and enrollments in a single transaction

### API Changes

- `POST /schools/{school_id}/classes` request body gains an optional `student_ids: list[UUID]` field
- If provided, enrollments are created atomically in the same transaction as the class
- New endpoint: `GET /schools/{school_id}/students?grade_id={id}` (may already exist — verify before implementing)

---

## 4. Teacher Setup Wizard

**Approved design:** Gold banner on class page → two-step setup page (not a modal)

**Mockup:** `mockups/2026-05-02-class-curriculum-teacher-control/teacher-setup-wizard.html`

### Banner (Screen 1)

- Shown on the class Overview tab when setup is incomplete: either `class_topics` has no rows for this class (topics not configured) OR no published Tier 1 diagnostic exists for this class yet
- If the teacher has saved topics but not yet published the diagnostic, the banner links directly to Step 2 (skipping Step 1)
- Gold background (`#fffbeb`), amber border, gold CTA button
- Text: *"This class needs setup before students can begin — Choose your topics and design the Tier 1 diagnostic"*
- Clicking "Set up class →" navigates to `/teacher/classes/{class_id}/setup`
- Tabs (Gap Map, Assessments, Study Plans, Lesson Plans) remain visible but show a placeholder message until setup is complete

### Step 1 — Topics (`/teacher/classes/{class_id}/setup/topics`)

**Purpose:** Teacher defines which curriculum topics are in scope for this class and in what order.

**Behaviour:**
- Loads all `CurriculumTopics` for the class's `(curriculum_id, subject_id, grade_id)` tuple
- Teacher can **add** any curriculum topic to the class (creates a `class_topics` row)
- Teacher can **remove** any topic (deletes the `class_topics` row) — no restriction
- Teacher can **reorder** topics via drag-and-drop (`@dnd-kit/core`) — updates `sequence_order`
- Teacher can **mark a topic as covered** — sets `is_covered = TRUE` on the `class_topics` row
- **Covered topics** are grouped at the top of the list with a green "✓ Covered" badge
- **Upcoming topics** are grouped below, reorderable, with a "Mark covered" button
- Clicking "Next: Design Diagnostic →" advances to Step 2

**Rules:**
- Topics remain editable at any time, even after students enroll and attempt the diagnostic
- No minimum topic count enforced — teacher can have as few as 1

### Step 2 — Diagnostic (`/teacher/classes/{class_id}/setup/diagnostic`)

**Purpose:** Teacher selects which topics to include in the Tier 1 diagnostic. System samples questions per topic automatically.

**Behaviour:**
- Lists the class's topics (from Step 1) grouped into Covered / Upcoming sections
- Covered topics are **pre-checked** (included by default — knowledge refresh rationale)
- Teacher can uncheck any topic to exclude it
- Question count estimate shown: `selected_topic_count × ~10 questions`
- Amber warning banner: *"Once a student submits an attempt, this diagnostic is locked and cannot be edited"*
- Clicking "Publish Diagnostic & Finish Setup" creates the `Assessment` row with `is_system_generated = FALSE`, `status = ACTIVE`, and saves `diagnostic_topic_ids` array

**Lock rule:**
- Once any `StudentAttempt` row exists for this diagnostic with `status != NOT_STARTED`, the diagnostic is locked
- Lock is enforced at the service layer: `DiagnosticLockedError` raised if teacher attempts to edit
- UI shows a locked state badge ("🔒 Locked — students have begun") replacing the edit controls

**Tier 2 diagnostics:**
- Teacher can create Tier 2 assessments at any time via the existing Assessments tab
- No lock rules apply to Tier 2

---

## 5. Student Diagnostic Gate Change

### What is removed

- `require_diagnostic_complete(class_id)` API dependency is removed from study plan and lesson plan routes
- `onboarding_diagnostic_status = COMPLETED` no longer gates any content

### What stays

- Gate 1 (learning profile questionnaire) is unchanged — dashboard still requires it
- `onboarding_diagnostic_status` column is retained — drives UI state only, not access control

### New student experience when diagnostic is pending

| Location | State |
|---|---|
| Class page banner | Amber "Complete your diagnostic" banner (dismissible per session) |
| Gap Map tab | Greyed-out state: *"Complete your diagnostic to see your gap map"* — no mastery scores rendered |
| Study Plans | Fully accessible immediately after enrollment |
| Lesson Plans | Fully accessible immediately after enrollment |

---

## 6. Lesson Plan — On-Demand Generation

### What changes

- The planned weekly Celery auto-generation job is **not implemented** — dropped from scope
- `lesson_plan_tasks.py` placeholder is replaced with an on-demand Celery task
- Teacher triggers generation from the **Lesson Plans tab** of their class

### UI flow

1. Lesson Plans tab shows the class's topics and subtopics (from `class_topics`)
2. Teacher selects 1 or more subtopics and clicks "Generate Lesson Plan"
3. Button shows a pulsing "Generating..." badge (Rule 22) while the Celery task runs
4. On completion, the lesson plan appears in the tab with Edit / Mark as Used / Archive actions

### Caching / deduplication

- If an active (`GENERATED` or `EDITED`) lesson plan already exists for that `(class_id, focus_subtopic_ids)` pair, the service returns it with a "Regenerate" option rather than creating a duplicate
- Deduplication is enforced at the service layer — no DB uniqueness constraint

### Lesson plans are class-specific

Lesson plans are generated using the aggregated learning style distribution of that class's students (visual, auditory, kinesthetic group counts) captured in `gap_summary`. Two different class sections teaching the same subtopic will produce different plans because their student compositions differ. Cache key `(class_id, focus_subtopic_ids)` is correct.

### Schema changes to `lesson_plans`

- Drop `UNIQUE (class_id, week_start)` constraint
- `week_start` becomes nullable — repurposed as the generation date (informational only)

---

## 7. Backend Data Model Changes

### Migration 1 — New `class_topics` table

```sql
CREATE TABLE class_topics (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id           UUID NOT NULL REFERENCES schools(id),
  class_id            UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
  curriculum_topic_id UUID NOT NULL REFERENCES curriculum_topics(id),
  sequence_order      INT NOT NULL,
  is_covered          BOOLEAN NOT NULL DEFAULT FALSE,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ,
  UNIQUE (class_id, curriculum_topic_id)
);
```

### Migration 2 — Modify `assessments` table

```sql
ALTER TABLE assessments
  ADD COLUMN diagnostic_topic_ids UUID[] DEFAULT NULL;
```

Stores the `curriculum_topic_id` values the teacher selected for the Tier 1 diagnostic. NULL for legacy system-generated assessments.

### Migration 3 — Modify `lesson_plans` table

```sql
ALTER TABLE lesson_plans
  DROP CONSTRAINT lp_class_week_unique;

ALTER TABLE lesson_plans
  ALTER COLUMN week_start DROP NOT NULL;
```

### Retired

- `create_class_diagnostic_task` Celery task is retired — no auto-generation of Tier 1 on class creation

---

## 8. API Contract Changes

All new endpoints follow the frozen contract rules (CONSTITUTION Rule 19). Existing endpoint paths/methods are unchanged.

| Method | Path | Role | Purpose |
|---|---|---|---|
| `GET` | `/schools/{school_id}/students?grade_id={id}` | SCHOOL_ADMIN | List students in a grade for enrollment picker — verify if exists before implementing |
| `GET` | `/classes/{class_id}/topics` | TEACHER, SCHOOL_ADMIN | List class_topics for this class |
| `POST` | `/classes/{class_id}/topics` | TEACHER | Add a curriculum_topic to class |
| `PUT` | `/classes/{class_id}/topics/{topic_id}` | TEACHER | Update sequence_order or is_covered |
| `DELETE` | `/classes/{class_id}/topics/{topic_id}` | TEACHER | Remove topic from class |
| `PUT` | `/classes/{class_id}/topics/reorder` | TEACHER | Bulk-update sequence_order after drag |
| `POST` | `/classes/{class_id}/diagnostic/design` | TEACHER | Publish teacher-designed Tier 1 diagnostic |
| `POST` | `/classes/{class_id}/lesson-plans` | TEACHER | Trigger on-demand lesson plan generation |

---

## 9. Migration Path (Status Gate — Future)

If teachers consistently forget to complete class setup, Approach 2 (class status gate) can be adopted later with a single additive migration:

```sql
ALTER TABLE classes
  ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE';
  -- Values: SETUP | ACTIVE
```

No data restructuring needed — the `class_topics` table already exists. This is a future decision, not part of this spec.
