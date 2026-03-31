# M0-7-T3-hotfix — Student Dashboard: Nine Remaining Bugs
**Milestone:** M0 — Foundations
**Epic:** M0-7 — Frontend Foundations
**Task ID:** M0-7-T3-hotfix
**Executor:** Coding agent
**Depends on:** M0-7-T3-patch (already merged)
**Blocks:** Nothing
**Estimated effort:** 2–3 hours
**Reference mockup:** `docs/design/mockups/student_dashboard.html`
**Design authority:** `docs/design/DESIGN_SYSTEM.md` §5.4

> Read `docs/design/DESIGN_SYSTEM.md` §5.4 before touching any component.
> Read `docs/design/screens/STUDENT_SCREENS.md` before touching any route or layout.

---

## Critical rule before starting

**Do NOT rewrite any file from scratch.** Every fix below is a surgical edit.
Identify the exact lines described, make only the stated change, leave everything
else untouched.

---

## Do NOT Touch

- `frontend/apps/student/src/pages/onboarding/` — any file
- `frontend/apps/student/src/store/questionnaireStore.ts`
- `frontend/apps/student/src/hooks/useOnboardingStatus.ts`
- Any backend file
- Any file in `apps/teacher/`, `apps/parent/`, `apps/school-admin/`, `apps/kaihle-admin/`
- `packages/ui/src/components/nav/Sidebar.tsx` — Teacher/SchoolAdmin/Admin only
- `packages/ui/src/layouts/DashboardLayout.tsx`

---

## Bug 1 — `useSubjectScores.ts`: queryFn returns Axios response, not data

### File
`frontend/apps/student/src/hooks/useSubjectScores.ts`

### What is wrong
The `queryFn` in `useSubjectGapMap` returns the raw `AxiosResponse` object.
React Query stores whatever `queryFn` returns as `data`. So when
`aggregateSubjectMastery(data)` is called in `SingleSubjectCardWithCallback`,
it receives an `AxiosResponse` — not the gap map payload. `data.scores` is
`undefined` on an `AxiosResponse`. Every subject card shows "–" / "Not assessed"
regardless of real mastery.

### What to change
Find this block in `useSubjectScores.ts`:

```typescript
// FIND THIS — WRONG
queryFn: () => {
  if (!subjectId) {
    throw new Error("subjectId is required");
  }
  return apiClient.get(`/api/v1/students/me/gap-map`, {
    params: { subject_id: subjectId },
  });
},
```

Replace it with:

```typescript
// REPLACE WITH — CORRECT
queryFn: async () => {
  if (!subjectId) {
    throw new Error("subjectId is required");
  }
  const response = await apiClient.get(`/api/v1/students/me/gap-map`, {
    params: { subject_id: subjectId },
  });
  return response.data;   // ← return the payload, not the AxiosResponse
},
```

No other changes to this file.

---

## Bug 2 — `useStudentInfo.ts`: interface uses snake_case but API returns camelCase

### File
`frontend/apps/student/src/hooks/useStudentInfo.ts`

### What is wrong
The backend `StudentInfoResponse` schema uses Pydantic field aliases:
```python
first_name: str = Field(..., alias="firstName")
grade_name: str = Field(..., alias="gradeName")
curriculum_name: str = Field(..., alias="curriculumName")
```

When FastAPI serializes by alias (default), the JSON response contains `firstName`,
`gradeName`, `curriculumName` — camelCase. The TypeScript interface in
`useStudentInfo.ts` declares `first_name`, `grade_name`, `curriculum_name` —
snake_case. JavaScript does not auto-convert field names, so `studentInfo?.first_name`
is always `undefined`. The greeting shows "Good morning, Student 👋" instead of
the real name.

### What to change
Replace the entire `StudentInfo` interface:

```typescript
// FIND AND REPLACE THE ENTIRE INTERFACE

// WRONG — current
export interface StudentInfo {
  id: string;
  first_name: string;
  last_name: string;
  grade_name: string;
  curriculum_name: string;
  school_id: string;
}

// CORRECT — replace with
export interface StudentInfo {
  id: string;
  firstName: string;        // camelCase — matches backend alias="firstName"
  lastName?: string;        // camelCase — matches backend alias="lastName" (if present)
  gradeName: string;        // camelCase — matches backend alias="gradeName"
  curriculumName: string;   // camelCase — matches backend alias="curriculumName"
  schoolId: string;         // camelCase — matches backend alias="schoolId"
  classId?: string | null;
  isEnrolled?: boolean;
}
```

No other changes to this file.

---

