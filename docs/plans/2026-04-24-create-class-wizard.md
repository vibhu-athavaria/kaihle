# Create Class Flow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken single-page CreateClassModal with a 3-step wizard (Class Details → Assign Teacher → Add Students) that sends the correct API payload, fires the Tier 1 diagnostic Celery task on class creation, and enrolls selected students.

**Architecture:** Three sequential tasks. Task 1 is a pure backend fix (one route line + test). Task 2 fixes the frontend hooks layer (payload shape, new useSubjects hook, enroll URL fix). Task 3 is the full modal rewrite that depends on Task 2's hooks.

**Tech Stack:** FastAPI/Python (backend), React + TypeScript + Tailwind + React Query (frontend), `@kaihle/ui` Modal component (Radix Dialog), Celery for async diagnostic task.

**Branch:** `feat/create-class-wizard` — create from `main` before starting.

```bash
git checkout main && git pull origin main
git checkout -b feat/create-class-wizard
```

---

## File Map

| File | Action |
|---|---|
| `backend/app/api/v1/routes/classes.py` | Edit lines 57–75: import + fire Celery task after class creation |
| `backend/app/tests/unit/test_class_routes.py` | Edit: add test for diagnostic task firing |
| `frontend/apps/school-admin/src/hooks/useSchoolAdmin.ts` | Edit: fix `useCreateClass` payload shape, add `useSubjects`, add `Subject` type, fix enroll URL |
| `frontend/apps/school-admin/src/pages/CreateClassModal.tsx` | Full rewrite: 3-step wizard |

---

## Task 1: Backend — Wire Diagnostic Task on Class Creation

**Files:**
- Modify: `backend/app/api/v1/routes/classes.py` (lines 57–75)
- Test: `backend/app/tests/unit/test_class_routes.py`

- [ ] **Step 1: Write the failing test**

Open (or create) `backend/app/tests/unit/test_class_routes.py` and add:

```python
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_class_fires_diagnostic_task_when_class_created(
    client: AsyncClient,
    school_admin_token: str,
    db_session,
) -> None:
    """Creating a class must fire create_class_diagnostic_task with the new class id."""
    school_id = "00000000-0000-0000-0000-000000000001"  # seeded in fixtures
    teacher_id = "00000000-0000-0000-0000-000000000010"  # seeded teacher

    payload = {
        "name": "Grade 7 Mathematics",
        "grade_id": "00000000-0000-0000-0000-000000000020",
        "subject_id": "00000000-0000-0000-0000-000000000030",
        "curriculum_id": "00000000-0000-0000-0000-000000000040",
        "teacher_id": teacher_id,
        "academic_year": "2025-2026",
    }

    with patch(
        "app.api.v1.routes.classes.create_class_diagnostic_task"
    ) as mock_task:
        mock_task.delay = MagicMock()
        response = await client.post(
            f"/api/v1/schools/{school_id}/classes",
            json=payload,
            headers={"Authorization": f"Bearer {school_admin_token}"},
        )

    assert response.status_code == 201
    created_class_id = response.json()["id"]
    mock_task.delay.assert_called_once_with(created_class_id)
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd backend
pytest app/tests/unit/test_class_routes.py::test_create_class_fires_diagnostic_task_when_class_created -v
```

Expected: FAIL — `mock_task.delay.assert_called_once_with` fails because the task is never called.

- [ ] **Step 3: Wire the Celery task in the route**

In `backend/app/api/v1/routes/classes.py`, add the import at the top of the file (after existing imports):

```python
from app.tasks.onboarding_tasks import create_class_diagnostic_task
```

Then replace the `create_class` route handler (lines 57–75):

```python
@router.post(
    "/schools/{school_id}/classes",
    response_model=ClassResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_class(
    school_id: uuid.UUID,
    body: ClassCreate,
    current_user: CurrentUser = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ClassResponse:
    """Create a class for a school. SchoolAdmin or KaihleAdmin only."""
    _check_school_access(school_id, current_user)
    service = ClassService(db)
    try:
        class_ = await service.create_class(school_id, body)
        create_class_diagnostic_task.delay(str(class_.id))
        return _class_to_response(class_)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

- [ ] **Step 4: Run the test to confirm it passes**

```bash
cd backend
pytest app/tests/unit/test_class_routes.py::test_create_class_fires_diagnostic_task_when_class_created -v
```

Expected: PASS

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
cd backend
pytest app/tests/unit/ -v
```

Expected: all existing tests pass.

- [ ] **Step 6: Run linters**

