# Kaihle Teacher App — Task Board
> Generated from full codebase review. Covers App.tsx, Sidebar.tsx, all pages, components, hooks, and tests.

---

## 🔴 P1 — Critical Bugs (Breaks Core Functionality)

---

### T-001 · Fix useRoutes + Exact Route Bug in All Shells
**Files:** `App.tsx`, `TeacherAssessmentShell`, `TeacherContentShell`

**Problem:**  
All shells use `useRoutes()` but are mounted on exact parent routes. React Router v6 consumes the full path on the parent match, leaving nothing for `useRoutes` to match — so it always falls through to `*` → redirect to dashboard.

**Fix:**
1. Change all class-level routes in `App.tsx` to use a single wildcard:
```tsx
// Replace 3 separate exact routes with one wildcard
<Route path="/teacher/classes/:classId/*" element={<TeacherContentShell />} />
```

2. Update `useRoutes` paths inside `TeacherContentShell` to short relative paths:
```tsx
{ path: "gap-map",            element: <GapMapPage /> },
{ path: "assessments",        element: <AssessmentListPage /> },
{ path: "study-plan",         element: <StudyPlanPage /> },
{ path: "lesson-plans",       element: <LessonPlansPage /> },
{ path: "explanation-review", element: <ExplanationReviewPage /> },
{ path: "*", element: <Navigate to="/teacher/dashboard" replace /> },
```

3. Collapse `TeacherAssessmentShell` — `/teacher/assessments/new` is a single route, no shell needed. Render `NewAssessmentPage` directly in the route element.

**Acceptance:** Clicking Gap Map, Assessments, Lesson Plans from a ClassCard navigates to the correct page without redirecting to dashboard.

---

### T-002 · Wire Missing Routes Back Into App.tsx
**Files:** `App.tsx`

**Problem:**  
These page files exist and are fully built but have no route — they are completely unreachable:

| Page File | Missing Route |
|---|---|
| `GapMapPage` | `/teacher/classes/:classId/gap-map` |
| `LessonPlansPage` | `/teacher/classes/:classId/lesson-plans` |
| `StudentProfilePage` | `/teacher/students/:studentId/profile` |
| `MyStudentsPage` | `/teacher/students` |

**Fix:**  
Add all missing routes into `App.tsx` under the appropriate shell. Follow the wildcard pattern from T-001.

**Acceptance:** All four pages are reachable by URL and via in-app links.

---

### T-003 · Fix useTeacherDashboard — studentCount and avgMastery Always Zero
**Files:** `hooks/useTeacherDashboard.ts`

**Problem:**  
Dashboard data is hardcoded — every class shows "0 students" and "Not assessed":
```ts
const classes = (classesRes.data || []).map((c: any) => ({
  studentCount: 0,     // ← hardcoded
  avgMastery: null,    // ← hardcoded
  lessonPlanStatus: "none" as const,
}));
```
The analytics response is fetched but thrown away. This makes every ClassCard on the dashboard appear broken.

**Fix:**  
Either:
- Map `analyticsRes.data` into `studentCount` and `avgMastery` per class if the API returns this data
- Or add separate enrollment count and mastery queries per class (parallel, not sequential)
- Fetch `studentCount` from `/api/v1/classes/:classId/enrollments` length if no aggregate endpoint exists

**Acceptance:** ClassCards on the dashboard show real student counts and mastery scores.

---

### T-004 · Enable "View Results" Button in AssessmentListPage
**Files:** `pages/assessments/AssessmentListPage.tsx`

**Problem:**  
"View Results" is permanently disabled with `title="Results view coming soon"`. But `AssessmentResultsPage` is fully built and tested.

```tsx
// Current — disabled for no reason
<button type="button" disabled title="Results view coming soon">
  View Results
</button>
```

**Fix:**
```tsx
<Link to={`/teacher/assessments/${assessment.id}/results`}>
  <button className="...">View Results</button>
</Link>
```

**Acceptance:** Clicking "View Results" on an ACTIVE or CLOSED assessment navigates to `AssessmentResultsPage`.

---

### T-005 · Remove debugger Statement From TeacherContentShell
**Files:** `App.tsx` (TeacherContentShell function)

**Problem:**  
A `debugger` statement was left in `TeacherContentShell`. This freezes execution for any user with browser DevTools open.

**Fix:** Delete the line. One-line fix.

**Acceptance:** No `debugger` statements exist anywhere in production code.

---