## Bug 3 — `StudentDashboard.tsx`: student name, grade, curriculum always empty

### File
`frontend/apps/student/src/pages/dashboard/StudentDashboard.tsx`

### What is wrong
After Bug 2 is fixed, the field access in `StudentDashboard.tsx` must also use
camelCase. Find these lines:

```typescript
// FIND — WRONG
const firstName = studentInfo?.first_name || "";
const lastName = studentInfo?.last_name || "";
```

### What to change

```typescript
// REPLACE WITH — CORRECT
const firstName = studentInfo?.firstName || "";
const lastName = studentInfo?.lastName || "";
const studentName =
  firstName && lastName ? `${firstName} ${lastName}` : firstName || "Student";
const gradeName = studentInfo?.gradeName || "";
const curriculumName = studentInfo?.curriculumName || "";
```

Search for any other references to `studentInfo?.first_name`, `studentInfo?.grade_name`,
`studentInfo?.curriculum_name` in this file and update them to camelCase equivalents.

---

## Bug 4 — `StudentDashboard.tsx`: study plans and assessments hardcoded as empty arrays

### File
`frontend/apps/student/src/pages/dashboard/StudentDashboard.tsx`

### What is wrong
These two lines hardcode empty arrays, so "What's waiting for you" will always show
the "all caught up" state regardless of real data:

```typescript
// FIND — WRONG
const studyPlans: Array<{ id: string; title: string; status: string }> = [];
const assessments: Array<{ id: string; subjectName: string; dueDate: string }> = [];
```

### What to change

**Step 1 — Add import for `useStudentDashboard`** at the top of the file:

```typescript
import { useStudentDashboard } from "../../hooks/useStudentDashboard";
```

**Step 2 — Call the hook** inside `StudentDashboard()`, alongside the existing hooks:

```typescript
const { data: dashboardData, isLoading: isDashboardLoading } = useStudentDashboard();
```

**Step 3 — Replace the hardcoded arrays**:

```typescript
// REPLACE the two hardcoded empty array lines with:
const studyPlans = dashboardData?.studyPlans ?? [];
const assessments = dashboardData?.assessments ?? [];
```

**Step 4 — Update the isLoading check** used for the skeleton in "What's waiting":

Find:
```typescript
{isInfoLoading || isClassesLoading ? (
```

Replace with:
```typescript
{isInfoLoading || isClassesLoading || isDashboardLoading ? (
```

No other changes. Do not touch `buildNextSteps`.

---

## Bug 5 — `AccountSection.tsx`: calls endpoint that does not exist

### File
`frontend/apps/student/src/components/settings/AccountSection.tsx`

### What is wrong
The component calls `GET /api/v1/users/me` which does not exist in the live API.
The correct endpoint is `GET /api/v1/schools/{school_id}/users/me`.

### What to change

**Step 1 — Add import** for `useStudentInfo` at the top of `AccountSection.tsx`:

```typescript
import { useStudentInfo } from "../../hooks/useStudentInfo";
```

**Step 2 — Call the hook** inside `AccountSection()` to get `schoolId`:

```typescript
const { data: studentInfo } = useStudentInfo();
const schoolId = studentInfo?.schoolId;
```

**Step 3 — Fix the query**. Find:

```typescript
// FIND — WRONG
queryFn: async () => {
  const response = await apiClient.get<User>("/api/v1/users/me");
  return response.data;
},
```

Replace with:

```typescript
// REPLACE WITH — CORRECT
queryFn: async () => {
  if (!schoolId) throw new Error("School ID not available");
  const response = await apiClient.get<User>(
    `/api/v1/schools/${schoolId}/users/me`
  );
  return response.data;
},
```

**Step 4 — Add `schoolId` to the query key** so React Query refetches when it changes.
Find:

```typescript
queryKey: ["student", "settings", "user"],
```

Replace with:

```typescript
queryKey: ["student", "settings", "user", schoolId],
```

**Step 5 — Add `enabled` guard** so the query doesn't fire before `schoolId` is known.
Find the closing brace of the `useQuery` options object and add:

```typescript
enabled: !!schoolId,
```

No other changes to this file.

---

## Bug 6 — Other pages pass no identity props to `StudentLayout`

### Files
- `frontend/apps/student/src/pages/my-progress/MyProgress.tsx`
- `frontend/apps/student/src/pages/study-plans/StudyPlans.tsx`
- `frontend/apps/student/src/pages/assessments/Assessments.tsx`
- `frontend/apps/student/src/pages/settings/StudentSettings.tsx`

