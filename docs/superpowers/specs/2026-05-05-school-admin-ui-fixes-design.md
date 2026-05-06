# School Admin UI Fixes — Design Spec
**Date:** 2026-05-05
**Branch:** `M0-1-T1_fix/school-admin-ui-issues`
**Scope:** Four targeted frontend + backend fixes; no schema migrations; no new routes.

---

## 1. Inactive Classes Not Appearing When Toggle Is Active

### Root Cause
`ClassService.list_classes()` (`backend/app/services/class_service.py:149`) hard-codes
`Class.is_active.is_(True)`. The `GET /schools/{school_id}/classes` route
(`backend/app/api/v1/routes/classes.py:88`) does not accept an `include_inactive` query
parameter, so the frontend toggle only sorts an already-active-only dataset.

### Backend Changes

**`backend/app/services/class_service.py`**

Extend `list_classes` signature with `include_inactive: bool = False`.
When `False` (default, existing behaviour), keep `Class.is_active.is_(True)`.
When `True`, remove that filter entirely so inactive classes are returned.

```python
async def list_classes(
    self,
    school_id: uuid.UUID,
    teacher_id: uuid.UUID | None = None,
    include_inactive: bool = False,
) -> list[Class]:
    query = select(Class).where(Class.school_id == school_id)
    if not include_inactive:
        query = query.where(Class.is_active.is_(True))
    if teacher_id:
        query = query.where(Class.teacher_id == teacher_id)
    result = await self.db.execute(query.order_by(Class.name))
    return list(result.scalars().all())
```

**`backend/app/api/v1/routes/classes.py`**

Add `include_inactive: bool = Query(False)` to `list_classes` route handler.
Pass it through to the service. Teachers always see active-only regardless of param.

```python
@router.get("/schools/{school_id}/classes")
async def list_classes(
    school_id: uuid.UUID,
    include_summary: bool = Query(False),
    include_inactive: bool = Query(False),
    current_user: CurrentUser = Depends(...),
    db: AsyncSession = Depends(get_db),
):
    service = ClassService(db)
    teacher_id = current_user.id if current_user.role == UserRole.TEACHER else None
    # Teachers always see active-only; admin roles respect the flag
    effective_inactive = include_inactive if current_user.role != UserRole.TEACHER else False
    classes = await service.list_classes(school_id, teacher_id, include_inactive=effective_inactive)
    ...
```

### Frontend Changes

**`frontend/apps/school-admin/src/hooks/useSchoolAdmin.ts`**

Change `useSchoolClasses` to accept a `showActive: boolean` param (default `true`).
Append `&include_inactive=true` when `!showActive`.
The React Query key must include `showActive` so switching the toggle triggers a new fetch.

```typescript
export function useSchoolClasses(showActive: boolean = true) {
  const schoolId = useAuthStore((state) => state.user?.school_id);
  return useQuery({
    queryKey: ["school", "classes", schoolId, showActive],
    queryFn: async () => {
      const params = new URLSearchParams({ include_summary: "true" });
      if (!showActive) params.set("include_inactive", "true");
      const res = await apiClient.get(
        `/api/v1/schools/${schoolId}/classes?${params}`,
      );
      ...
    },
    enabled: !!schoolId,
  });
}
```

**`frontend/apps/school-admin/src/pages/ClassManagement.tsx`**

Pass `showActive` state into the hook.

```typescript
const { data: classes = [], isLoading, isError } = useSchoolClasses(showActive);
```

Remove the existing client-side `activeClasses` intermediate constant — filtering is now done server-side.
Update the `filtered` computation to apply remaining client-side filters directly on `classes`.

The `attentionCount` KPI (line 20) currently derives from `activeClasses`. After the refactor it must
derive from `classes` directly — which is already active-only when `showActive=true`, so the count
remains correct without additional changes.

---

## 2. Manage Enrollments Modal Must Show Only Grade-Matched Students

### Root Cause
`ManageEnrollmentsModal` calls `useSchoolStudents()` (no grade filter) and its props
carry only `classId` and `className` — no grade context. All school students appear in
the "Available" column regardless of whether they match the class grade.

### Data Already Available
`ClassDetailPage` (line 431–432) already calls `useSchoolClasses()` and resolves
`classSummary` which has `grade_level: number | null`. This is in scope at the
`<ManageEnrollmentsModal>` call site (line 602–608). `StudentListItem` already carries
`grade_level: number | null` (returned by `useSchoolStudents()`).