### T-006 · Fix Dead Links in ClassCard, PendingActionBanner, ThisWeekCard, StudentGapMapTab
**Files:**  
- `pages/dashboard/ClassCard.tsx`  
- `pages/dashboard/PendingActionBanner.tsx`  
- `pages/dashboard/ThisWeekCard.tsx`  
- `components/students/StudentGapMapTab.tsx`

**Problem:**  
All these components link to routes that are either broken (T-001) or missing (T-002). In `ClassCard`, only Gap Map and Assessments are linked — Lesson Plans and Study Plan are missing entirely.

**Fix:**  
After T-001 and T-002 are resolved, update all links. For `ClassCard`, add the two missing quick links:
```tsx
<Link to={`/teacher/classes/${classId}/gap-map`}>Gap Map</Link>
<Link to={`/teacher/classes/${classId}/assessments`}>Assessments</Link>
<Link to={`/teacher/classes/${classId}/study-plan`}>Study Plan</Link>
<Link to={`/teacher/classes/${classId}/lesson-plans`}>Lesson Plans</Link>
<Link to={`/teacher/classes/${classId}`}>View →</Link>
```

**Acceptance:** Every link in every card navigates to its correct destination.

---

## 🟠 P2 — Architecture & Navigation Restructure

---

### T-007 · Restructure Sidebar Nav to Match New Global Structure
**Files:** `components/Sidebar.tsx`

**Problem:**  
Current sidebar is class-context-aware (Gap Map, Assessments etc. are class-level items). Per agreed design, the sidebar is always global — context-specific links live on cards, not the sidebar.

**New Teacher Sidebar Structure:**
```
MY WORKSPACE
  Dashboard        → /teacher/dashboard
  Classes          → /teacher/classes
  Students         → /teacher/students
  Assessments      → /teacher/assessments

ACCOUNT
  Settings         → /teacher/settings
```

**Fix:**  
Replace `teacherSections` in `Sidebar.tsx` with the above structure. Remove all `:classId`-dependent hrefs. Remove `resolveHref` function — it is no longer needed. Remove `classId` prop from `SidebarProps`.

**Acceptance:** Teacher sidebar never shows class-specific links. All nav items resolve without params.

---

### T-008 · Build Classes List Page
**Files:** New file — `pages/classes/ClassesPage.tsx`

**Problem:**  
There is no `/teacher/classes` page. The sidebar "Classes" link has nowhere to go.

**Page requirements:**
- Lists all teacher's classes (data already available from `useTeacherDashboard`)
- Each class renders as a card following the agreed pattern:
  - Identity: Class name · Grade · Subject · Student count · Avg mastery
  - Quick links: Gap Map · Assessments · Study Plan · Lesson Plans
  - View →: navigates to `/teacher/classes/:classId`
- Empty state if teacher has no classes
- Skeleton loading state

**Acceptance:** `/teacher/classes` renders a card grid of all classes with working quick links.

---

### T-009 · Build Class Detail Page
**Files:** New file — `pages/classes/ClassDetailPage.tsx`

**Problem:**  
There is no `/teacher/classes/:classId` page. The "View →" on class cards has nowhere to go.

**Page requirements:**
- Header: Class name, Subject, Grade, student count, avg mastery pill
- Quick-access section: 4 cards linking to Gap Map, Assessments, Study Plan, Lesson Plans
- Recent students section: top 5 students by lowest mastery (at-risk first), each linking to their profile
- Recent assessments section: last 3 assessments with status badge and results link
- Breadcrumb: `← Classes`

**Acceptance:** `/teacher/classes/:classId` renders class summary with working sub-resource links.

---

### T-010 · Build Global Students List Page
**Files:** Refactor `pages/MyStudents.tsx` → `pages/students/StudentsPage.tsx`

**Problem:**  
`MyStudents.tsx` exists but requires upfront class selection via dropdown before showing any students. Per agreed architecture, the global students page should show all students across all classes by default, with an optional class filter.

**Fix:**  
Refactor `MyStudents.tsx`:
- On load: fetch all students across all teacher's classes (aggregate)
- Show all students by default in `StudentsTable`
- Add class filter chips above the table (not a blocking dropdown)
- Each student row links to `/teacher/students/:studentId/profile`
- Each student row quick links: Detail · Classes · Gap Map
- Default sort: `mastery-asc` (lowest mastery first — at-risk students visible immediately)

**Acceptance:** `/teacher/students` shows all students across all classes. Class filter is additive, not blocking.

---

### T-011 · Build Global Assessments List Page
**Files:** New file — `pages/assessments/AllAssessmentsPage.tsx`

**Problem:**  
There is no `/teacher/assessments` page listing all assessments across all classes. `AssessmentListPage.tsx` only works per-class.

