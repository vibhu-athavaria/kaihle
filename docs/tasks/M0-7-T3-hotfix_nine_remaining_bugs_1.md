# M0-7-T3-hotfix — Student Dashboard: Complete Fix (All Remaining Issues)
**Milestone:** M0 — Foundations
**Epic:** M0-7 — Frontend Foundations
**Task ID:** M0-7-T3-hotfix
**Executor:** Coding agent
**Depends on:** M0-7-T3-patch (merged)
**Estimated effort:** 3–4 hours
**Design authority:** `docs/design/DESIGN_SYSTEM.md` · `docs/design/screens/STUDENT_SCREENS.md`

> Before touching any file: open `docs/design/DESIGN_SYSTEM.md` and read §2 (tokens),
> §5.4 (Student spec), and the Type Scale table in §3. Every class you write must map
> to a row in those sections.

---

## Critical rule

**Surgical edits only. Find the exact string, replace it, leave everything else alone.**
Do not rewrite files from scratch. Do not add new features. Fix only what is listed below.

---

## Do NOT touch

- `frontend/apps/student/src/pages/onboarding/` — any file
- `frontend/apps/student/src/hooks/useOnboardingStatus.ts`
- `frontend/apps/student/src/store/questionnaireStore.ts`
- `frontend/packages/ui/src/layouts/DashboardLayout.tsx`
- `frontend/packages/ui/src/components/nav/Sidebar.tsx`
- `frontend/packages/ui/src/components/nav/BottomNav.tsx`
- Any backend file
- Any file in `apps/teacher/`, `apps/parent/`, `apps/school-admin/`, `apps/kaihle-admin/`

---

## Fix 1 — `tailwind.config.js`: Add three missing tokens

**File:** `frontend/packages/ui/tailwind.config.js`

Three hex values appear hardcoded in components because they have no token. Fix the config
first — every subsequent fix in this task depends on these tokens existing.

### 1a — Add `nav-active` to `role-student` block

```js
// FIND
'role-student': {
  bg:     '#f9fafb',
  border: '#e5e7eb',
  // Subject cards use colored borders derived from getMasteryStyle()
  // See DESIGN_SYSTEM.md §5.4 for the colored-border card pattern
},

// REPLACE WITH
'role-student': {
  bg:           '#f9fafb',   // page background
  border:       '#e5e7eb',   // card borders, dividers
  'nav-active': '#f0fdf4',   // active sidebar nav tint (NOT the mastery Strong tint)
  'nav-locked-hover': '#fffbeb',  // hover tint for locked class items (amber/gold tint)
},
```

### 1b — Add `nav-active` to `role-teacher` block

```js
// FIND
'role-teacher': {
  bg:     '#f5f7f1',
  sidebar: '#ffffff',
  border: '#e5e7eb',
  muted:  '#9ca3af',
  body:   '#4a5240',
  // Active nav: bg-[#fffbeb] text-brand-gold-dark (gold tint)
},

// REPLACE WITH
'role-teacher': {
  bg:         '#f5f7f1',
  sidebar:    '#ffffff',
  border:     '#e5e7eb',
  muted:      '#9ca3af',
  body:       '#4a5240',
  'nav-active': '#fffbeb',   // active sidebar nav tint — Teacher gold tint
},
```

After this fix, the available tokens are:
- `bg-role-student-nav-active` → `#f0fdf4`
- `bg-role-student-nav-locked-hover` → `#fffbeb`
- `bg-role-teacher-nav-active` → `#fffbeb`
- `text-role-teacher-nav-active` → (same value, used for text on that bg)

---

## Fix 2 — `StudentLayout.tsx`: Replace two hardcoded hex values with tokens

**File:** `frontend/packages/ui/src/layouts/StudentLayout.tsx`

Two hex values remain in the component. Both now have tokens from Fix 1.

### 2a — Active nav tint

```tsx
// FIND
"bg-[#f0fdf4] text-brand-primary font-semibold"

// REPLACE WITH
"bg-role-student-nav-active text-brand-primary font-semibold"
```

### 2b — Locked class item hover tint