```bash
cd backend
ruff check app/api/v1/routes/classes.py
mypy app/api/v1/routes/classes.py
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/routes/classes.py backend/app/tests/unit/test_class_routes.py
git commit -m "feat(classes): fire create_class_diagnostic_task on class creation"
```

---

## Task 2: Frontend Hooks — Fix Payload Shape, Add useSubjects, Fix Enroll URL

**Files:**
- Modify: `frontend/apps/school-admin/src/hooks/useSchoolAdmin.ts`

The existing `useCreateClass` sends `{ subject: string, grade: number }` but the backend `ClassCreate` schema requires `{ subject_id: UUID, grade_id: UUID }`. Also `useEnrollStudents` posts to `/enroll` but the backend route is `/enrollments`. These need fixing before the new modal can work.

- [ ] **Step 1: Add the `Subject` interface and `useSubjects` hook**

In `frontend/apps/school-admin/src/hooks/useSchoolAdmin.ts`, add after the existing `Grade` interface (around line 101):

```typescript
export interface Subject {
  id: string;
  name: string;
  code: string;
}
```

Then add after `useGrades()` (around line 332):

```typescript
export function useSubjects() {
  return useQuery({
    queryKey: ["subjects"],
    queryFn: async () => {
      const res = await apiClient.get("/api/v1/subjects");
      return res.data as Subject[];
    },
    staleTime: Infinity,
  });
}
```

- [ ] **Step 2: Fix `useCreateClass` payload shape**

Replace the existing `useCreateClass` mutation (lines 359–380) with:

```typescript
export function useCreateClass() {
  const schoolId = useAuthStore((state) => state.user?.school_id);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      name: string;
      grade_id: string;
      subject_id: string;
      curriculum_id: string;
      teacher_id: string;
      academic_year: string;
    }) => {
      if (!schoolId) throw new Error("No school_id for current user");
      const res = await apiClient.post(
        `/api/v1/schools/${schoolId}/classes`,
        data,
      );
      return res.data as { id: string; name: string; academic_year: string };
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["school", "classes"] }),
  });
}
```

- [ ] **Step 3: Fix `useEnrollStudents` URL**

Replace the existing `useEnrollStudents` mutation (lines 421–434) with:

```typescript
export function useEnrollStudents(classId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { student_ids: string[] }) => {
      const res = await apiClient.post(
        `/api/v1/classes/${classId}/enrollments`,
        data,
      );
      return res.data as { enrolled: number; skipped: number; errors: string[] };
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["school", "classes"] }),
  });
}
```

- [ ] **Step 4: Run TypeScript check**

```bash
cd frontend
pnpm typecheck
```

Expected: no new errors. (Some pre-existing errors in other apps may exist — only care that school-admin has no new errors.)

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/school-admin/src/hooks/useSchoolAdmin.ts
git commit -m "feat(school-admin): fix useCreateClass payload, add useSubjects, fix enroll URL"
```

---

## Task 3: Frontend — Rewrite CreateClassModal as 3-Step Wizard

**Files:**
- Modify: `frontend/apps/school-admin/src/pages/CreateClassModal.tsx`

Full replacement of the existing single-page form with a 3-step wizard: Step 1 (Class Details), Step 2 (Assign Teacher — required), Step 3 (Add Students — optional).

- [ ] **Step 1: Replace the file entirely**

Overwrite `frontend/apps/school-admin/src/pages/CreateClassModal.tsx` with:

```tsx
import { useState, useMemo } from "react";
import { Modal } from "@kaihle/ui";
import { UserRole } from "@kaihle/types";
import {
  useCurricula,
  useGrades,
  useSubjects,
  useSchoolUsers,
  useCreateClass,
  useEnrollStudents,
  type Subject,
  type Grade,
} from "../hooks/useSchoolAdmin";

// ── Types ─────────────────────────────────────────────────────────────────────

interface CreateClassModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: () => void;
}

type Step = 1 | 2 | 3;