**Page requirements:**
- Lists all assessments across all teacher's classes
- Each assessment card shows: title, class name, type badge, status badge, deadline, question count
- Quick links per card: Results (if ACTIVE/CLOSED), View class
- Filter chips: All · Active · Draft · Closed
- "New Assessment" button in top right (existing pattern)
- Empty state

**Acceptance:** `/teacher/assessments` shows all assessments across classes with working filters and links.

---

### T-012 · Fix Back Navigation Across All Pages
**Files:**  
- `pages/gap-map/GapMapPage.tsx`  
- `pages/assessments/AssessmentResultsPage.tsx`  
- `pages/assessments/StudentResultDetailPage.tsx`  
- `pages/MyStudents.tsx`  
- `components/students/StudentProfileHeader.tsx`

**Problem:**  
Every page hardcodes "← Back to dashboard" regardless of where the user came from. This loses navigation context.

**Correct back links:**

| Page | Current | Should Be |
|---|---|---|
| GapMapPage | `/teacher/dashboard` | `/teacher/classes/:classId` |
| AssessmentResultsPage | `/teacher/dashboard` | `/teacher/classes/:classId/assessments` |
| StudentResultDetailPage | `/teacher/assessments/:id/results` | Correct ✓ |
| MyStudentsPage | `/teacher/dashboard` | `/teacher/students` |
| StudentProfileHeader | `/teacher/dashboard` | `/teacher/students` |

**Fix:** Use `useParams` to build context-aware back links. For `GapMapPage`, `classId` is already available from `useParams`.

**Acceptance:** Back navigation on every page returns the user to the logical parent, not always the dashboard.

---

## 🟡 P3 — Code Quality & Performance

---

### T-013 · Eliminate Shell Duplication — Extract useTeacherShellProps Hook
**Files:** `App.tsx`

**Problem:**  
`greeting()` function and the `topNavAction` button are copy-pasted identically across `TeacherShell`, `TeacherAssessmentShell`, and `TeacherContentShell`. Any change must be made in 3 places.

**Fix:**
```tsx
function useTeacherShellProps() {
  const { user, logout } = useAuth();

  const greeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  };

  const teacherName = user?.email?.split("@")[0] || "Teacher";

  const topNavAction = (
    <Link to="/teacher/assessments/new">
      <Button variant="primary" size="sm" className="gap-1 bg-brand-gold hover:bg-brand-gold-dark">
        <Plus className="w-4 h-4" aria-hidden="true" />
        Assessment
      </Button>
    </Link>
  );

  return {
    pageTitle: `${greeting()}, ${teacherName}`,
    onLogout: logout,
    topNavAction,
  };
}
```

**Acceptance:** `greeting()` and `topNavAction` exist in exactly one place.

---

### T-014 · Fix N+1 API Problem in useStudentProfile
**Files:** `hooks/useStudentProfile.ts`

**Problem:**  
To find a student's class, the hook fetches all school classes then fires up to 10 parallel enrollment checks:
```ts
const enrollmentChecks = await Promise.all(
  allClasses.slice(0, 10).map(async (cls) => {
    const res = await apiClient.get(`/api/v1/classes/${cls.id}/enrollments`)
    ...
  })
)
```
This is 1 + N API calls on every student profile load.

**Fix (frontend):**  
Cap parallel calls at 5, add proper error handling. Cache results aggressively (`staleTime: 30 * 60 * 1000`).

**Fix (backend — flag for backend team):**  
Request a `/api/v1/students/:studentId/classes` endpoint that returns the student's enrolled classes directly. This eliminates the N+1 entirely.

**Acceptance:** Student profile loads with ≤ 2 API calls.

---

### T-015 · Fix min-h on tr Elements in AssessmentListPage
**Files:** `pages/assessments/AssessmentListPage.tsx`

**Problem:**  
```tsx
<tr className="hover:bg-gray-50 transition-colors min-h-[56px]">
```
`min-h` does not work on `<tr>` elements in most browsers. This is a no-op.

**Fix:** Remove `min-h-[56px]`. Row height is already controlled by `py-4` padding on `<td>` elements.

**Acceptance:** No `min-h` applied to any `<tr>` element.

---

### T-016 · Replace Inline Styles With Tailwind Arbitrary Classes in GapMapPage
**Files:** `pages/gap-map/GapMapPage.tsx`

**Problem:**  
```tsx
<div style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}>
```
Inline styles bypass the design system.

**Fix:**
```tsx
<div className="[writing-mode:vertical-rl] rotate-180">
```