```tsx
// FIND
"text-brand-gold hover:bg-[#fffbeb]"

// REPLACE WITH
"text-brand-gold hover:bg-role-student-nav-locked-hover"
```

---

## Fix 3 — `NavItem.tsx`: Replace hardcoded hex with token

**File:** `frontend/packages/ui/src/components/nav/NavItem.tsx`

```tsx
// FIND
teacher: "bg-[#fffbeb] text-brand-gold-dark font-bold rounded-lg",

// REPLACE WITH
teacher: "bg-role-teacher-nav-active text-brand-gold-dark font-bold rounded-lg",
```

---

## Fix 4 — `StudentShellLayout.tsx`: Delete the file

**File:** `frontend/packages/ui/src/layouts/StudentShellLayout.tsx`

This layout is dead code. `StudentDashboard.tsx` switched to `StudentLayout`.
`StudentShellLayout` is used by no page and should not exist alongside the correct layout.

**Step 1:** Delete `frontend/packages/ui/src/layouts/StudentShellLayout.tsx`.

**Step 2:** Remove the export from `frontend/packages/ui/src/index.ts`:

```ts
// FIND and DELETE this line
export { StudentShellLayout } from "./layouts/StudentShellLayout";
```

**Step 3:** Remove the export from `frontend/packages/ui/src/layouts/index.ts` if present:

```ts
// FIND and DELETE this line (if it exists)
export { StudentShellLayout } from "./StudentShellLayout";
```

---

## Fix 5 — `useSubjectScores.ts`: Return `response.data` not the AxiosResponse

**File:** `frontend/apps/student/src/hooks/useSubjectScores.ts`

This is why all subject score cards show "–". `aggregateSubjectMastery(data)` receives
an `AxiosResponse` object — not the gap map payload — so `data.scores` is always undefined.

```typescript
// FIND — WRONG
queryFn: () => {
  if (!subjectId) {
    throw new Error("subjectId is required");
  }
  return apiClient.get(`/api/v1/students/me/gap-map`, {
    params: { subject_id: subjectId },
  });
},

// REPLACE WITH — CORRECT
queryFn: async () => {
  if (!subjectId) {
    throw new Error("subjectId is required");
  }
  const response = await apiClient.get(`/api/v1/students/me/gap-map`, {
    params: { subject_id: subjectId },
  });
  return response.data;   // ← return the JSON payload, not the AxiosResponse wrapper
},
```

---

## Fix 6 — `StudentDashboard.tsx`: Wire study plans + assessments + fix section headings

**File:** `frontend/apps/student/src/pages/dashboard/StudentDashboard.tsx`

Three changes in this file.

### 6a — Import `useStudentDashboard`

Add to the imports at the top of the file:

```tsx
import { useStudentDashboard } from "../../hooks/useStudentDashboard";
```

### 6b — Call the hook inside `StudentDashboard()`

Add after the existing hook calls (`useStudentInfo`, `useMyClasses`):

```tsx
const { data: dashboardData, isLoading: isDashboardLoading } = useStudentDashboard();
```

### 6c — Replace the hardcoded empty arrays

```tsx
// FIND and DELETE these two lines entirely
const studyPlans: Array<{ id: string; title: string; status: string }> = [];
const assessments: Array<{
  id: string;
  subjectName: string;
  dueDate: string;
}> = [];

// REPLACE WITH — read from the hook
const studyPlans = dashboardData?.studyPlans ?? [];
const assessments = dashboardData?.assessments ?? [];
```

### 6d — Update the loading check for "What's waiting for you"

```tsx
// FIND
{isInfoLoading || isClassesLoading ? (

// REPLACE WITH
{isInfoLoading || isClassesLoading || isDashboardLoading ? (
```

### 6e — Fix section heading colors: `text-brand-muted` → `text-brand-body`