### Component Changes

**`ManageEnrollmentsModal` interface and props**

Add `gradeLevel: number | null` to `ManageEnrollmentsModalProps`.

```typescript
interface ManageEnrollmentsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  classId: string;
  className?: string;
  gradeLevel: number | null;
}
```

**`availableStudents` memo** — add grade filter as first step:

```typescript
const availableStudents = useMemo(() => {
  if (!allStudents) return [];
  return allStudents.filter((s) => {
    if (gradeLevel !== null && s.grade_level !== gradeLevel) return false;
    return !enrolledIds.has(s.id);
  });
}, [allStudents, enrolledIds, gradeLevel]);
```

**`ClassDetailPage`** — pass `gradeLevel` at the call site:

```tsx
<ManageEnrollmentsModal
  open={enrollmentsModalOpen}
  onOpenChange={setEnrollmentsModalOpen}
  classId={classId!}
  className={classDetail?.name}
  gradeLevel={classSummary?.grade_level ?? null}
/>
```

### Edge Case
When `gradeLevel` is `null` (class detail not yet loaded, or grade not set on class),
filtering is skipped — all students appear. This is safe: it degrades to the previous
behaviour, which is better than showing an empty list.

---

## 3. Grade Field Blank in Edit Student Panel

### Root Cause
`EditStudentPanel` uses React Hook Form's `register()` (uncontrolled mode) for the
grade `<select>`. The `useEffect` calls `reset()` with `grade_id: student.grade_id`
whenever `student && open` changes. However, `useGrades()` is async and may not have
resolved by the time `reset()` fires. When options aren't in the DOM yet, the browser
silently ignores a `value` attribute it cannot match, leaving the select on the empty
"Select grade" option. When grades eventually load and re-render the options, RHF does
not re-sync the native select element's `selectedIndex`.

**Note:** The backend does return `grade_id` correctly (confirmed in `user_service.py:445`).
This is purely a frontend timing issue.

### Fix

Add a second `useEffect` that calls `setValue` after both `grades` and `student` are
available, running whenever `grades` resolves. This re-syncs the native select after
its options exist in the DOM.

```typescript
// In EditStudentPanel, add below the existing reset useEffect:
useEffect(() => {
  if (student && grades && open) {
    setValue("grade_id", student.grade_id ?? "");
  }
}, [grades, student, open, setValue]);
```

`setValue` is already available from `useForm` destructure — add it to the destructured
list alongside `register`, `handleSubmit`, `reset`, and `formState`.

No schema, type, or backend changes required.

---

## 4. Hide Billing Page from School Admin

### Root Cause
`BillingPage` contains entirely hardcoded placeholder data and no real billing
integration. It is reachable at `/school-admin/billing` through a live route in
`App.tsx` and a visible sidebar link in `Sidebar.tsx` (`frontend/packages/ui`).

### Changes

**`frontend/packages/ui/src/components/nav/Sidebar.tsx`**

Remove the billing entry from the school-admin nav array:

```typescript
// Remove this object from the school-admin navItems array:
{ label: "Billing", href: "/school-admin/billing", icon: CreditCard }
```

**`frontend/apps/school-admin/src/App.tsx`**

Replace the live route with a redirect:

```tsx
// Before:
<Route path="billing" element={<BillingPage />} />

// After:
<Route path="billing" element={<Navigate to="dashboard" replace />} />
```

Remove the `BillingPage` import from `App.tsx`. Do not delete `BillingPage.tsx` — keep
the file so the scaffold is ready when billing is implemented.

### Re-enabling Billing
To re-enable when billing is ready:
1. Restore the `BillingPage` import and route in `App.tsx`.
2. Re-add the nav entry in `Sidebar.tsx`.
3. Replace placeholder data in `BillingPage.tsx` with live API calls.

---

## Test Plan

### Backend (pytest)

**File:** `backend/app/tests/unit/services/test_class_service.py`

```
test_list_classes_when_include_inactive_false_then_omits_inactive_classes
  arrange: school with 2 active + 1 inactive class
  act: list_classes(school_id, include_inactive=False)
  assert: returns 2 classes, none with is_active=False

test_list_classes_when_include_inactive_true_then_returns_all_classes
  arrange: school with 2 active + 1 inactive class
  act: list_classes(school_id, include_inactive=True)
  assert: returns 3 classes including the inactive one

test_list_classes_when_teacher_role_and_include_inactive_true_then_returns_active_only
  arrange: teacher with 1 active + 1 inactive own class
  act: route called with include_inactive=true but teacher role
  assert: only active class returned (guard in route handler)
```