**Acceptance:** No inline style attributes in `GapMapPage`.

---

### T-017 · Fix Color Token Inconsistency in Results Pages
**Files:**  
- `pages/assessments/AssessmentResultsPage.tsx`  
- `pages/assessments/StudentResultDetailPage.tsx`  
- `components/results/ResultsKPIRow.tsx`

**Problem:**  
These files use raw Tailwind classes (`border-gray-100`, `shadow-sm`) instead of design tokens (`border-brand-border`, `shadow-card`). When the teacher role theme changes, these won't update.

**Fix:**  
Audit all three files and replace:
- `border-gray-100` → `border-brand-border`
- `shadow-sm` → `shadow-card`
- `bg-gray-50` → `bg-brand-bg`
- `text-gray-400` → `text-brand-muted`

**Acceptance:** No raw `gray-*` color classes in results page files.

---

### T-018 · Make StudentProfilePage Tabs URL-Driven
**Files:** `pages/StudentProfilePage.tsx`

**Problem:**  
Active tab is stored in component state — tab state is lost on refresh and can't be linked or bookmarked:
```tsx
const [activeTab, setActiveTab] = useState<TabId>("gap-map");
```

**Fix:**
```tsx
const [searchParams, setSearchParams] = useSearchParams();
const activeTab = (searchParams.get("tab") as TabId) ?? "gap-map";

const handleTabChange = (tab: TabId) => {
  setSearchParams({ tab });
};
```

URLs become:
```
/teacher/students/:studentId/profile?tab=gap-map
/teacher/students/:studentId/profile?tab=learning-profile
/teacher/students/:studentId/profile?tab=assessments
```

**Acceptance:** Refreshing the page or sharing the URL preserves the active tab.

---

## 🔵 P4 — Product & UX Improvements (Nancy + Pixel)

---

### T-019 · Redesign ClassCard With 4 Quick Links and View Button
**Files:** `pages/dashboard/ClassCard.tsx`

**Current:** 2 quick links, no "View →" to class detail.

**New card structure:**
```
┌──────────────────────────────────────────────┐
│  ● Grade 10 Math                [Grade 10]   │
│  28 students  ·  72%  Strong                 │
│  ─────────────────────────────────────────── │
│  Gap Map · Assessments · Study Plan          │
│  Lesson Plans                      [View →]  │
└──────────────────────────────────────────────┘
```

**Token requirements (Pixel):**
- Quick links: `text-sm font-medium text-brand-muted hover:text-brand-primary transition-colors`
- Divider: `border-t border-brand-border pt-3`
- View button: `text-sm font-semibold text-brand-gold hover:text-brand-gold-dark`
- Card hover: existing `hover:-translate-y-0.5 hover:shadow-card-hover` — keep

**Acceptance:** All 4 quick links visible on every class card. View → navigates to class detail page.

---

### T-020 · Show All Pending Actions on Dashboard, Not Just First
**Files:** `pages/dashboard/TeacherDashboard.tsx`, `pages/dashboard/PendingActionBanner.tsx`

**Problem:**  
```tsx
// Only shows the first action — rest are silently ignored
<PendingActionBanner action={data.pendingActions[0]} />
```

**Fix:**  
Render all pending actions (capped at 3 to avoid overwhelming the dashboard):
```tsx
{data.pendingActions.slice(0, 3).map((action, i) => (
  <PendingActionBanner key={i} action={action} />
))}
```

Also fix the action generation logic in `useTeacherDashboard` — it currently generates actions based on `avgMastery: null` which is always true (T-003 dependency).

**Acceptance:** Up to 3 pending action banners shown. Actions reflect real data.

---

### T-021 · Change Default Student Table Sort to Mastery Ascending
**Files:** `components/students/StudentsTable.tsx`

**Problem:**  
```tsx
const [sortBy, setSortBy] = useState<...>("name"); // alphabetical by default
```
Teachers want to see struggling students first, not alphabetical order.

**Fix:**
```tsx
const [sortBy, setSortBy] = useState<...>("mastery-asc");
```

**Acceptance:** Students table defaults to lowest mastery first. Sort label still correctly defaults to "Mastery ↑" in the dropdown.

---

### T-022 · Add Post-Publish Success Banner on AssessmentListPage
**Files:** `pages/assessments/AssessmentListPage.tsx`, `pages/assessments/steps/Step5Publish.tsx`

**Problem:**  
After publishing, the teacher is redirected to the assessment list with no confirmation. The newly published assessment is not highlighted.

