# Create Class Flow — Design Spec
**Date:** 2026-04-24  
**Status:** Approved  
**Roles affected:** School Admin, Teacher, Student

---

## 1. Context & Goal

School Admins need a guided way to create subject classes, assign a teacher, and enrol students — all from a single workflow. Once created:
- The assigned **teacher** sees the class in their dashboard immediately
- **Enrolled students** see the class in their dashboard with a Tier 1 Diagnostic triggered automatically
- The admin sees the class in the Class Management list with live status

Currently, a partial `CreateClassModal` exists but it: uses hardcoded subjects, sends the wrong payload shape to the backend (strings instead of UUIDs), doesn't trigger the Tier 1 diagnostic on class creation, and doesn't include student selection. This spec replaces it entirely.

---

## 2. Flow Overview

```
School Admin clicks "Create Class"
  → 3-step wizard modal (728px wide)
      Step 1: Class Details     (required before proceeding)
      Step 2: Assign Teacher    (optional — skippable)
      Step 3: Add Students      (optional — skippable)
  → On "Create Class" confirm:
      POST /api/v1/schools/{schoolId}/classes        (create class + teacher)
      POST /api/v1/classes/{classId}/enrollments     (enroll selected students)
      Celery: create_class_diagnostic_task fires     (triggered by route after class creation)
      Celery: trigger_onboarding_diagnostics fires   (triggered per-student by enroll endpoint)
  → Modal closes, class list refreshes, success toast shown
```

---

## 3. Modal — Structure & Sizing

| Property | Value |
|---|---|
| Width | 728px (30% larger than the old 560px) |
| Max height | 92vh with internal scroll on body |
| Border radius | 20px |
| Backdrop | rgba(0,0,0,0.35) |
| Box shadow | 0 24px 80px rgba(0,0,0,0.18) |
| Font (title) | Fraunces, 22px, weight 700 |
| Font (body) | Nunito throughout |
| Padding (header) | 26px 32px |
| Padding (body) | 24px 32px |
| Padding (footer) | 18px 32px |
| Footer background | #fafafa with 1px top border #f3f4f6 |

**Modal component:** Must use `Modal` from `@kaihle/ui` (Radix Dialog wrapper) per CONSTITUTION Rule 21. Focus trapped, Escape closes, focus returns to trigger button.

---

## 4. Step Progress Bar

Three steps rendered at the top of the modal below the header:

```
[✓ done] ——— [● active] ——— [○ pending]
Class Details   Assign Teacher   Add Students
```

| State | Circle style | Label colour |
|---|---|---|
| `done` | bg-brand-primary, white checkmark | text-brand-primary |
| `active` | bg-brand-primary, white number, ring shadow | text-brand-primary |
| `pending` | bg-gray-200, gray number | text-gray-400 |

Connector line between steps: `h-2px bg-border` → `bg-brand-primary` when left step is done.

---

## 5. Step 1 — Class Details

### Fields

| Field | Type | Required | Source | Notes |
|---|---|---|---|---|
| Class Name | Text input | Yes | Admin types it | Max 100 chars. Hint: "A clear name teachers and students will recognise" |
| Subject | Pill selector | Yes | `GET /api/v1/subjects` | Dynamic — not hardcoded. Renders as clickable pills. Only one selectable. Falls back to dropdown if > 8 subjects |
| Grade | Dropdown | Yes | `GET /api/v1/grades?curriculum_id=...` | Filtered by selected curriculum once subject is chosen; initially all active grades |
| Curriculum | Read-only text input | Yes | Auto-detected from grade level | Rule: level 1–5 → Cambridge Primary, 6–8 → Cambridge Lower Secondary, 9–10 → Cambridge IGCSE, 11–12 → Cambridge AS & A Level. Not editable. Badge: "auto-detected" |
| Academic Year | Text input | Yes | Auto-filled "YYYY–YYYY" | Computed as `{currentYear}–{currentYear+1}`. Editable. |

### Subject pill behaviour
- Pills loaded from `GET /api/v1/subjects` on modal open (or from React Query cache)
- Only one pill selectable at a time (single-select)
- Selected: `bg-brand-primary text-white border-brand-primary`
- Unselected: `border-role-school-border text-brand-ink hover:border-brand-primary hover:text-brand-primary`
- If no subject is selected and admin clicks Next → validation error below pills: "Please select a subject"