`text-brand-muted` (#9ca3af) is for placeholder and disabled text only.
Section headings ("YOUR SUBJECTS", "MY CLASSES", "WHAT'S WAITING FOR YOU") are
real navigation landmarks and must use `text-brand-body` (#4a5240).

Find every occurrence of this exact class string in `StudentDashboard.tsx`
and apply the replacement:

```tsx
// FIND (appears 2–3 times)
"font-sans text-xs font-bold uppercase tracking-widest text-brand-muted mb-3"

// REPLACE WITH
"font-sans text-xs font-bold uppercase tracking-widest text-brand-body mb-3"
```

---

## Fix 7 — `SubjectScoreCard.tsx`: Font sizes, colors, spacing

**File:** `frontend/apps/student/src/pages/dashboard/SubjectScoreCard.tsx`

### Typography reference for this component

| Element | Current (WRONG) | Required (CORRECT) | Rule |
|---|---|---|---|
| Score value | `text-[20px] font-bold` | `font-sans font-extrabold text-2xl leading-tight` | §3 scale: text-2xl = 1.5rem |
| Subject name | `text-[9px] font-bold uppercase tracking-[0.5px] text-[#9ca3af]` | `font-sans font-bold text-xs uppercase tracking-wide text-brand-body` | Real label → brand-body; token not hex |
| Band label | `text-[9px] font-semibold` | `font-sans text-xs` (keep `${textClass}` for color) | §3 scale: text-xs = 0.75rem |
| Card container | `rounded-[10px] p-3` | `rounded-2xl p-4` | Config: `2xl = 1rem`; card padding = p-4 |

### Apply all four changes

```tsx
// FIND
<div
  className={`bg-white rounded-[10px] border-[1.5px] ${borderClass} p-3 text-center`}
>
  <div className={`text-[20px] font-bold ${textClass} mb-0.5`}>
    {displayPct}
  </div>
  <div className="text-[9px] font-bold uppercase tracking-[0.5px] text-[#9ca3af] mb-0.5">
    {subjectName}
  </div>
  <div
    className={`inline-block text-[9px] font-semibold px-1.5 py-0.5 rounded-[5px] ${textClass}`}
  >
    {label}
  </div>
</div>

// REPLACE WITH
<div
  className={`bg-white rounded-2xl border-[1.5px] ${borderClass} p-4 text-center`}
>
  <div className={`font-sans font-extrabold text-2xl leading-tight ${textClass}`}>
    {displayPct}
  </div>
  <div className="font-sans font-bold text-xs uppercase tracking-wide text-brand-body mt-1">
    {subjectName}
  </div>
  <div className={`font-sans text-xs mt-0.5 ${textClass}`}>
    {label}
  </div>
</div>
```

---

## Fix 8 — `NextStepCard.tsx`: Font sizes, border, padding, radius

**File:** `frontend/apps/student/src/pages/dashboard/NextStepCard.tsx`

### Typography reference for this component

| Element | Current (WRONG) | Required (CORRECT) |
|---|---|---|
| Card container border | `border-[0.5px] border-[#e5e7eb] rounded-[10px] p-[10px_14px]` | `border border-role-student-border rounded-2xl px-4 py-3` |
| Card title | `text-[11px] font-semibold text-brand-ink` | `font-sans font-semibold text-sm text-brand-ink` |
| Card subtitle | `text-[9px] text-brand-muted` | `font-sans text-xs text-brand-muted mt-0.5` |
| Action button | `text-[10px] font-bold text-brand-primary` | `font-sans font-bold text-xs text-brand-primary` |

### Apply all changes

```tsx
// FIND
<div className="bg-white border-[0.5px] border-[#e5e7eb] rounded-[10px] p-[10px_14px] flex items-center justify-between">
  <div className="flex items-center gap-[10px]">
    <span
      className="text-[14px] w-[18px] text-center"
      role="img"
      aria-label={type}
    >
      {emoji}
    </span>
    <div>
      <div className="text-[11px] font-semibold text-brand-ink">
        {title}
      </div>
      <div className="text-[9px] text-brand-muted">{subtitle}</div>
    </div>
  </div>
  <button
    onClick={onAction}
    className="text-[10px] font-bold text-brand-primary whitespace-nowrap hover:underline min-h-[44px] flex items-center focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
  >
    {actionLabel}
  </button>
</div>

// REPLACE WITH
<div className="bg-white border border-role-student-border rounded-2xl px-4 py-3 flex items-center justify-between">
  <div className="flex items-center gap-3">
    <span
      className="text-sm w-5 text-center flex-shrink-0"
      role="img"
      aria-label={type}
    >
      {emoji}
    </span>
    <div>
      <div className="font-sans font-semibold text-sm text-brand-ink">
        {title}
      </div>
      <div className="font-sans text-xs text-brand-muted mt-0.5">{subtitle}</div>
    </div>
  </div>
  <button
    onClick={onAction}
    className="font-sans font-bold text-xs text-brand-primary whitespace-nowrap hover:underline min-h-[44px] flex items-center ml-4 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
  >
    {actionLabel}
  </button>
</div>
```

---

## Fix 9 — `ClassCard.tsx`: Font sizes, font family, teacher name color

**File:** `frontend/apps/student/src/components/ClassCard.tsx`

### Typography reference for this component

| Element | Current (WRONG) | Required (CORRECT) | Rule |
|---|---|---|---|
| Class name | `text-[11px] font-semibold font-display text-brand-ink` | `font-sans font-semibold text-base text-brand-ink` | Card titles = font-sans text-base (NOT Fraunces) |
| Teacher + grade meta | `text-[9px] text-brand-muted mb-2` | `font-sans text-xs text-brand-body mb-3` | Real content → brand-body |
| Footer link wrapper | `text-[10px] font-semibold` | `font-sans font-semibold text-xs` | §3 scale |
| Card container | `rounded-[10px]` | `rounded-2xl` | Config: 2xl = 1rem |

### Apply changes — four find-and-replace operations

**Change 1 — class name heading:**

```tsx
// FIND
<span className="text-[11px] font-semibold font-display text-brand-ink truncate">

// REPLACE WITH
<span className="font-sans font-semibold text-base text-brand-ink truncate">
```

**Change 2 — teacher/grade meta line:**

```tsx
// FIND
<div className="text-[9px] text-brand-muted mb-2">

// REPLACE WITH
<div className="font-sans text-xs text-brand-body mb-3">
```

**Change 3 — CTA footer wrapper:**

```tsx
// FIND
<div
  className={`text-[10px] font-semibold ${
    isLocked ? "text-brand-gold" : "text-brand-primary"
  }`}
>

// REPLACE WITH
<div
  className={`font-sans font-semibold text-xs ${
    isLocked ? "text-brand-gold" : "text-brand-primary"
  }`}
>
```

**Change 4 — card container radius:**

```tsx
// FIND
className={`w-full text-left bg-white rounded-[10px] border border-brand-border p-3 ...

// REPLACE WITH
className={`w-full text-left bg-white rounded-2xl border border-role-student-border p-4 ...
```

---

## Fix 10 — `AccountSection.tsx`: Fix the wrong API endpoint

**File:** `frontend/apps/student/src/components/settings/AccountSection.tsx`

`GET /api/v1/users/me` does not exist in the live API.
The correct endpoint is `GET /api/v1/schools/{school_id}/users/me`.

**Step 1 — Add import for `useStudentInfo`:**

```tsx
// Add at the top, with other imports
import { useStudentInfo } from "../../hooks/useStudentInfo";
```

**Step 2 — Call `useStudentInfo` inside `AccountSection()`:**

Add immediately after `const queryClient = useQueryClient();`:

```tsx
const { data: studentInfo } = useStudentInfo();
const schoolId = studentInfo?.school_id;
```

**Step 3 — Fix the query:**

```tsx
// FIND
const { data: user } = useQuery<User>({
  queryKey: ["student", "settings", "user"],
  queryFn: async () => {
    const response = await apiClient.get<User>("/api/v1/users/me");
    return response.data;
  },
});

// REPLACE WITH
const { data: user } = useQuery<User>({
  queryKey: ["student", "settings", "user", schoolId],
  queryFn: async () => {
    if (!schoolId) throw new Error("School ID not available");
    const response = await apiClient.get<User>(
      `/api/v1/schools/${schoolId}/users/me`
    );
    return response.data;
  },
  enabled: !!schoolId,
});
```

---

## Fix 11 — Four pages: Pass required identity props to `StudentLayout`

`StudentLayout` requires `studentName`, `gradeName`, `curriculumName` (typed as `string`,
no defaults). These pages currently pass none of them — TypeScript errors and empty sidebars.

**Apply identically to all four files listed below.**

### Files

- `frontend/apps/student/src/pages/my-progress/MyProgress.tsx`
- `frontend/apps/student/src/pages/study-plans/StudyPlans.tsx`
- `frontend/apps/student/src/pages/assessments/Assessments.tsx`
- `frontend/apps/student/src/pages/settings/StudentSettings.tsx`

### Step A — Add imports to each file

```tsx
import { useStudentInfo } from "../../hooks/useStudentInfo";
import { useMyClasses, type StudentClassResponse } from "../../hooks/useMyClasses";
```

For `StudentSettings.tsx`, the hooks live one level deeper — use:
```tsx
import { useStudentInfo } from "../../hooks/useStudentInfo";
import { useMyClasses, type StudentClassResponse } from "../../hooks/useMyClasses";
```
(Path is the same relative to `src/` — verify against file location before writing.)

### Step B — Call hooks inside each page component

```tsx
const { data: studentInfo } = useStudentInfo();
const { data: classesData } = useMyClasses();

const firstName      = studentInfo?.first_name   ?? "";
const lastName       = studentInfo?.last_name    ?? "";
const studentName    = [firstName, lastName].filter(Boolean).join(" ") || "Student";
const gradeName      = studentInfo?.grade_name      ?? "";
const curriculumName = studentInfo?.curriculum_name ?? "";

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

### Step C — Pass props to `StudentLayout` in each file

**`MyProgress.tsx`:**

```tsx
// FIND
<StudentLayout activeNav="progress" onLogout={logout}>

// REPLACE WITH
<StudentLayout
  activeNav="progress"
  studentName={studentName}
  gradeName={gradeName}
  curriculumName={curriculumName}
  classes={sidebarClasses}
  onLogout={logout}
>
```

**`StudyPlans.tsx`:**

```tsx
// FIND
<StudentLayout activeNav="study" onLogout={logout}>
// NOTE: "study" is not a valid StudentNavItem — correct value is "study-plans"

// REPLACE WITH
<StudentLayout
  activeNav="study-plans"
  studentName={studentName}
  gradeName={gradeName}
  curriculumName={curriculumName}
  classes={sidebarClasses}
  onLogout={logout}
>
```

**`Assessments.tsx`:**

```tsx
// FIND
<StudentLayout activeNav="assessments" onLogout={logout}>

// REPLACE WITH
<StudentLayout
  activeNav="assessments"
  studentName={studentName}
  gradeName={gradeName}
  curriculumName={curriculumName}
  classes={sidebarClasses}
  onLogout={logout}
>
```

**`StudentSettings.tsx`:**

```tsx
// FIND
<StudentLayout onLogout={logout}>
// NOTE: no activeNav — settings is reached via avatar, not the nav

// REPLACE WITH
<StudentLayout
  activeNav="home"
  studentName={studentName}
  gradeName={gradeName}
  curriculumName={curriculumName}
  classes={sidebarClasses}
  onLogout={logout}
>
```

---

## Fix 12 — `student-app.spec.ts`: Update stale comment

**File:** `frontend/apps/student/src/tests/student-app.spec.ts`

```typescript
// FIND
/**
 * Smoke test for Student app - verifies correct app is loaded
 * Design: StudentLayout with top + bottom nav, green primary buttons, no sidebar
 */

// REPLACE WITH
/**
 * Smoke test for Student app - verifies correct app is loaded
 * Design: StudentLayout v2.1 — left sidebar, green primary buttons, no bottom nav
 * Reference: docs/design/DESIGN_SYSTEM.md §5.4
 */
```

---

## Files to modify / delete

```
frontend/packages/ui/tailwind.config.js               MODIFY  (Fix 1)
frontend/packages/ui/src/layouts/StudentLayout.tsx     MODIFY  (Fix 2)
frontend/packages/ui/src/components/nav/NavItem.tsx    MODIFY  (Fix 3)
frontend/packages/ui/src/layouts/StudentShellLayout.tsx  DELETE  (Fix 4)
frontend/packages/ui/src/index.ts                      MODIFY  (Fix 4 — remove export)
frontend/packages/ui/src/layouts/index.ts              MODIFY  (Fix 4 — remove export if present)

frontend/apps/student/src/hooks/useSubjectScores.ts    MODIFY  (Fix 5)
frontend/apps/student/src/pages/dashboard/StudentDashboard.tsx   MODIFY  (Fix 6)
frontend/apps/student/src/pages/dashboard/SubjectScoreCard.tsx   MODIFY  (Fix 7)
frontend/apps/student/src/pages/dashboard/NextStepCard.tsx       MODIFY  (Fix 8)
frontend/apps/student/src/components/ClassCard.tsx               MODIFY  (Fix 9)
frontend/apps/student/src/components/settings/AccountSection.tsx MODIFY  (Fix 10)

frontend/apps/student/src/pages/my-progress/MyProgress.tsx       MODIFY  (Fix 11)
frontend/apps/student/src/pages/study-plans/StudyPlans.tsx        MODIFY  (Fix 11)
frontend/apps/student/src/pages/assessments/Assessments.tsx       MODIFY  (Fix 11)
frontend/apps/student/src/pages/settings/StudentSettings.tsx      MODIFY  (Fix 11)

frontend/apps/student/src/tests/student-app.spec.ts    MODIFY  (Fix 12)
```

---

## Verification checklist

Run through every item before pushing. Each item is directly observable.

### TypeScript
- [ ] `tsc --noEmit` passes with zero errors in `apps/student`
- [ ] `tsc --noEmit` passes with zero errors in `packages/ui`
- [ ] No TypeScript error on `StudentLayout` props in `MyProgress`, `StudyPlans`,
      `Assessments`, `StudentSettings`
- [ ] `activeNav="study"` is gone — `StudyPlans.tsx` uses `activeNav="study-plans"`

### Config tokens (open `tailwind.config.js` and verify)
- [ ] `role-student.nav-active: '#f0fdf4'` exists
- [ ] `role-student.nav-locked-hover: '#fffbeb'` exists
- [ ] `role-teacher.nav-active: '#fffbeb'` exists

### Zero hardcoded hex values in components
Open browser devtools → inspect each element → confirm no inline style or `[#......]`
class resolves to a hex literal in these files:
- [ ] `StudentLayout.tsx` — no `bg-[#...]` or `text-[#...]`
- [ ] `NavItem.tsx` — no `bg-[#...]`
- [ ] `SubjectScoreCard.tsx` — no `text-[#9ca3af]`
- [ ] `NextStepCard.tsx` — no `border-[#e5e7eb]`
- [ ] `ClassCard.tsx` — no `border-[#...]` or `rounded-[10px]`

### Font sizes — open devtools, inspect computed styles
- [ ] Subject score value: computed font-size = 24px (`text-2xl`)
- [ ] Subject name label: computed font-size = 12px (`text-xs`)
- [ ] Class card name: computed font-size = 16px (`text-base`)
- [ ] Teacher meta line: computed font-size = 12px (`text-xs`)
- [ ] Next step card title: computed font-size = 14px (`text-sm`)
- [ ] Next step subtitle: computed font-size = 12px (`text-xs`)

### Font family — no Fraunces on card content
- [ ] Class card class name uses Nunito (font-sans), not Fraunces (font-display)

### Colors — inspect computed styles
- [ ] Section headings ("YOUR SUBJECTS", "MY CLASSES", "WHAT'S WAITING FOR YOU"):
      computed color = `#4a5240` (brand-body), NOT `#9ca3af` (brand-muted)
- [ ] Subject name in score card: computed color = `#4a5240` (brand-body)
- [ ] Teacher name in class card: computed color = `#4a5240` (brand-body)
- [ ] "Not assessed" label in score card: color comes from `textClass` (getMasteryStyle) = `text-brand-muted` ✅ correct

### API calls — check network tab
- [ ] `GET /api/v1/students/me/gap-map?subject_id={uuid}` fires once per subject
- [ ] `GET /api/v1/students/me/study-plans` fires on dashboard load
- [ ] `GET /api/v1/schools/{school_id}/users/me` fires on Settings page
- [ ] `GET /api/v1/users/me` NEVER appears in network tab (endpoint does not exist)

### Navigation
- [ ] Clicking "Study plans" in sidebar navigates to `/student/study-plans`
      AND the "Study plans" nav item shows active (green tint + dot)
- [ ] Navigating to `/student/my-progress` shows correct sidebar with profile card
- [ ] Profile card shows real student name on ALL pages (not empty)

### Deleted file
- [ ] `frontend/packages/ui/src/layouts/StudentShellLayout.tsx` does not exist
- [ ] No import of `StudentShellLayout` anywhere in the codebase

---

## Acceptance tests — named test functions

Add to `frontend/apps/student/src/hooks/__tests__/useSubjectScores.test.ts`:

`test_use_subject_gap_map_query_fn_returns_data_not_axios_response`
Mock `apiClient.get` to resolve with `{ data: { scores: [{ mastery_score: 0.8 }] } }`.
Call `queryFn()` from the `useSubjectGapMap` `useQuery` config.
Assert: resolved value has a `scores` property at the top level — NOT at `value.data.scores`.
Assert: `aggregateSubjectMastery(resolvedValue)` returns `0.8`.

Add to `frontend/packages/ui/src/layouts/__tests__/StudentLayout.test.tsx`:

`test_no_bottom_nav_rendered`
Render `StudentLayout` with required props.
Assert: no element matching `nav[aria-label="Student navigation"]` exists in the DOM.
(BottomNav has `aria-label="Student navigation"` — if it renders, this test fails.)

`test_active_nav_uses_token_class_not_hardcoded_hex`
Render with `activeNav="home"`.
Find the Home link element.
Assert: it has class `bg-role-student-nav-active`.
Assert: it does NOT have class `bg-[#f0fdf4]`.

---

## Branch and commit

```
Branch: M0-7-T3-hotfix/fix-all-remaining-issues

Commit:
fix(student): complete remaining hotfix — tokens, fonts, data, identity props

Config:
- tailwind.config.js: add role-student.nav-active, role-student.nav-locked-hover,
  role-teacher.nav-active tokens — eliminates 3 hardcoded hex values from components

Layout:
- StudentLayout.tsx: bg-[#f0fdf4] → bg-role-student-nav-active,
  hover:bg-[#fffbeb] → hover:bg-role-student-nav-locked-hover
- NavItem.tsx: bg-[#fffbeb] → bg-role-teacher-nav-active
- StudentShellLayout.tsx: DELETE — dead code, no longer used by any page

Data:
- useSubjectScores.ts: queryFn now returns response.data (was returning AxiosResponse —
  caused all subject cards to show "–")
- StudentDashboard.tsx: wire useStudentDashboard — remove hardcoded empty arrays
- AccountSection.tsx: fix endpoint /users/me → /schools/{schoolId}/users/me

Typography (page content — rem scale, no px):
- SubjectScoreCard.tsx: text-[20px]→text-2xl, text-[9px]→text-xs,
  text-[#9ca3af]→text-brand-body, p-3 rounded-[10px]→p-4 rounded-2xl
- NextStepCard.tsx: all text-[Npx] → rem tokens, border-[#e5e7eb]→border-role-student-border,
  rounded-[10px]→rounded-2xl
- ClassCard.tsx: text-[11px] font-display→text-base font-sans (card titles = Nunito),
  text-[9px] text-brand-muted→text-xs text-brand-body (teacher name = real content)

Colors:
- StudentDashboard.tsx: section headings text-brand-muted→text-brand-body (×3)

Identity props:
- MyProgress, StudyPlans, Assessments, StudentSettings: add useStudentInfo + useMyClasses,
  pass studentName/gradeName/curriculumName/classes to StudentLayout
- StudyPlans.tsx: fix activeNav="study"→"study-plans" (was invalid StudentNavItem)
```