**File:** `backend/app/tests/integration/test_class_routes.py`

```
test_list_classes_route_when_include_inactive_true_then_returns_inactive_classes
  arrange: seed school with active + inactive class, authenticate as SCHOOL_ADMIN
  act: GET /schools/{id}/classes?include_inactive=true
  assert: 200, response includes inactive class

test_list_classes_route_when_include_inactive_false_then_omits_inactive_classes
  arrange: same seed
  act: GET /schools/{id}/classes (default)
  assert: 200, response excludes inactive class
```

### Frontend (Jest + React Testing Library)

**File:** `frontend/apps/school-admin/src/pages/__tests__/ClassManagement.test.tsx`

```
test_class_management_when_inactive_toggle_clicked_then_fetches_inactive_classes
  mock useSchoolClasses; assert it's called with showActive=false after toggle click

test_class_management_when_inactive_toggle_off_then_no_active_classes_shown
  mock: useSchoolClasses returns [{is_active: false, name: "History 8A"}]
  render with showActive=false; assert "History 8A" visible
```

**File:** `frontend/apps/school-admin/src/pages/__tests__/ManageEnrollmentsModal.test.tsx`

```
test_manage_enrollments_modal_when_grade_level_set_then_filters_available_students
  mock useSchoolStudents: [{grade_level: 7, ...studentA}, {grade_level: 8, ...studentB}]
  render with gradeLevel=7
  assert studentA visible in Available, studentB not visible

test_manage_enrollments_modal_when_grade_level_null_then_all_students_visible
  render with gradeLevel=null
  assert both students visible in Available
```

**File:** `frontend/apps/school-admin/src/pages/__tests__/StudentDetailPage.test.tsx`

```
test_edit_student_panel_when_grades_load_after_open_then_grade_select_shows_correct_grade
  arrange: student with grade_id="grade-7-uuid"
  render panel; assert select shows "Select grade" initially (grades not loaded)
  resolve grades mock; assert select now shows "Grade 7"
```

**File:** `frontend/apps/school-admin/src/App.test.tsx`

```
test_app_when_billing_route_accessed_then_redirects_to_dashboard
  render <App />, navigate to /school-admin/billing
  assert current path is /school-admin/dashboard
```

---

## Files Changed

| File | Type | Change |
|---|---|---|
| `backend/app/services/class_service.py` | Backend | Add `include_inactive` param to `list_classes` |
| `backend/app/api/v1/routes/classes.py` | Backend | Add `include_inactive` query param; guard for teacher role |
| `backend/app/tests/unit/services/test_class_service.py` | Test | 3 new unit tests |
| `backend/app/tests/integration/test_class_routes.py` | Test | 2 new integration tests |
| `frontend/apps/school-admin/src/hooks/useSchoolAdmin.ts` | Frontend | `useSchoolClasses` accepts `showActive` param |
| `frontend/apps/school-admin/src/pages/ClassManagement.tsx` | Frontend | Pass `showActive` to hook; simplify `filtered` logic |
| `frontend/apps/school-admin/src/pages/ManageEnrollmentsModal.tsx` | Frontend | Add `gradeLevel` prop; filter `availableStudents` |
| `frontend/apps/school-admin/src/pages/ClassDetailPage.tsx` | Frontend | Pass `gradeLevel` to modal |
| `frontend/apps/school-admin/src/pages/EditStudentPanel.tsx` | Frontend | Add `setValue` useEffect for grade re-sync |
| `frontend/apps/school-admin/src/App.tsx` | Frontend | Replace billing route with redirect |
| `frontend/packages/ui/src/components/nav/Sidebar.tsx` | Shared UI | Remove billing nav item for school-admin |
| `frontend/apps/school-admin/src/pages/__tests__/ClassManagement.test.tsx` | Test | New test file |
| `frontend/apps/school-admin/src/pages/__tests__/ManageEnrollmentsModal.test.tsx` | Test (exists) | Extend with grade filter tests |
| `frontend/apps/school-admin/src/pages/__tests__/StudentDetailPage.test.tsx` | Test (exists) | Extend with grade re-sync test |
| `frontend/apps/school-admin/src/App.test.tsx` | Test | Billing redirect test |

No schema changes. No new migrations. No new environment variables.