### Curriculum auto-detection logic (frontend)
```typescript
function detectCurriculum(gradeLevel: number): string {
  if (gradeLevel <= 5)  return 'Cambridge Primary'
  if (gradeLevel <= 8)  return 'Cambridge Lower Secondary'
  if (gradeLevel <= 10) return 'Cambridge IGCSE'
  return 'Cambridge AS & A Level'
}
```
The actual `curriculum_id` UUID is resolved by matching the detected name against the curricula fetched from `GET /api/v1/curricula`.

### Validation (Step 1 — cannot proceed to Step 2 without)
- Class name: non-empty, max 100 chars
- Subject: one selected
- Grade: one selected
- Curriculum: auto-resolved (never fails unless API is down)

### Footer
| Left | Right |
|---|---|
| Cancel button (ghost) | "Next: Assign Teacher →" (primary) |

---

## 6. Step 2 — Assign Teacher

### Layout
- Section label: "Select a Teacher" (no optional qualifier — required)
- Search input (full width) — client-side filter on already-loaded teacher list
- Scrollable teacher card list (max-height: 320px)

### Teacher card fields
| Field | Source |
|---|---|
| Avatar initials | First + last name initials |
| Full name | `GET /api/v1/schools/{schoolId}/users?role=TEACHER` |
| Metadata line | "Mathematics · 3 active classes" — subject from first active class; class count from summary |
| Selection check | Green circle with checkmark, appears on selection |

### Data source
Teachers loaded from `useSchoolUsers(UserRole.TEACHER)` — already implemented in `useSchoolAdmin.ts`. Filtered client-side by the search input.

### Behaviour
- Only one teacher selectable (single-select)
- A teacher **must** be selected before proceeding — "Next: Add Students →" is disabled until a teacher is chosen
- If no teacher selected and admin clicks Next → validation message below the list: "Please assign a teacher to this class"
- Clicking a selected teacher deselects them (returns button to disabled state)

### Footer
| Left | Right |
|---|---|
| ← Back (text button) | "Next: Add Students →" (primary, disabled until a teacher is selected) |

---

## 7. Step 3 — Add Students

### Layout (top to bottom)
1. **Info banner** (blue) — "A Tier 1 Diagnostic will be automatically generated for each enrolled student. They'll see it when they log in."
2. Section label: "Select Students" + "(optional — can enroll later)"
3. Grade filter tabs
4. Select-all row
5. Student table (scrollable, max-height 280px)

### Grade filter tabs
- Tabs generated dynamically from grades present in the school's student population
- Each tab shows: "Grade N (count)" — count is students in that grade not yet enrolled in this class
- "All Grades" tab always present as first tab
- Active tab: `bg-brand-primary text-white border-brand-primary`
- Inactive: `border-role-school-border text-gray-500`
- Selecting a tab filters the student table; does NOT deselect already-selected students from other grades

### Select-all checkbox
- "Select all Grade N students" label — updates dynamically with active tab
- Checked when all visible (filtered) students are checked
- Indeterminate when some but not all are checked
- Clicking it selects/deselects all visible filtered students
- Counter on the right: "X selected" — reflects total across ALL grades, not just filtered view

### Student table columns
| Column | Notes |
|---|---|
| Checkbox | Multi-select |
| Name + email | Student full name (bold), email (muted below) |
| Grade | Grade name |
| Enrolment Status | "Not enrolled yet" (green badge) or "Already enrolled" (muted badge — if a student is already in this class, they appear greyed-out and non-selectable) |

### Data source
`GET /api/v1/schools/{schoolId}/users?role=STUDENT` — returns all active students in the school. Load on modal open. Filter on client. This endpoint likely exists; if not, it shares the same `useSchoolUsers` hook pattern.