**Fix:**  
Pass a `?published=true` query param from `Step5Publish` on redirect:
```tsx
navigate(`/teacher/classes/${targetClassId}/assessments?published=true`);
```

In `AssessmentListPage`, read the param and show a dismissible banner:
```tsx
const [searchParams] = useSearchParams();
const justPublished = searchParams.get("published") === "true";

{justPublished && (
  <div className="bg-brand-green-light border border-brand-green rounded-xl p-4 flex items-center justify-between mb-4">
    <span className="text-sm font-medium text-brand-ink">
      ✓ Assessment published — students can now complete it.
    </span>
    <button onClick={dismissBanner}>Dismiss</button>
  </div>
)}
```

**Acceptance:** A success banner appears on the assessment list immediately after publishing. Banner is dismissible.

---

### T-023 · Add Plain-Language Descriptor to Gap Map Entry Points
**Files:**  
- `pages/dashboard/ClassCard.tsx`  
- `pages/classes/ClassDetailPage.tsx` (T-009)

**Problem:**  
"Gap Map" is internal product language. New teachers don't know what it means from the label alone.

**Fix:**  
Add a tooltip or sub-label on first exposure:
```tsx
// On ClassCard quick link
<Link to={...} title="See where each student is struggling by subtopic">
  Gap Map
</Link>
```

On the Class Detail page, add a descriptor under the Gap Map card:
```
Gap Map
See exactly where each student is struggling, subtopic by subtopic
```

**Acceptance:** "Gap Map" quick link has a `title` attribute. Class detail Gap Map card has a one-line descriptor.

---

### T-024 · Add Breadcrumb to GapMapPage, AssessmentResultsPage, ExplanationReviewPage
**Files:**  
- `pages/gap-map/GapMapPage.tsx`  
- `pages/assessments/AssessmentResultsPage.tsx`  
- `pages/classes/ExplanationReviewPage.tsx`

**Problem:**  
These pages show only a back arrow with no context about where they are in the hierarchy.

**Fix:**  
Add a two-level breadcrumb using the class name (already available):
```tsx
// GapMapPage — currentClass is already fetched
<nav className="flex items-center gap-2 text-sm text-brand-muted">
  <Link to="/teacher/classes" className="hover:text-brand-ink">Classes</Link>
  <span>/</span>
  <Link to={`/teacher/classes/${classId}`} className="hover:text-brand-ink">
    {currentClass?.name ?? "Class"}
  </Link>
  <span>/</span>
  <span className="text-brand-ink font-medium">Gap Map</span>
</nav>
```

**Acceptance:** All three pages show a 3-level breadcrumb. Each breadcrumb segment is a working link.

---

## 🔧 P5 — Testing

---

### T-025 · Add Unit Tests for ClassCard and New Card Components
**Files:** New test file — `src/tests/class-card.test.tsx`

Cover:
- Renders class name, subject, student count, mastery correctly
- All 4 quick links render with correct hrefs
- View → link renders with correct href
- Skeleton renders without crashing
- Mastery color classes apply correctly per band

---

### T-026 · Add E2E Smoke Tests for New Routes
**Files:** New test file — `src/tests/navigation.spec.ts`

Cover:
- `/teacher/classes` renders classes list
- `/teacher/classes/:classId` renders class detail
- `/teacher/students` renders students list
- `/teacher/students/:studentId/profile` renders student profile
- Clicking Gap Map quick link on ClassCard navigates to correct URL
- Back navigation from GapMapPage goes to Class detail, not dashboard

---

## Dependency Map

```
T-001 (Fix useRoutes)
  └── T-002 (Wire missing routes)
        └── T-006 (Fix dead links)
              └── T-019 (Redesign ClassCard)

T-003 (Fix dashboard data)
  └── T-020 (Show all pending actions)

T-007 (Restructure sidebar)
  └── T-008 (Classes list page)
        └── T-009 (Class detail page)
              └── T-024 (Breadcrumbs)

T-010 (Students list page)
  └── T-021 (Default sort)

T-004 (Enable View Results)
  └── T-022 (Post-publish banner)
```

---

## Quick Wins (Do These First)
These are low-effort, high-impact and have no dependencies:

| Task | Effort | Impact |
|---|---|---|
| T-005 Remove debugger | 1 min | Stops app freezing in DevTools |
| T-004 Enable View Results | 5 min | Unlocks a fully built feature |
| T-021 Default sort mastery-asc | 1 min | Better teacher experience |
| T-015 Fix min-h on tr | 2 min | Code correctness |
| T-016 Replace inline styles | 5 min | Design system compliance |