### What is wrong
These pages call `StudentLayout` without `studentName`, `gradeName`,
`curriculumName`, or `classes`. The sidebar profile card renders empty
("" name, no grade/curriculum) on all pages except the dashboard.

### What to change — apply identically to all four files

**Step 1 — Add imports** at the top of each file:

```typescript
import { useStudentInfo } from "../../hooks/useStudentInfo";
import { useMyClasses, type StudentClassResponse } from "../../hooks/useMyClasses";
```

Note: adjust the relative import path `../../hooks/` for `StudentSettings.tsx`
which lives one level deeper (`../../components/settings/` → `../../hooks/`
becomes `../../../hooks/`). Check the actual file path before writing the import.

**Step 2 — Call the hooks** inside each page component:

```typescript
const { data: studentInfo } = useStudentInfo();
const { data: classesData } = useMyClasses();

const firstName    = studentInfo?.firstName    ?? "";
const lastName     = studentInfo?.lastName     ?? "";
const studentName  = [firstName, lastName].filter(Boolean).join(" ") || "Student";
const gradeName    = studentInfo?.gradeName    ?? "";
const curriculumName = studentInfo?.curriculumName ?? "";

const sidebarClasses = (Array.isArray(classesData) ? classesData : []).map(
  (cls: StudentClassResponse) => ({
    id:                  cls.id,
    name:                cls.name,
    subjectName:         cls.subjectName,
    subjectId:           cls.subjectId,
    diagnosticStatus:    cls.onboardingDiagnosticStatus,
    diagnosticAttemptId: cls.diagnosticAttemptId,
  })
);
```

**Step 3 — Pass the props** to `StudentLayout` in each file:

```tsx
// BEFORE (wrong — no identity props)
<StudentLayout activeNav="progress" onLogout={logout}>

// AFTER (correct — full identity props)
<StudentLayout
  activeNav="progress"         // keep whatever activeNav was already set
  studentName={studentName}
  gradeName={gradeName}
  curriculumName={curriculumName}
  classes={sidebarClasses}
  onLogout={logout}
>
```

Apply this pattern to all four files. Keep the existing `activeNav` value for
each file (`"progress"` for MyProgress, `"study"` for StudyPlans, etc.).
`StudentSettings.tsx` has no `activeNav` — pass `activeNav="home"` as a default
since settings is accessed via avatar, not the nav.

---

## Bug 7 — `SubjectScoreCard.tsx`: pixel font sizes violate design system

### File
`frontend/apps/student/src/pages/dashboard/SubjectScoreCard.tsx`

### What is wrong
`DESIGN_SYSTEM.md` Hard Rule: *"No font-size in px — always rem via Tailwind
text scale."* This file uses raw pixel sizes on page content elements.

### Typography reference (from `DESIGN_SYSTEM.md` §5.4)

| Element | Current (WRONG) | Required (CORRECT) | Reason |
|---|---|---|---|
| Score value | `text-[20px] font-bold` | `font-sans font-extrabold text-2xl leading-tight` | `text-2xl` = 1.5rem = 24px — larger and bolder |
| Subject name | `text-[9px] font-bold uppercase tracking-[0.5px] text-[#9ca3af]` | `font-sans font-bold text-xs uppercase tracking-wide text-brand-muted` | Use token, not hex; `text-xs` = 0.75rem |
| Band label | `text-[9px] font-semibold` | `font-sans text-xs text-brand-muted` | `text-xs` = 0.75rem; use semantic token |

### What to change

Find and replace the JSX in `SubjectScoreCard`:

```tsx
// FIND — WRONG
<div className={`text-[20px] font-bold ${textClass} mb-0.5`}>
  {displayPct}
</div>
<div className="text-[9px] font-bold uppercase tracking-[0.5px] text-[#9ca3af] mb-0.5">
  {subjectName}
</div>
<div className={`inline-block text-[9px] font-semibold px-1.5 py-0.5 rounded-[5px] ${textClass}`}>
  {label}
</div>
```

```tsx
// REPLACE WITH — CORRECT
<div className={`font-sans font-extrabold text-2xl leading-tight ${textClass}`}>
  {displayPct}
</div>
<div className="font-sans font-bold text-xs uppercase tracking-wide text-brand-muted mt-1">
  {subjectName}
</div>
<div className="font-sans text-xs text-brand-muted mt-0.5">
  {label}
</div>
```

Also update the card container from `p-3` to `p-4` and `rounded-[10px]` to `rounded-2xl`
to match the mockup proportions:

```tsx
// FIND
<div className={`bg-white rounded-[10px] border-[1.5px] ${borderClass} p-3 text-center`}>

// REPLACE WITH
<div className={`bg-white rounded-2xl border-[1.5px] ${borderClass} p-4 text-center`}>
```

---

## Bug 8 — `NextStepCard.tsx` and `ClassCard.tsx`: pixel font sizes

### Files
- `frontend/apps/student/src/pages/dashboard/NextStepCard.tsx`
- `frontend/apps/student/src/components/ClassCard.tsx`

### Typography reference (from `DESIGN_SYSTEM.md` §5.4 and Typography Reference table)

| Element | Current (WRONG) | Required (CORRECT) |
|---|---|---|
| NextStepCard title | `text-[11px] font-semibold` | `font-sans font-semibold text-sm` |
| NextStepCard subtitle | `text-[9px] text-brand-muted` | `font-sans text-xs text-brand-muted` |
| NextStepCard action link | `text-[10px] font-bold` | `font-sans font-bold text-xs` |
| ClassCard class name | `text-[11px] font-semibold font-display` | `font-sans font-semibold text-sm` |
| ClassCard meta (teacher + grade) | `text-[9px] text-brand-muted` | `font-sans text-xs text-brand-muted` |
| ClassCard footer link | `text-[10px] font-semibold` | `font-sans font-semibold text-xs` |

### Changes to `NextStepCard.tsx`

Find and replace each of these three class strings:

```tsx
// 1. Title — FIND
<div className="text-[11px] font-semibold text-brand-ink">
// REPLACE WITH
<div className="font-sans font-semibold text-sm text-brand-ink">

// 2. Subtitle — FIND
<div className="text-[9px] text-brand-muted">
// REPLACE WITH
<div className="font-sans text-xs text-brand-muted mt-0.5">

// 3. Action button — FIND
className="text-[10px] font-bold text-brand-primary whitespace-nowrap hover:underline min-h-[44px] flex items-center focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
// REPLACE WITH
className="font-sans font-bold text-xs text-brand-primary whitespace-nowrap hover:underline min-h-[44px] flex items-center focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 ml-4"
```

### Changes to `ClassCard.tsx`

Find and replace each of these three class strings:

```tsx
// 1. Class name heading — FIND
<span className="text-[11px] font-semibold font-display text-brand-ink truncate">
// REPLACE WITH
<span className="font-sans font-semibold text-sm text-brand-ink truncate">

// 2. Teacher + grade meta — FIND
<div className="text-[9px] text-brand-muted mb-2">
// REPLACE WITH
<div className="font-sans text-xs text-brand-muted mb-3">

// 3. Footer link text — the two <span> elements inside the CTA div
// FIND the wrapping div
<div className={`text-[10px] font-semibold ${isLocked ? "text-brand-gold" : "text-brand-primary"}`}>
// REPLACE WITH
<div className={`font-sans font-semibold text-xs ${isLocked ? "text-brand-gold" : "text-brand-primary"}`}>
```

---

## Bug 9 — `student-app.spec.ts`: stale comment describes old layout

### File
`frontend/apps/student/src/tests/student-app.spec.ts`

### What is wrong
The comment says *"Design: StudentLayout with top + bottom nav, green primary buttons,
no sidebar"* — this was the v1 spec. The layout is now sidebar-based per v2.1.

### What to change

Find:
```typescript
/**
 * Smoke test for Student app - verifies correct app is loaded
 * Design: StudentLayout with top + bottom nav, green primary buttons, no sidebar
 */
```

Replace with:
```typescript
/**
 * Smoke test for Student app - verifies correct app is loaded
 * Design: StudentLayout v2.1 — left sidebar, green primary buttons, no bottom nav
 * Reference: docs/design/DESIGN_SYSTEM.md §5.4, docs/design/mockups/student_dashboard.html
 */
```

---

## Files to modify (no new files)

```
frontend/apps/student/src/hooks/useSubjectScores.ts        Bug 1
frontend/apps/student/src/hooks/useStudentInfo.ts           Bug 2
frontend/apps/student/src/pages/dashboard/StudentDashboard.tsx  Bugs 3, 4
frontend/apps/student/src/components/settings/AccountSection.tsx  Bug 5
frontend/apps/student/src/pages/my-progress/MyProgress.tsx     Bug 6
frontend/apps/student/src/pages/study-plans/StudyPlans.tsx      Bug 6
frontend/apps/student/src/pages/assessments/Assessments.tsx     Bug 6
frontend/apps/student/src/pages/settings/StudentSettings.tsx    Bug 6
frontend/apps/student/src/pages/dashboard/SubjectScoreCard.tsx  Bug 7
frontend/apps/student/src/pages/dashboard/NextStepCard.tsx      Bug 8
frontend/apps/student/src/components/ClassCard.tsx              Bug 8
frontend/apps/student/src/tests/student-app.spec.ts            Bug 9
```