### Students already enrolled (edge case)
If the admin somehow opens this modal for a class that already has students (e.g., re-opening after partial creation), those students show "Already enrolled" badge, are pre-checked but disabled (cannot be unchecked from this modal — they'd need to be removed from the class detail view).

### Footer
| Left | Right |
|---|---|
| ← Back (text button) | "Create without students" (ghost) + "✓ Create Class (N students)" (primary) |

The primary button label updates live: "✓ Create Class" when 0 selected, "✓ Create Class (N students)" when N > 0.

---

## 8. Submission Logic (What Happens on "Create Class")

The modal does **not** create the class on Step 1 completion — it collects all data first and submits everything on the final "Create Class" click. This is a two-API-call sequence:

### Call 1 — Create Class
```
POST /api/v1/schools/{schoolId}/classes
Body: {
  name: string,
  grade_id: UUID,
  subject_id: UUID,
  curriculum_id: UUID,
  teacher_id: UUID,          ← Required
  academic_year: string      ← e.g. "2025-2026"
}
```
On success: receive `class_id`. Backend route must also fire `create_class_diagnostic_task.delay(class_id)` here.

### Call 2 — Enroll Students (only if any selected)
```
POST /api/v1/classes/{classId}/enrollments
Body: { student_ids: UUID[] }
```
This endpoint already fires `trigger_onboarding_diagnostics.delay(student_id, class_id)` per new enrollment.

### Sequencing
Calls are sequential (not parallel) — `classId` from Call 1 is required for Call 2. If Call 1 fails, show error toast and stay on modal. If Call 2 fails (partial enrolment), close modal but show warning toast: "Class created, but some students couldn't be enrolled. Check the class page."

### Loading state
While submitting: primary button shows spinner + "Creating…" text, all inputs and nav disabled. This follows CONSTITUTION Rule 22 (button spinner for async actions).

### Success state
- Modal closes
- React Query invalidates `schoolClasses` cache → class list refreshes
- Success toast: "Grade 7 Mathematics created with 12 students enrolled."

---

## 9. Post-Creation — Dashboard Effects

### Teacher dashboard
- Teacher sees the new class card in their class list immediately (via cache invalidation on teacher's `GET /teacher/classes` query or on next page load)
- Class shows "Diagnostic pending" state until the Celery task completes

### Student dashboard
- Each enrolled student's class sidebar entry appears on next login or page refresh
- Class card shows locked state (arrow icon, no lock icon per CONSTITUTION §5.4 spec)
- `onboarding_diagnostic_status = PENDING` → becomes `IN_PROGRESS` when `trigger_onboarding_diagnostics` completes

### Class Management list (school-admin)
- New class appears immediately at the top of the list (sorted by created_at desc)
- Shows: class name, subject colour dot, grade, teacher name (or "No teacher assigned"), student count, diagnostic status chip

---

## 10. Empty & Error States

| Scenario | UI Behaviour |
|---|---|
| No subjects loaded | Skeleton pulses in subject pill area; if API fails, error message "Couldn't load subjects" with retry button |
| No teachers in school | Step 2 shows empty state: "No teachers have been added to this school yet. Add a teacher before creating a class." Next button disabled. |
| No students in school | Step 3 shows empty state: "No students added yet. You can enrol students later from the class settings." |
| Class name already exists | POST returns 409 → inline error under class name field: "A class with this name already exists for this school year" |
| Subject has no questions in question bank | Tier 1 diagnostic task will log a WARNING and skip (graceful — not a blocker for class creation) |
| Network error on submission | Error toast with retry option; modal stays open |

---

## 11. Backend Changes Required

### 11.1 — `teacher_id` is required — no schema change needed
`teacher_id: UUID` remains required in `ClassCreate`. The class cannot be created without a teacher assigned.

### 11.2 — Wire `create_class_diagnostic_task` in the create_class route
**File:** `backend/app/api/v1/routes/classes.py`

After the class is successfully committed, fire:
```python
from app.tasks.onboarding_tasks import create_class_diagnostic_task
create_class_diagnostic_task.delay(str(new_class.id))
```
This task is fully implemented in `backend/app/tasks/onboarding_tasks.py` — it just isn't called from the route yet.

### 11.3 — Ensure `GET /api/v1/schools/{schoolId}/users?role=STUDENT` works
The student selection in Step 3 needs to fetch all active students in the school. Verify this query param is supported in the existing school users endpoint. If not, add `role` filter to `SchoolService.get_school_users()`.

### 11.4 — Academic year format
Backend `ClassCreate.academic_year` is `str`. Frontend sends `"2025-2026"` (hyphen, not en-dash). Ensure consistency — backend stores whatever string is sent, no parsing needed.

---

## 12. Frontend Changes Required

### 12.1 — Replace `CreateClassModal.tsx` entirely
**File:** `frontend/apps/school-admin/src/pages/CreateClassModal.tsx`

Full rewrite with:
- 3-step wizard structure using local state (`step: 1 | 2 | 3`)
- Step 1: dynamic subject pills from `useSubjects()`, dynamic grades from `useGrades()`, curriculum auto-detection
- Step 2: teacher cards from `useSchoolUsers(TEACHER)` with client-side search
- Step 3: student table from `useSchoolUsers(STUDENT)` with grade tabs + select-all
- Two-call submission sequence with sequential `useCreateClass` → `useEnrollStudents` mutations
- Uses `Modal` from `@kaihle/ui`

### 12.2 — New or updated hooks in `useSchoolAdmin.ts`
| Hook | Status | Notes |
|---|---|---|
| `useCreateClass()` | Exists | Verify payload shape matches new `ClassCreate` schema |
| `useEnrollStudents(classId)` | Exists | Unchanged |
| `useSchoolUsers(role)` | Exists | Verify it works for `STUDENT` role, not just `TEACHER` |
| `useSubjects()` | Needs creation | `GET /api/v1/subjects` — global, not school-scoped |
| `useGrades()` | Exists | Already implemented |
| `useCurricula()` | Exists | Already implemented — needed to resolve curriculum UUID from name |

### 12.3 — New `useSubjects` hook
```typescript
export function useSubjects() {
  return useQuery({
    queryKey: ['subjects'],
    queryFn: () => apiClient.get<SubjectResponse[]>('/subjects').then(r => r.data),
    staleTime: Infinity, // subjects rarely change
  })
}
```

### 12.4 — No changes to ClassManagement.tsx
The class list page already polls `useSchoolClasses()` with `include_summary=true`. React Query cache invalidation on successful creation will refresh it automatically.

---

## 13. Files to Create / Modify

| File | Action | Notes |
|---|---|---|
| `frontend/apps/school-admin/src/pages/CreateClassModal.tsx` | **Full rewrite** | 3-step wizard |
| `frontend/apps/school-admin/src/hooks/useSchoolAdmin.ts` | **Add** `useSubjects()` | +verify `useSchoolUsers(STUDENT)` |
| `backend/app/schemas/class_enrollment.py` | **Edit** | `teacher_id: Optional[UUID] = None` |
| `backend/app/services/class_service.py` | **Edit** | Handle `teacher_id=None` in `create_class()` |
| `backend/app/api/v1/routes/classes.py` | **Edit** | Fire `create_class_diagnostic_task.delay()` after class creation |

---

## 14. What We Are NOT Building (Scope Boundary)

- Editing a class (assign teacher later, add/remove students) — this is a separate "Class Detail" view, not in this spec
- Removing students from a class via this modal
- Bulk-creating multiple classes at once
- Copying a class from a previous academic year
- Sending email notifications to teacher/students on enrolment (future milestone)

---

## 15. Verification Plan

### Manual test (golden path)
1. Log in as School Admin
2. Navigate to Class Management → click "Create Class"
3. Step 1: enter name, select subject, select grade — confirm curriculum auto-detects, academic year auto-fills
4. Step 2: select a teacher — confirm teacher list loads from API (not hardcoded)
5. Step 3: switch grade tabs, use select-all, manually deselect 1 student — confirm counter updates
6. Click "Create Class" — confirm spinner, then modal closes, toast appears, class appears in list
7. Log in as the assigned teacher → confirm new class appears in dashboard
8. Log in as an enrolled student → confirm class appears, locked (diagnostic arrow), `onboarding_diagnostic_status = PENDING`
9. Confirm in DB: `assessments` table has a new row with `is_system_generated=TRUE` for the class

### Backend unit tests
- `test_create_class_when_no_teacher_then_succeeds` — `teacher_id=None` accepted
- `test_create_class_fires_diagnostic_task_when_class_created` — Celery task called with class_id
- `test_enroll_students_when_valid_then_triggers_diagnostic_per_student` — already exists, verify still passes

### Frontend tests
- Step navigation: cannot proceed from Step 1 without name + subject + grade
- Subject pills: selecting one deselects others
- Grade tabs: switching tab filters table, does not lose selections from other grade tabs
- Select-all: correctly toggles all visible students
- "Create without students" skips enrolment call entirely