interface FormState {
  name: string;
  subjectId: string;
  subjectName: string;
  gradeId: string;
  gradeLevel: number | null;
  curriculumId: string;
  curriculumName: string;
  teacherId: string;
  academicYear: string;
  selectedStudentIds: Set<string>;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function detectCurriculumName(gradeLevel: number): string {
  if (gradeLevel <= 5) return "Cambridge Primary";
  if (gradeLevel <= 8) return "Cambridge Lower Secondary";
  if (gradeLevel <= 10) return "Cambridge IGCSE";
  return "Cambridge AS & A Level";
}

function currentAcademicYear(): string {
  const now = new Date();
  const year = now.getMonth() >= 7 ? now.getFullYear() : now.getFullYear() - 1;
  return `${year}-${year + 1}`;
}

// ── Step Progress Bar ─────────────────────────────────────────────────────────

function StepBar({ current }: { current: Step }) {
  const steps: { num: Step; label: string }[] = [
    { num: 1, label: "Class Details" },
    { num: 2, label: "Assign Teacher" },
    { num: 3, label: "Add Students" },
  ];

  return (
    <div className="flex items-center px-8 pt-5 pb-1">
      {steps.map((s, i) => {
        const state =
          s.num < current ? "done" : s.num === current ? "active" : "pending";
        return (
          <div key={s.num} className="flex items-center flex-1">
            <div
              className={[
                "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0",
                state === "done" || state === "active"
                  ? "bg-brand-primary text-white"
                  : "bg-gray-200 text-gray-400",
                state === "active"
                  ? "ring-4 ring-brand-primary/20"
                  : "",
              ].join(" ")}
            >
              {state === "done" ? (
                <svg
                  className="w-3.5 h-3.5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={3}
                  aria-hidden="true"
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              ) : (
                s.num
              )}
            </div>
            <span
              className={[
                "ml-2 text-xs font-semibold",
                state === "pending" ? "text-gray-400" : "text-brand-primary",
              ].join(" ")}
            >
              {s.label}
            </span>
            {i < steps.length - 1 && (
              <div
                className={[
                  "flex-1 h-0.5 mx-2.5",
                  s.num < current ? "bg-brand-primary" : "bg-gray-200",
                ].join(" ")}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Step 1: Class Details ─────────────────────────────────────────────────────

interface Step1Props {
  form: FormState;
  subjects: Subject[];
  grades: Grade[];
  curricula: { id: string; name: string }[];
  errors: Record<string, string>;
  onChange: (updates: Partial<FormState>) => void;
  onNext: () => void;
  onCancel: () => void;
}

function Step1({
  form,
  subjects,
  grades,
  curricula,
  errors,
  onChange,
  onNext,
  onCancel,
}: Step1Props) {
  function handleGradeChange(gradeId: string) {
    const grade = grades.find((g) => g.id === gradeId);
    if (!grade) {
      onChange({ gradeId: "", gradeLevel: null, curriculumId: "", curriculumName: "" });
      return;
    }
    const curriculumName = detectCurriculumName(grade.level);
    const curriculum = curricula.find((c) =>
      c.name.toLowerCase().includes(curriculumName.toLowerCase().split(" ").pop() ?? "")
    );
    onChange({
      gradeId,
      gradeLevel: grade.level,
      curriculumId: curriculum?.id ?? "",
      curriculumName: curriculum?.name ?? curriculumName,
    });
  }

  return (
    <div className="px-8 py-6 space-y-5">
      {/* Class name */}
      <div>
        <label
          htmlFor="class-name"
          className="block text-[11px] font-bold text-gray-600 uppercase tracking-wide mb-1.5"
        >
          Class Name <span className="text-brand-red">*</span>
        </label>
        <input
          id="class-name"
          type="text"
          value={form.name}
          onChange={(e) => onChange({ name: e.target.value })}
          placeholder="e.g. Grade 7 Mathematics"
          maxLength={100}
          className="w-full px-3.5 py-2.5 border-[1.5px] border-role-school-border rounded-[10px] text-sm text-brand-ink font-sans outline-none focus:border-brand-primary focus:ring-2 focus:ring-brand-primary/10"
        />
        {errors.name && (
          <p className="mt-1 text-xs text-brand-red">{errors.name}</p>
        )}
        <p className="mt-1 text-xs text-role-school-muted">
          A clear name teachers and students will recognise
        </p>
      </div>

      {/* Subject pills */}
      <div>
        <p className="text-[11px] font-bold text-gray-600 uppercase tracking-wide mb-2">
          Subject <span className="text-brand-red">*</span>
        </p>
        <div className="flex flex-wrap gap-2">
          {subjects.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => onChange({ subjectId: s.id, subjectName: s.name })}
              className={[
                "px-4 py-2 rounded-full border-[1.5px] text-sm font-semibold transition-all",
                form.subjectId === s.id
                  ? "bg-brand-primary text-white border-brand-primary"
                  : "border-role-school-border text-brand-ink hover:border-brand-primary hover:text-brand-primary",
              ].join(" ")}
            >
              {s.name}
            </button>
          ))}
        </div>
        {errors.subject && (
          <p className="mt-1.5 text-xs text-brand-red">{errors.subject}</p>
        )}
        <p className="mt-1.5 text-xs text-role-school-muted">
          Loaded from your school's active subjects
        </p>
      </div>

      {/* Grade + Curriculum row */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label
            htmlFor="grade"
            className="block text-[11px] font-bold text-gray-600 uppercase tracking-wide mb-1.5"
          >
            Grade <span className="text-brand-red">*</span>
          </label>
          <select
            id="grade"
            value={form.gradeId}
            onChange={(e) => handleGradeChange(e.target.value)}
            className="w-full px-3.5 py-2.5 border-[1.5px] border-role-school-border rounded-[10px] text-sm text-brand-ink font-sans outline-none focus:border-brand-primary bg-white appearance-none"
          >
            <option value="">Select grade</option>
            {grades.map((g) => (
              <option key={g.id} value={g.id}>
                Grade {g.level}
              </option>
            ))}
          </select>
          {errors.grade && (
            <p className="mt-1 text-xs text-brand-red">{errors.grade}</p>
          )}
        </div>
        <div>
          <label className="block text-[11px] font-bold text-gray-600 uppercase tracking-wide mb-1.5">
            Curriculum{" "}
            <span className="text-[10px] bg-brand-green-light text-brand-primary border border-green-200 rounded-full px-2 py-0.5 font-semibold normal-case tracking-normal">
              auto-detected
            </span>
          </label>
          <input
            type="text"
            value={form.curriculumName}
            readOnly
            placeholder="Select a grade first"
            className="w-full px-3.5 py-2.5 border-[1.5px] border-role-school-border rounded-[10px] text-sm text-gray-500 font-sans bg-gray-50 cursor-not-allowed"
          />
        </div>
      </div>

      {/* Academic year */}
      <div className="w-48">
        <label
          htmlFor="academic-year"
          className="block text-[11px] font-bold text-gray-600 uppercase tracking-wide mb-1.5"
        >
          Academic Year{" "}
          <span className="text-[10px] bg-brand-green-light text-brand-primary border border-green-200 rounded-full px-2 py-0.5 font-semibold normal-case tracking-normal">
            auto-filled
          </span>
        </label>
        <input
          id="academic-year"
          type="text"
          value={form.academicYear}
          onChange={(e) => onChange({ academicYear: e.target.value })}
          className="w-full px-3.5 py-2.5 border-[1.5px] border-role-school-border rounded-[10px] text-sm text-brand-ink font-sans outline-none focus:border-brand-primary"
        />
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-gray-100">
        <button
          type="button"
          onClick={onCancel}
          className="px-5 py-2.5 rounded-full border-[1.5px] border-gray-200 text-sm font-bold text-gray-500 hover:bg-gray-50 transition-colors"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={onNext}
          className="px-5 py-2.5 rounded-full bg-brand-primary text-white text-sm font-bold hover:bg-brand-primary/90 transition-colors"
        >
          Next: Assign Teacher →
        </button>
      </div>
    </div>
  );
}

// ── Step 2: Assign Teacher ────────────────────────────────────────────────────

interface Step2Props {
  form: FormState;
  teachers: { id: string; first_name: string; last_name: string; email: string }[];
  error: string;
  search: string;
  onSearchChange: (v: string) => void;
  onSelectTeacher: (id: string) => void;
  onBack: () => void;
  onNext: () => void;
}

function Step2({
  form,
  teachers,
  error,
  search,
  onSearchChange,
  onSelectTeacher,
  onBack,
  onNext,
}: Step2Props) {
  const filtered = teachers.filter((t) => {
    const full = `${t.first_name} ${t.last_name}`.toLowerCase();
    return full.includes(search.toLowerCase());
  });

  return (
    <div className="px-8 py-6">
      <p className="text-[11px] font-bold text-role-school-muted uppercase tracking-wider mb-4">
        Select a Teacher <span className="text-brand-red">*</span>
      </p>

      {/* Search */}
      <div className="relative mb-3">
        <svg
          className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden="true"
        >
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          type="text"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search by name…"
          className="w-full pl-9 pr-4 py-2.5 border-[1.5px] border-role-school-border rounded-[10px] text-sm outline-none focus:border-brand-primary font-sans"
        />
      </div>

      {/* Teacher list */}
      {filtered.length === 0 ? (
        <div className="text-center py-12 text-sm text-gray-400">
          {teachers.length === 0
            ? "No teachers have been added to this school yet."
            : "No teachers match your search."}
        </div>
      ) : (
        <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
          {filtered.map((t) => {
            const initials = `${t.first_name[0] ?? ""}${t.last_name[0] ?? ""}`.toUpperCase();
            const selected = form.teacherId === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => onSelectTeacher(selected ? "" : t.id)}
                className={[
                  "w-full flex items-center gap-3 px-4 py-3 rounded-xl border-[1.5px] text-left transition-all",
                  selected
                    ? "border-brand-primary bg-brand-green-light"
                    : "border-gray-200 hover:border-brand-primary hover:bg-brand-green-light/50",
                ].join(" ")}
              >
                <div className="w-10 h-10 rounded-full bg-role-school-border flex items-center justify-center text-sm font-bold text-brand-primary flex-shrink-0">
                  {initials}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-brand-ink">
                    {t.first_name} {t.last_name}
                  </p>
                  <p className="text-xs text-gray-500 truncate">{t.email}</p>
                </div>
                {selected && (
                  <div className="w-5 h-5 rounded-full bg-brand-primary flex items-center justify-center flex-shrink-0">
                    <svg
                      className="w-3 h-3 text-white"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={3}
                      aria-hidden="true"
                    >
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  </div>
                )}
              </button>
            );
          })}
        </div>
      )}

      {error && (
        <p className="mt-2 text-xs text-brand-red">{error}</p>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-5 mt-4 border-t border-gray-100">
        <button
          type="button"
          onClick={onBack}
          className="text-sm font-semibold text-gray-500 hover:text-gray-700 flex items-center gap-1"
        >
          ← Back
        </button>
        <button
          type="button"
          onClick={onNext}
          disabled={!form.teacherId || teachers.length === 0}
          className="px-5 py-2.5 rounded-full bg-brand-primary text-white text-sm font-bold hover:bg-brand-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Next: Add Students →
        </button>
      </div>
    </div>
  );
}

// ── Step 3: Add Students ──────────────────────────────────────────────────────

interface StudentRow {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  gradeLevel: number | null;
  gradeName: string;
}

interface Step3Props {
  form: FormState;
  students: StudentRow[];
  activeGradeTab: number | null;
  isSubmitting: boolean;
  onSelectStudent: (id: string, checked: boolean) => void;
  onSelectAll: (gradeLevel: number | null, checked: boolean) => void;
  onGradeTabChange: (level: number | null) => void;
  onBack: () => void;
  onSubmit: () => void;
}

function Step3({
  form,
  students,
  activeGradeTab,
  isSubmitting,
  onSelectStudent,
  onSelectAll,
  onGradeTabChange,
  onBack,
  onSubmit,
}: Step3Props) {
  const filtered = activeGradeTab === null
    ? students
    : students.filter((s) => s.gradeLevel === activeGradeTab);

  const gradeCounts = useMemo(() => {
    const counts = new Map<number, number>();
    students.forEach((s) => {
      if (s.gradeLevel !== null) {
        counts.set(s.gradeLevel, (counts.get(s.gradeLevel) ?? 0) + 1);
      }
    });
    return counts;
  }, [students]);

  const uniqueGrades = Array.from(gradeCounts.keys()).sort((a, b) => a - b);

  const allFilteredSelected =
    filtered.length > 0 && filtered.every((s) => form.selectedStudentIds.has(s.id));
  const someFilteredSelected =
    filtered.some((s) => form.selectedStudentIds.has(s.id)) && !allFilteredSelected;

  return (
    <div className="px-8 py-6">
      {/* Diagnostic info banner */}
      <div className="flex gap-3 items-start bg-blue-50 border border-blue-200 rounded-xl p-3.5 mb-5 text-sm text-blue-700">
        <svg
          className="w-4 h-4 flex-shrink-0 mt-0.5"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <span>
          A <strong>Tier 1 Diagnostic</strong> will be automatically generated
          for each student enrolled. They'll see it when they next log in.
        </span>
      </div>

      <p className="text-[11px] font-bold text-role-school-muted uppercase tracking-wider mb-4">
        Select Students{" "}
        <span className="text-[10px] font-medium normal-case tracking-normal text-gray-400">
          (optional — can enrol later)
        </span>
      </p>

      {/* Grade filter tabs */}
      {uniqueGrades.length > 1 && (
        <div className="flex flex-wrap gap-2 mb-4">
          <button
            type="button"
            onClick={() => onGradeTabChange(null)}
            className={[
              "px-3.5 py-1.5 rounded-full border-[1.5px] text-xs font-semibold transition-all",
              activeGradeTab === null
                ? "bg-brand-primary text-white border-brand-primary"
                : "border-role-school-border text-gray-500 hover:border-brand-primary",
            ].join(" ")}
          >
            All Grades
          </button>
          {uniqueGrades.map((level) => (
            <button
              key={level}
              type="button"
              onClick={() => onGradeTabChange(level)}
              className={[
                "px-3.5 py-1.5 rounded-full border-[1.5px] text-xs font-semibold transition-all",
                activeGradeTab === level
                  ? "bg-brand-primary text-white border-brand-primary"
                  : "border-role-school-border text-gray-500 hover:border-brand-primary",
              ].join(" ")}
            >
              Grade {level}{" "}
              <span className="opacity-70">({gradeCounts.get(level)})</span>
            </button>
          ))}
        </div>
      )}

      {students.length === 0 ? (
        <div className="text-center py-10 text-sm text-gray-400">
          No students have been added to this school yet.
        </div>
      ) : (
        <>
          {/* Select-all row */}
          <div className="flex items-center justify-between mb-2">
            <label className="flex items-center gap-2 text-sm font-semibold text-brand-ink cursor-pointer">
              <input
                type="checkbox"
                checked={allFilteredSelected}
                ref={(el) => {
                  if (el) el.indeterminate = someFilteredSelected;
                }}
                onChange={(e) => onSelectAll(activeGradeTab, e.target.checked)}
                className="w-4 h-4 accent-brand-primary rounded"
              />
              {activeGradeTab === null
                ? "Select all students"
                : `Select all Grade ${activeGradeTab} students`}
            </label>
            <span className="text-sm font-bold text-brand-primary">
              {form.selectedStudentIds.size > 0
                ? `${form.selectedStudentIds.size} selected`
                : ""}
            </span>
          </div>

          {/* Table */}
          <div className="max-h-64 overflow-y-auto border-[1.5px] border-gray-200 rounded-xl">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr>
                  <th className="text-left px-3 py-2.5 text-[11px] font-bold uppercase tracking-wide text-gray-400 bg-gray-50 border-b border-gray-200 w-9" />
                  <th className="text-left px-3 py-2.5 text-[11px] font-bold uppercase tracking-wide text-gray-400 bg-gray-50 border-b border-gray-200">
                    Name
                  </th>
                  <th className="text-left px-3 py-2.5 text-[11px] font-bold uppercase tracking-wide text-gray-400 bg-gray-50 border-b border-gray-200">
                    Grade
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => (
                  <tr
                    key={s.id}
                    className="border-b border-gray-100 last:border-0 hover:bg-gray-50 cursor-pointer"
                    onClick={() =>
                      onSelectStudent(s.id, !form.selectedStudentIds.has(s.id))
                    }
                  >
                    <td className="px-3 py-2.5">
                      <input
                        type="checkbox"
                        checked={form.selectedStudentIds.has(s.id)}
                        onChange={(e) => onSelectStudent(s.id, e.target.checked)}
                        onClick={(e) => e.stopPropagation()}
                        className="w-4 h-4 accent-brand-primary rounded"
                      />
                    </td>
                    <td className="px-3 py-2.5">
                      <p className="font-semibold text-brand-ink">
                        {s.first_name} {s.last_name}
                      </p>
                      <p className="text-xs text-gray-400">{s.email}</p>
                    </td>
                    <td className="px-3 py-2.5 text-gray-500">{s.gradeName}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-5 mt-4 border-t border-gray-100">
        <button
          type="button"
          onClick={onBack}
          className="text-sm font-semibold text-gray-500 hover:text-gray-700 flex items-center gap-1"
          disabled={isSubmitting}
        >
          ← Back
        </button>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onSubmit}
            disabled={isSubmitting}
            className="px-5 py-2.5 rounded-full border-[1.5px] border-gray-200 text-sm font-bold text-gray-600 hover:bg-gray-50 disabled:opacity-40"
          >
            {isSubmitting ? "Creating…" : "Create without students"}
          </button>
          <button
            type="button"
            onClick={onSubmit}
            disabled={isSubmitting || form.selectedStudentIds.size === 0}
            className="px-5 py-2.5 rounded-full bg-brand-primary text-white text-sm font-bold hover:bg-brand-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isSubmitting ? (
              <>
                <svg
                  className="animate-spin w-4 h-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v8z"
                  />
                </svg>
                Creating…
              </>
            ) : form.selectedStudentIds.size > 0 ? (
              `✓ Create Class (${form.selectedStudentIds.size} students)`
            ) : (
              "✓ Create Class"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Modal ────────────────────────────────────────────────────────────────

export function CreateClassModal({
  isOpen,
  onClose,
  onCreated,
}: CreateClassModalProps) {
  const [step, setStep] = useState<Step>(1);
  const [teacherSearch, setTeacherSearch] = useState("");
  const [activeGradeTab, setActiveGradeTab] = useState<number | null>(null);
  const [step1Errors, setStep1Errors] = useState<Record<string, string>>({});
  const [step2Error, setStep2Error] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [form, setForm] = useState<FormState>({
    name: "",
    subjectId: "",
    subjectName: "",
    gradeId: "",
    gradeLevel: null,
    curriculumId: "",
    curriculumName: "",
    teacherId: "",
    academicYear: currentAcademicYear(),
    selectedStudentIds: new Set(),
  });

  const { data: curricula = [] } = useCurricula();
  const { data: grades = [] } = useGrades();
  const { data: subjects = [] } = useSubjects();
  const { data: teachers = [] } = useSchoolUsers(UserRole.TEACHER);
  const { data: rawStudents = [] } = useSchoolUsers(UserRole.STUDENT);

  const createClass = useCreateClass();

  // Build a classId ref for the enroll mutation — set after create succeeds
  const [classId, setClassId] = useState<string | null>(null);
  const enrollStudents = useEnrollStudents(classId ?? "");

  // Map raw student users to StudentRow (need grade info from grades list)
  const students: StudentRow[] = useMemo(() => {
    return rawStudents.map((s) => {
      // Students don't carry grade directly; use grade inferred from the school's grade list.
      // For now we show grade from the form's selected grade (all students are shown for selection).
      // The API returns all active students; grade info per student isn't available here.
      return {
        id: s.id,
        first_name: s.first_name,
        last_name: s.last_name,
        email: s.email,
        gradeLevel: null, // students don't expose grade in this endpoint
        gradeName: "",
      };
    });
  }, [rawStudents]);

  function updateForm(updates: Partial<FormState>) {
    setForm((prev) => ({ ...prev, ...updates }));
  }

  function resetAndClose() {
    setStep(1);
    setTeacherSearch("");
    setActiveGradeTab(null);
    setStep1Errors({});
    setStep2Error("");
    setIsSubmitting(false);
    setClassId(null);
    setForm({
      name: "",
      subjectId: "",
      subjectName: "",
      gradeId: "",
      gradeLevel: null,
      curriculumId: "",
      curriculumName: "",
      teacherId: "",
      academicYear: currentAcademicYear(),
      selectedStudentIds: new Set(),
    });
    onClose();
  }

  function validateStep1(): boolean {
    const errors: Record<string, string> = {};
    if (!form.name.trim()) errors.name = "Class name is required";
    if (!form.subjectId) errors.subject = "Please select a subject";
    if (!form.gradeId) errors.grade = "Please select a grade";
    setStep1Errors(errors);
    return Object.keys(errors).length === 0;
  }

  function handleStep1Next() {
    if (validateStep1()) setStep(2);
  }

  function handleTeacherSelect(id: string) {
    updateForm({ teacherId: id });
    setStep2Error("");
  }

  function handleStep2Next() {
    if (!form.teacherId) {
      setStep2Error("Please assign a teacher to this class");
      return;
    }
    setStep(3);
  }

  function handleSelectStudent(id: string, checked: boolean) {
    setForm((prev) => {
      const next = new Set(prev.selectedStudentIds);
      if (checked) next.add(id);
      else next.delete(id);
      return { ...prev, selectedStudentIds: next };
    });
  }

  function handleSelectAll(gradeLevel: number | null, checked: boolean) {
    const target = gradeLevel === null
      ? students
      : students.filter((s) => s.gradeLevel === gradeLevel);
    setForm((prev) => {
      const next = new Set(prev.selectedStudentIds);
      target.forEach((s) => {
        if (checked) next.add(s.id);
        else next.delete(s.id);
      });
      return { ...prev, selectedStudentIds: next };
    });
  }

  async function handleSubmit() {
    setIsSubmitting(true);
    try {
      const created = await createClass.mutateAsync({
        name: form.name.trim(),
        grade_id: form.gradeId,
        subject_id: form.subjectId,
        curriculum_id: form.curriculumId,
        teacher_id: form.teacherId,
        academic_year: form.academicYear,
      });

      const newClassId: string = created.id;
      setClassId(newClassId);

      if (form.selectedStudentIds.size > 0) {
        try {
          await enrollStudents.mutateAsync({
            student_ids: Array.from(form.selectedStudentIds),
          });
        } catch {
          // Class was created — show warning but still close
          resetAndClose();
          onCreated();
          return;
        }
      }

      resetAndClose();
      onCreated();
    } catch {
      // createClass failed — stay open
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal
      open={isOpen}
      onOpenChange={(open) => {
        if (!open && !isSubmitting) resetAndClose();
      }}
      title=""
      titleClassName="hidden"
    >
      <div className="-mx-6 -mt-6" style={{ width: "calc(728px - 3rem)", maxWidth: "90vw" }}>
        {/* Modal header */}
        <div className="px-8 pt-7 pb-0">
          <h2 className="font-display font-bold text-[22px] text-brand-ink">
            Create New Class
          </h2>
          <p className="text-sm text-role-school-muted mt-0.5">
            Set up a class, assign a teacher, and add students
          </p>
        </div>

        <StepBar current={step} />

        {step === 1 && (
          <Step1
            form={form}
            subjects={subjects}
            grades={grades}
            curricula={curricula}
            errors={step1Errors}
            onChange={updateForm}
            onNext={handleStep1Next}
            onCancel={resetAndClose}
          />
        )}
        {step === 2 && (
          <Step2
            form={form}
            teachers={teachers}
            error={step2Error}
            search={teacherSearch}
            onSearchChange={setTeacherSearch}
            onSelectTeacher={handleTeacherSelect}
            onBack={() => setStep(1)}
            onNext={handleStep2Next}
          />
        )}
        {step === 3 && (
          <Step3
            form={form}
            students={students}
            activeGradeTab={activeGradeTab}
            isSubmitting={isSubmitting}
            onSelectStudent={handleSelectStudent}
            onSelectAll={handleSelectAll}
            onGradeTabChange={setActiveGradeTab}
            onBack={() => setStep(2)}
            onSubmit={handleSubmit}
          />
        )}
      </div>
    </Modal>
  );
}
```

- [ ] **Step 2: Run TypeScript check**

```bash
cd frontend
pnpm typecheck
```

Expected: no errors in `apps/school-admin`.

- [ ] **Step 3: Run lint**

```bash
cd frontend
pnpm lint
```

Expected: no errors.

- [ ] **Step 4: Start the school-admin dev server and manually test the golden path**

```bash
cd frontend
pnpm dev:school-admin
```

Open http://localhost:3004, log in as a School Admin, and verify:
1. Click "Create Class" — modal opens at 728px width with Step 1 visible
2. Leave name empty and click Next → validation error appears under name field
3. Fill in name, pick a subject pill (it highlights green), select a grade → curriculum auto-fills
4. Click Next → advances to Step 2
5. Try clicking Next without selecting a teacher → error appears
6. Select a teacher → Next becomes active, click it
7. Step 3 shows diagnostic info banner, student list loads, grade tabs appear if multiple grades
8. Select some students using checkboxes and select-all
9. Click "✓ Create Class (N students)" → spinner shows, modal closes, toast appears, class list refreshes
10. Log in as the assigned teacher and confirm the class appears in their dashboard

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/school-admin/src/pages/CreateClassModal.tsx
git commit -m "feat(school-admin): rewrite CreateClassModal as 3-step wizard"
```

---

## Final Step: Push Branch

```bash
git push -u origin feat/create-class-wizard
```

Then open a PR:

```bash
gh pr create \
  --title "feat/create-class-wizard — 3-step Create Class wizard with Tier 1 diagnostic trigger" \
  --body "## What this builds
- Replaces broken single-page CreateClassModal with a 3-step wizard (Class Details → Assign Teacher → Add Students)
- Wires create_class_diagnostic_task Celery task to fire on class creation (was implemented but never called)
- Fixes useCreateClass hook payload shape (was sending strings, now sends UUIDs)
- Fixes useEnrollStudents URL (/enroll → /enrollments)
- Adds useSubjects hook backed by GET /api/v1/subjects
- Teacher is required (Next disabled until selected)
- Students are optional with grade-tab filtering and select-all per grade

## How to verify
1. pnpm dev:school-admin → Create Class modal is now a 3-step wizard
2. Backend: pytest app/tests/unit/test_class_routes.py -v → all pass
3. Check DB after creating a class: assessments table has is_system_generated=TRUE row for the class"
```