---

## Verification checklist — confirm each before pushing

### Data correctness
- [ ] Subject score cards show real mastery percentages (not always "–")
- [ ] Greeting shows real first name, not "Student"
- [ ] Top nav subtitle shows real grade and curriculum
- [ ] Profile card in sidebar shows real name, grade, curriculum
- [ ] "What's waiting for you" fetches from API (not always "all caught up")
- [ ] MyProgress, StudyPlans, Assessments, Settings pages all show sidebar with real identity data

### API endpoints — verify each call hits exactly these URLs
- [ ] `GET /api/v1/students/me/gap-map?subject_id={uuid}` — one per subject
- [ ] `GET /api/v1/students/me/info` — student identity
- [ ] `GET /api/v1/students/me/classes` — class list
- [ ] `GET /api/v1/students/me/study-plans?status=active,in_progress&limit=10`
- [ ] `GET /api/v1/schools/{school_id}/users/me` — settings account section
- [ ] `GET /api/v1/onboarding/learning-profile` — settings learning profile section
- [ ] NO calls to `/api/v1/users/me` (this endpoint does not exist)

### Typography — open devtools and inspect each element
- [ ] Subject score values use `text-2xl` class (24px / 1.5rem) — NOT `text-[20px]`
- [ ] Subject name labels use `text-xs` class (12px / 0.75rem) — NOT `text-[9px]`
- [ ] Class card names use `text-sm` class (14px / 0.875rem) — NOT `text-[11px]`
- [ ] Next step card titles use `text-sm` — NOT `text-[11px]`
- [ ] Next step subtitles use `text-xs` — NOT `text-[9px]`
- [ ] No `text-[Npx]` classes remain on any page content element (sidebar chrome exempt)

### TypeScript
- [ ] `tsc --noEmit` passes with zero errors in `apps/student`
- [ ] No TypeScript errors on `StudentInfo` field access after camelCase fix

---

## Acceptance criteria — named tests

Add these tests to `frontend/apps/student/src/hooks/__tests__/useStudentInfo.test.ts`
(create the file if it does not exist):

`test_student_info_interface_uses_camelcase_fields`
Construct a mock response `{ firstName: "Jane", gradeName: "Grade 9", curriculumName: "Cambridge IGCSE", schoolId: "abc" }`.
Assert that TypeScript compiles without error when assigning to `StudentInfo`.
Assert that `info.firstName === "Jane"` (not `info.first_name`).

`test_student_info_snake_case_fields_are_undefined`
Given the same mock, assert that accessing `(info as any).first_name === undefined`.
This confirms the interface no longer expects snake_case.

Add to `frontend/apps/student/src/hooks/__tests__/useSubjectScores.test.ts`
(already exists — add these cases):

`test_use_subject_gap_map_returns_data_not_axios_response`
Mock `apiClient.get` to resolve with `{ data: { scores: [{ mastery_score: 0.8 }] } }`.
Call `queryFn` from `useSubjectGapMap`.
Assert the resolved value has a `scores` property (not `data.scores`) — confirming
`response.data` is returned, not the whole AxiosResponse.

---

## Branch and commit

```
Branch: M0-7-T3-hotfix/fix-nine-remaining-bugs

Commit:
fix(student): hotfix nine bugs — data, types, endpoints, typography

- Bug 1: useSubjectGapMap queryFn now returns response.data (was returning
  AxiosResponse — caused all subject cards to show "–")
- Bug 2: useStudentInfo interface now uses camelCase (firstName, gradeName,
  curriculumName, schoolId) to match backend Pydantic alias serialisation
- Bug 3: StudentDashboard field access updated to camelCase after Bug 2 fix
- Bug 4: Wire useStudentDashboard — remove hardcoded empty studyPlans/assessments
- Bug 5: AccountSection uses GET /schools/{school_id}/users/me (not /users/me)
- Bug 6: MyProgress, StudyPlans, Assessments, Settings now pass studentName,
  gradeName, curriculumName, classes to StudentLayout for consistent sidebar
- Bug 7: SubjectScoreCard — text-[20px]/text-[9px] → text-2xl/text-xs (rem scale)
- Bug 8: NextStepCard + ClassCard — all text-[Npx] → Tailwind rem tokens
- Bug 9: Update stale smoke test comment to reflect sidebar layout v2.1
```
