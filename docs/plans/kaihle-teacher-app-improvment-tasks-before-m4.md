# Kaihle Teacher App — Task Board v3
> Reviewed by Kramer (engineering) · Pixel (design system) · Vidhya (teacher UX).
> All code samples PR-reviewed. All sections cross-reviewed across disciplines.
> Kaihle is curriculum-agnostic. Topics and subtopics drive all AI features — not any specific framework.

---

## Architecture Decisions (locked)

**Sidebar — teacher:**
```
MY WORKSPACE
  Home            → /teacher/dashboard       icon: LayoutDashboard
  Classes         → /teacher/classes         icon: Building2
  Students        → /teacher/students        icon: Users
  Assessments     → /teacher/assessments     icon: ClipboardList

TOOLS
  Lesson Plans    → /teacher/lesson-plans    icon: BookOpen
  Content Review  → /teacher/content-review  icon: FileText

ACCOUNT
  Settings        → /teacher/settings        icon: Settings
```

**Not in sidebar:** Study Plans (assigned from Gap Map cell, not browsed). Gap Map (lives on class cards). New Assessment button (on Assessments pages only).

**Global topbar:** Greeting left, nothing right. No persistent action button.

**Navigation pattern:** Sidebar always fixed. Context-specific links live on cards, not sidebar.

**API strategy (minimal calls):**
- Dashboard: `GET /schools/{id}/classes` + `GET /classes/{id}/summary` ×N parallel
- Students list: `GET /teachers/me/students` — one call
- Gap Map: `GET /classes/{id}/gap-map?subject_id=` — subject_id already on class object
- Content Review: `GET /teacher/classes/{id}/explanation-review?status=pending` ×N parallel
- Grades/Subjects: `GET /grades` + `GET /subjects` — once on app init, `staleTime: Infinity`
- Analytics endpoint: **stub returning zeros — do not use**
- Lesson Plans endpoint: **M4 stub — show placeholder UI, never throw**

**Naming note (Content Review):**
UI label: "Content Review" · Frontend route: `/teacher/content-review` · Backend API: `/api/v1/teacher/classes/{id}/explanation-review`
All three are intentionally different. Do not rename any of them.

---

## 🔴 P1 — Critical Routing Fixes

---

### T-001 · Fix useRoutes Exact Route Bug + Wire All Missing Routes
**Files:** `App.tsx`

**Problem:**
All shells use `useRoutes()` mounted on exact parent routes. React Router v6 consumes the full path on the parent match, leaving nothing for `useRoutes` — always falls to `*` → dashboard. Additionally `GapMapPage`, `LessonPlansPage`, `StudentProfilePage`, `MyStudentsPage` have no routes.

**Fix — one pass:**

1. Delete `TeacherAssessmentShell` entirely.

2. Create `NewAssessmentApp` wrapper (same pattern as `TeacherSettingsApp`):
```tsx
function NewAssessmentApp() {
  const { user, logout } = useAuth(); // one call — not two
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const name = user?.email?.split("@")[0] || "Teacher";
  return (
    <DashboardLayout variant="teacher" pageTitle={`${greeting}, ${name}`} onLogout={logout}>
      <NewAssessmentPage />
    </DashboardLayout>
  );
}
```

3. `/teacher/assessments/new` → `NewAssessmentApp` directly, no `useRoutes`.

4. Replace ALL `/teacher/classes/:classId/[anything]` exact routes with one wildcard:
```tsx
<Route
  path="/teacher/classes/:classId/*"
  element={
    <PrivateRoute>
      <RoleRoute allowedRoles={[UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN]}>
        <ErrorBoundary role="teacher">
          <TeacherContentShell />
        </ErrorBoundary>
      </RoleRoute>
    </PrivateRoute>
  }
/>
```

5. Inside `TeacherContentShell`, short relative paths:
```tsx
const contentRoutes = useMemo(() => [
  { path: "assessments",        element: <AssessmentListPage /> },
  { path: "gap-map",            element: <GapMapPage /> },
  { path: "lesson-plans",       element: <LessonPlansPage /> },
  { path: "explanation-review", element: <ExplanationReviewPage /> },
  { path: "*", element: <Navigate to="/teacher/dashboard" replace /> },
], []);
```

6. Add missing imports: `GapMapPage`, `LessonPlansPage`

7. Add missing standalone routes — both need `RoleRoute`:
```tsx
<Route
  path="/teacher/students"
  element={
    <PrivateRoute>
      <RoleRoute allowedRoles={[UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN]}>
        <ErrorBoundary role="teacher">
          <StudentsPage />
        </ErrorBoundary>
      </RoleRoute>
    </PrivateRoute>
  }
/>
<Route
  path="/teacher/students/:studentId/profile"
  element={
    <PrivateRoute>
      <RoleRoute allowedRoles={[UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN]}>
        <ErrorBoundary role="teacher">
          <StudentProfilePage />
        </ErrorBoundary>
      </RoleRoute>
    </PrivateRoute>
  }
/>
```

**Acceptance:**
- Class-scoped pages navigate correctly without redirecting to dashboard.
- `/teacher/students` and `/teacher/students/:studentId/profile` are reachable.
- No route missing `RoleRoute`.

---

### T-002 · Fix useTeacherDashboard — Always Returns Zeros
**Files:** `hooks/useTeacherDashboard.ts`

**Problem:**
`studentCount` hardcoded to `0`, `avgMastery` hardcoded to `null`. Analytics endpoint is a stub.

**Fix:**
Call `GET /grades` and `GET /subjects` once (they're static seed data) then map IDs to names. Call `GET /classes/{id}/summary` in parallel for mastery data.

```ts
import { useQuery, useQueries } from "@tanstack/react-query";

// Grades and subjects — static, cache forever
export function useGrades() {
  return useQuery({
    queryKey: ["grades"],
    queryFn: () => apiClient.get("/api/v1/grades").then(r => r.data),
    staleTime: Infinity,
  });
}

export function useSubjects() {
  return useQuery({
    queryKey: ["subjects"],
    queryFn: () => apiClient.get("/api/v1/subjects").then(r => r.data),
    staleTime: Infinity,
  });
}
```

```ts
// Inside useTeacherDashboard
const classesQuery = useQuery({
  queryKey: ["teacher", "classes", schoolId],
  queryFn: () => apiClient.get(`/api/v1/schools/${schoolId}/classes`).then(r => r.data ?? []),
  enabled: !!schoolId,
});

const classes: ClassResponse[] = classesQuery.data ?? [];

// Parallel summary calls — typed, not any[]
const summaryQueries = useQueries({
  queries: classes.map(c => ({
    queryKey: ["teacher", "class-summary", c.id],
    queryFn: () =>
      apiClient.get(`/api/v1/classes/${c.id}/summary`)
        .then(r => r.data as ClassSummary)
        .catch(() => null),
    staleTime: 5 * 60 * 1000,
    enabled: !!c.id,
  })),
});

// Map classes with real data — no any[], use grade/subject maps from above
const enrichedClasses: TeacherClass[] = classes.map((c, i) => {
  const summary = summaryQueries[i]?.data;
  const gradeName = gradeMap[c.grade_id] ?? c.name;
  const subjectName = subjectMap[c.subject_id] ?? "";
  return {
    id: c.id,
    name: c.name,
    subjectId: c.subject_id,
    subjectName,
    gradeName,
    studentCount: summary?.student_count ?? 0,
    avgMastery: summary?.avg_mastery ?? null,
    studentsBelow: summary?.students_below_threshold ?? 0,
    lessonPlanStatus: "none" as const,
  };
});
```

Note: `students_below_threshold` comes from T-030. Until T-030 ships, default to `0`.

**React Query v5 note:** Use `isPending` (not `isLoading`) for initial skeleton rendering in all new hooks. `isLoading` still works but is deprecated for uninitiated queries.

**Acceptance:** ClassCards show real student counts, real mastery, and grade/subject names without fragile string parsing.

---

### T-003 · Enable "View Results" in AssessmentListPage
**Files:** `pages/assessments/AssessmentListPage.tsx`

**Fix — use `<Link>` directly, no button nesting (button inside anchor = invalid HTML):**
```tsx
{(assessment.status === "ACTIVE" || assessment.status === "CLOSED") && (
  <Link
    to={`/teacher/assessments/${assessment.id}/results`}
    className="flex items-center gap-1.5 text-xs font-sans font-bold text-brand-gold hover:text-brand-gold-dark focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 rounded px-2 py-1"
  >
    <BarChart2 className="w-3.5 h-3.5" aria-hidden="true" />
    View Results
  </Link>
)}
```

**Acceptance:** ACTIVE/CLOSED assessments show a working View Results link. DRAFT assessments do not.

---

### T-004 · Remove Global "New Assessment" Button From Topbar
**Files:** `App.tsx`

**Fix:**
1. Remove `topNavAction` prop from all `DashboardLayout` calls in teacher shells.
2. Remove now-unused `Link`, `Button`, `Plus` imports from `App.tsx`.
3. `+ New Assessment` button lives only in `AssessmentListPage` and `AllAssessmentsPage` (T-013) headers.

**Acceptance:** No `+ New Assessment` button on Gap Map, Settings, Student Profile, or any page other than the two assessments list pages.

---

### T-005 · Remove debugger Statement
**Files:** `App.tsx`

Delete the `debugger;` line in `TeacherContentShell`. One line.

---

### T-006 · Fix Back Navigation
**Files:** `GapMapPage.tsx`, `AssessmentResultsPage.tsx`, `MyStudents.tsx`, `StudentProfileHeader.tsx`

| Page | Correct back link |
|---|---|
| GapMapPage | `/teacher/classes/:classId` |
| AssessmentResultsPage | `/teacher/classes/:classId/assessments` |
| StudentsPage | `/teacher/students` |
| StudentProfileHeader | `/teacher/students` |

`classId` is available from `useParams` on all class-scoped pages — no prop threading needed.

---

### T-007 · Fix Dead Links in ClassCard, PendingActionBanner, ThisWeekCard, StudentGapMapTab
**Files:** `ClassCard.tsx`, `PendingActionBanner.tsx`, `ThisWeekCard.tsx`, `StudentGapMapTab.tsx`

**ClassCard — new structure (4 quick links + View →):**
```tsx
<div className="border-t border-brand-border pt-3">
  <div className="flex flex-wrap gap-x-3 gap-y-1 mb-2">
    <Link
      to={`/teacher/classes/${classId}/gap-map`}
      title="See where each student is struggling by topic"
      className="text-sm text-brand-muted hover:text-brand-primary transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1 rounded"
    >
      Gap Map
    </Link>
    <span className="text-brand-border" aria-hidden="true">·</span>
    <Link
      to={`/teacher/classes/${classId}/assessments`}
      className="text-sm text-brand-muted hover:text-brand-primary transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1 rounded"
    >
      Assessments
    </Link>
    <span className="text-brand-border" aria-hidden="true">·</span>
    <Link
      to={`/teacher/classes/${classId}/lesson-plans`}
      className="text-sm text-brand-muted hover:text-brand-primary transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1 rounded"
    >
      Lesson Plans
    </Link>
  </div>
  <Link
    to={`/teacher/classes/${classId}`}
    className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark float-right focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1 rounded"
  >
    View →
  </Link>
</div>
```

**Acceptance:** All quick links and View → navigate correctly. No `:classId` literal strings in rendered output.

---

## 🟠 P2 — Sidebar & Navigation

---

### T-008 · Restructure Teacher Sidebar
**Files:** `components/Sidebar.tsx`

**New `teacherSections`:**
```tsx
const teacherSections: NavSection[] = [
  {
    section: "MY WORKSPACE",
    items: [
      { label: "Home",           href: "/teacher/dashboard",       icon: LayoutDashboard },
      { label: "Classes",        href: "/teacher/classes",         icon: Building2 },
      { label: "Students",       href: "/teacher/students",        icon: Users },
      { label: "Assessments",    href: "/teacher/assessments",     icon: ClipboardList },
    ],
  },
  {
    section: "TOOLS",
    items: [
      { label: "Lesson Plans",   href: "/teacher/lesson-plans",   icon: BookOpen },
      { label: "Content Review", href: "/teacher/content-review", icon: FileText },
    ],
  },
  {
    section: "ACCOUNT",
    items: [
      { label: "Settings",       href: "/teacher/settings",       icon: Settings },
    ],
  },
];
```

**Remove:**
- `resolveHref` function — no longer needed
- `classId` prop from `SidebarProps`
- All `:classId`-dependent hrefs

**Icon note:** `Building2` for Classes — do not use `BookOpen` which conflicts with Lesson Plans.

**Acceptance:** Teacher sidebar has 7 items. None contain `:classId`. All resolve without params.

---

## 🟡 P3 — New Pages

---

### T-009 · Dashboard Redesign
**Files:** `pages/dashboard/TeacherDashboard.tsx`, `pages/dashboard/ClassCard.tsx`, `pages/dashboard/PendingActionBanner.tsx`
**API:** `GET /schools/{id}/classes` + `GET /classes/{id}/summary` ×N + `GET /teacher/classes/{id}/explanation-review?status=pending` ×N

**Section 1 — Needs Attention (class-level, no individual student names):**
Individual student names require N gap-map calls — not feasible on dashboard load. Show class-level alerts using `students_below_threshold` from `ClassSummary` (T-030):
```tsx
// New NeedsAttentionBanner — uses existing bg-brand-gold-light border-brand-gold-mid tokens
{enrichedClasses
  .filter(cls => cls.studentsBelow > 0)
  .map(cls => (
    <div
      key={cls.id}
      className="bg-brand-gold-light border border-brand-gold-mid rounded-xl p-4 flex items-center justify-between"
    >
      <div className="flex items-center gap-3">
        <AlertTriangle className="w-5 h-5 text-brand-gold" aria-hidden="true" />
        <span className="text-sm font-medium text-brand-ink">
          {cls.name} · {cls.avgMastery !== null ? `${Math.round(cls.avgMastery * 100)}% avg` : "No data"} · {cls.studentsBelow} student{cls.studentsBelow !== 1 ? "s" : ""} below 40%
        </span>
      </div>
      <Link to={`/teacher/classes/${cls.id}/gap-map`} className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark focus-visible:ring-2 focus-visible:ring-brand-gold rounded">
        Open Gap Map →
      </Link>
    </div>
  ))
}
```

**Section 2 — Ready for You (only show when items exist):**
- Content review pending → card linking to `/teacher/content-review`
- Lesson plan generated → card linking to `/teacher/classes/:classId/lesson-plans`
- Empty when nothing is new — section disappears entirely

**Section 3 — My Classes:**
- Same ClassCard grid, real data from T-002
- Max 3 cards shown, "See all →" links to `/teacher/classes`
- Show up to 3 Needs Attention banners (not just the first one)

**Typography:** All page `<h1>` elements must use `font-display font-bold text-2xl text-brand-ink`.

---

### T-010 · Build Classes List Page
**Files:** New — `pages/classes/ClassesPage.tsx`
**API:** `GET /schools/{id}/classes` + `GET /classes/{id}/summary` ×N parallel

Page title: `<h1 className="font-display font-bold text-2xl text-brand-ink">Classes</h1>`

Card grid using the same `ClassCard` component from dashboard. Skeleton loading. Empty state.

**Acceptance:** `/teacher/classes` renders all classes with working quick links and View →.

---

### T-011 · Build Class Detail Page
**Files:** New — `pages/classes/ClassDetailPage.tsx`
**API:** `GET /classes/{id}/summary` + `GET /classes/{id}/assessments` + `GET /classes/{id}/enrollments` + `GET /classes/{id}/gap-map?subject_id=` — 4 parallel calls

**Breadcrumb:**
```tsx
<nav className="flex items-center gap-2 text-sm text-brand-muted mb-4" aria-label="Breadcrumb">
  <Link to="/teacher/classes" className="hover:text-brand-ink transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold rounded">
    Classes
  </Link>
  <span className="text-brand-border" aria-hidden="true">/</span>
  <span className="text-brand-ink">{cls.name}</span>
</nav>
```

**Quick-access cards (4-grid) — must include hover state:**
```tsx
<div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
  {[
    { label: "Gap Map", sub: "See where students struggle", href: `gap-map` },
    { label: "Assessments", sub: `${assessmentCount} active`, href: `assessments` },
    { label: "Lesson Plans", sub: "This week's plan", href: `lesson-plans` },
    { label: "Content Review", sub: `${pendingCount} pending`, href: `../content-review` },
  ].map(card => (
    <Link
      key={card.label}
      to={card.href}
      className="bg-white rounded-2xl border border-brand-border p-4 hover:-translate-y-0.5 hover:shadow-card-hover transition-all focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 rounded-2xl"
    >
      <div className="font-display font-semibold text-sm text-brand-ink">{card.label}</div>
      <div className="text-xs text-brand-muted mt-1">{card.sub}</div>
    </Link>
  ))}
</div>
```

**At-risk students section:**
One gap-map call is acceptable here (single class page). Show top 5 students by lowest mastery from gap map data, sorted ascending. Each row links to `/teacher/students/:studentId/profile`.

**Gap Map empty state (pedagogical — not a dead end):**
```tsx
{students.length === 0 && (
  <div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
    <p className="font-display font-semibold text-brand-ink mb-2">No gap data yet</p>
    <p className="text-sm text-brand-muted mb-4">
      Run a Diagnostic assessment first — the Gap Map builds automatically from results.
      It shows exactly where each student has gaps against their curriculum topics.
    </p>
    <Link
      to="/teacher/assessments/new"
      className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
    >
      Create a Diagnostic →
    </Link>
  </div>
)}
```

**Acceptance:** `/teacher/classes/:classId` renders with breadcrumb, 4 quick-access cards with hover state, at-risk students, recent assessments. Empty state guides teacher to create a Diagnostic.

---

### T-012 · Build Gap Map Page Updates
**Files:** `pages/gap-map/GapMapPage.tsx` (existing, update)

**Add Study Plan call-to-action below the heatmap:**
```tsx
<p className="text-sm text-brand-muted mt-4">
  Click any cell to view that student's learning profile and assign a targeted study plan directly.
</p>
```

**Fix inline style (Pixel):**
```tsx
// Replace:
<div style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}>
// With:
<div className="[writing-mode:vertical-rl] rotate-180">
```

**Empty state — same pedagogical guidance as T-011:**
Link to `/teacher/assessments/new` with a clear explanation that the Gap Map populates from assessment data.

---

### T-013 · Build Global Students List Page
**Files:** Refactor `pages/MyStudents.tsx` → `pages/students/StudentsPage.tsx`
**API:** `GET /teachers/me/students` — one call

**Important:** This endpoint returns name, email, class_ids, class_names only — **no mastery, no learning style**. See T-031 for adding mastery. Until T-031 ships, the table shows Name · Email · Class(es) only.

**Table header tokens (must match existing `StudentsTable.tsx`):**
```tsx
<thead>
  <tr className="bg-brand-bg border-b border-brand-border">
    <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-widest text-role-teacher-muted">
      Student
    </th>
    <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-widest text-role-teacher-muted">
      Class(es)
    </th>
    <th className="px-4 py-3" />
  </tr>
</thead>
```

**Default sort:** `name-asc` (cannot sort by mastery until T-031). Reinstate `mastery-asc` as default when T-031 ships.

**Class filter chips:** Additive, not blocking — all students visible by default, chips narrow the list.

**Acceptance:** `/teacher/students` shows all students on load. No broken columns. Class filter works.

---

### T-014 · Build Global Assessments List Page
**Files:** New — `pages/assessments/AllAssessmentsPage.tsx`
**API:** `GET /schools/{id}/classes` → `GET /classes/{id}/assessments` ×N parallel

**Note:** `AssessmentResponse` has `class_id` not `class_name`. Join class name from the class list already in memory — no extra calls.

**`+ New Assessment` button:** Right side of page header only. Not in topbar.

Filter chips: All · Active · Draft · Closed

**Acceptance:** `/teacher/assessments` shows all assessments across classes. class_name correctly joined.

---

### T-015 · Build Lesson Plans Placeholder Page
**Files:** New — `pages/lesson-plans/AllLessonPlansPage.tsx`
**API:** `GET /classes/{id}/lesson-plans` (M4 stub)

Empty state copy (curriculum-agnostic):
```
📋 Lesson plans are generated every Monday at 6am.

They're built around your students' topic gaps — personalised to
whichever subtopics your class is struggling with that week.

Create assessments first to unlock personalised plans.
[Create an Assessment →]
```

**Acceptance:** `/teacher/lesson-plans` renders without error. Stub returns empty gracefully.

---

### T-016 · Build Content Review Global Page
**Files:** New — `pages/content-review/ContentReviewPage.tsx`
**API:** `GET /schools/{id}/classes` → `GET /teacher/classes/{id}/explanation-review?status=pending` ×N parallel

**Note:** `TeacherExplanationReviewItem` has no `class_name`. Join from class list already in memory using the class context from the parallel calls.

Filter chips: Pending · Approved · Rejected · All
Class filter chips: narrow by class

**Naming note in code comment:**
```tsx
// UI: "Content Review" | Route: /teacher/content-review | API: /explanation-review
// All three are intentional — do not rename.
```

**Acceptance:** `/teacher/content-review` shows pending items across all classes. Class name joined from memory.

---

## 🔵 P4 — Screen Polish

---

### T-017 · Add Breadcrumbs to Deep Pages
**Files:** `GapMapPage.tsx`, `AssessmentResultsPage.tsx`, `ExplanationReviewPage.tsx`, class detail pages

**Pattern — breadcrumb separator must be `aria-hidden` with token color:**
```tsx
<nav className="flex items-center gap-2 text-sm text-brand-muted mb-4" aria-label="Breadcrumb">
  <Link to="/teacher/classes" className="hover:text-brand-ink transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold rounded">
    Classes
  </Link>
  <span className="text-brand-border" aria-hidden="true">/</span>
  <Link to={`/teacher/classes/${classId}`} className="hover:text-brand-ink transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold rounded">
    {currentClass?.name ?? "Class"}
  </Link>
  <span className="text-brand-border" aria-hidden="true">/</span>
  <span className="text-brand-ink font-medium">Gap Map</span>
</nav>
```

| Page | Breadcrumb |
|---|---|
| Class Detail | Classes / [Class Name] |
| Gap Map | Classes / [Class Name] / Gap Map |
| Class Assessments | Classes / [Class Name] / Assessments |
| Assessment Results | Classes / [Class Name] / Assessments / Results |
| Content Review (class) | Classes / [Class Name] / Content Review |
| Student Profile | Students / [Student Name] |

---

### T-018 · Add Post-Publish Success Banner
**Files:** `pages/assessments/steps/Step5Publish.tsx`, `pages/assessments/AssessmentListPage.tsx`

**Step5Publish — invalidate cache then navigate:**
```tsx
async function handlePublish() {
  // ... existing publish logic ...
  await apiClient.post(`/api/v1/assessments/${targetAssessmentId}/publish`);

  // Invalidate stale assessment list cache before navigating
  queryClient.invalidateQueries({
    queryKey: ["assessments", "class", targetClassId],
  });

  reset();
  navigate(`/teacher/classes/${targetClassId}/assessments?published=true`);
  toast.success("Assessment published — students can now access it.");
}
```

**Step5Publish — add student access note above Publish button:**
```tsx
<div className="bg-brand-surface rounded-xl p-4 text-sm text-brand-body border border-brand-border mb-4">
  Once published, students can access this assessment from their Kaihle dashboard.
  They won't receive an email — they need to log in to see it.
</div>
```

**AssessmentListPage — read query param and show dismissible banner:**
```tsx
const [searchParams, setSearchParams] = useSearchParams();
const justPublished = searchParams.get("published") === "true";

const dismissBanner = () => setSearchParams({}, { replace: true });

{justPublished && (
  <div className="bg-brand-green-light border border-brand-green rounded-xl p-4 flex items-center justify-between mb-4">
    <span className="text-sm font-medium text-brand-ink">
      ✓ Assessment published — students can now access it from their dashboard.
    </span>
    <button
      onClick={dismissBanner}
      className="text-sm text-brand-muted hover:text-brand-ink focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
      aria-label="Dismiss"
    >
      ✕
    </button>
  </div>
)}
```

**Note on React Query v5:** `onSuccess` on `useQuery` was removed in v5. Do not use it in new hooks. Use `useEffect` watching `data` for side effects.

---

### T-019 · Fix Color Token Inconsistency in Results Pages
**Files:** `AssessmentResultsPage.tsx`, `StudentResultDetailPage.tsx`, `ResultsKPIRow.tsx`

| Replace | With |
|---|---|
| `border-gray-100` | `border-brand-border` |
| `shadow-sm` | `shadow-card` |
| `bg-gray-50` | `bg-brand-bg` |
| `text-gray-400` | `text-brand-muted` |

---

### T-020 · Fix min-h on tr, Inline Styles, URL-Driven Tabs

**AssessmentListPage.tsx:** Remove `min-h-[56px]` from `<tr>` — does not work on table rows.

**GapMapPage.tsx:**
```tsx
// Replace inline style:
<div className="[writing-mode:vertical-rl] rotate-180">
```

**StudentProfilePage.tsx — tabs should be URL-driven:**
```tsx
const [searchParams, setSearchParams] = useSearchParams();
const activeTab = (searchParams.get("tab") as TabId) ?? "gap-map";
const handleTabChange = (tab: TabId) => setSearchParams({ tab }, { replace: true });
```

---

### T-021 · Extract useTeacherShellProps — Renamed
**Files:** `App.tsx`

**Note:** This is NOT a React hook. Name it accordingly:
```tsx
// Plain function — no state, no effects, no React APIs
function getTeacherGreeting(email: string | undefined): { pageTitle: string } {
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const name = email?.split("@")[0] || "Teacher";
  return { pageTitle: `${greeting}, ${name}` };
}
```

All shells call `getTeacherGreeting(user?.email)`. No `use` prefix.

---

## 🔧 P5 — Code Quality

---

### T-022 · Fix N+1 in useStudentProfile
**Files:** `hooks/useStudentProfile.ts`

Cap parallel enrollment checks at 5. Cache aggressively: `staleTime: 30 * 60 * 1000`.

**Backend request (flag for backend team):** Add `GET /students/{studentId}/classes` returning enrolled classes directly. This eliminates the N+1 entirely and is the correct long-term fix.

---

## 🔴 P1 — Backend: Missing Endpoints

---

### T-023 · Backend: GET /assessments/{id}/results
**File:** `backend/app/api/v1/routes/assessments.py`
**Schemas:** `backend/app/schemas/assessments.py`
**Priority:** Blocking — `AssessmentResultsPage` 404s without this.

**New schemas:**
```python
from typing import Literal
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

class StudentAttemptSummary(BaseModel):
    attempt_id: UUID | None = None  # None when NOT_STARTED — do not use uuid4() sentinel
    student_id: UUID
    student_name: str
    score: float | None
    submitted_at: datetime | None
    status: Literal["SUBMITTED", "IN_PROGRESS", "NOT_STARTED"]

class AssessmentResultsSummary(BaseModel):
    assessment_id: UUID
    assessment_title: str
    assessment_type: str
    class_id: UUID
    class_name: str
    total_students: int
    submitted_count: int
    attempts: list[StudentAttemptSummary]
```

**Route:**
```python
@router.get(
    "/assessments/{assessment_id}/results",
    response_model=AssessmentResultsSummary,
)
async def get_assessment_results(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(
        require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResultsSummary:
    """
    All student attempt summaries for an assessment (class overview).
    Distinct from GET /attempts/{id}/results (per-student question breakdown).
    """
    service = AssessmentService(db)
    try:
        return await service.get_assessment_results(
            assessment_id=assessment_id,
            school_id=current_user.school_id,
            requesting_user_id=current_user.id,
            requesting_user_role=current_user.role,
        )
    except AssessmentAccessDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
```

**Service method — imports at file top, not inside function:**
```python
# These imports belong at the TOP of assessment_service.py, not inside the method
from sqlalchemy import select, and_
from app.models.assessment import Assessment, StudentAttempt
from app.models.school import Class, ClassEnrollment
from app.models.user import User

async def get_assessment_results(
    self,
    assessment_id: UUID,
    school_id: UUID | None,
    requesting_user_id: UUID,
    requesting_user_role: UserRole,
) -> AssessmentResultsSummary:

    # Step 1 — Load assessment
    assessment = await self.db.get(Assessment, assessment_id)
    if assessment is None:
        raise ValueError(f"Assessment {assessment_id} not found")

    # Step 2 — School access
    if requesting_user_role != UserRole.KAIHLE_ADMIN:
        if assessment.school_id != school_id:
            raise AssessmentAccessDeniedError()

    # Step 3 — Always fetch class (no conditional assignment that causes NameError)
    class_ = await self.db.get(Class, assessment.class_id)
    if class_ is None:
        raise ValueError(f"Class not found for assessment {assessment_id}")

    # Step 4 — TEACHER must own the class
    if requesting_user_role == UserRole.TEACHER:
        if class_.teacher_id != requesting_user_id:
            raise AssessmentAccessDeniedError()

    # Step 5 — One query: all enrolled students left-joined to their attempt
    rows = (await self.db.execute(
        select(
            ClassEnrollment.student_id,
            User.first_name,
            User.last_name,
            StudentAttempt.id.label("attempt_id"),
            StudentAttempt.overall_score,
            StudentAttempt.status,
            StudentAttempt.completed_at,
        )
        .join(User, User.id == ClassEnrollment.student_id)
        .outerjoin(
            StudentAttempt,
            and_(
                StudentAttempt.student_id == ClassEnrollment.student_id,
                StudentAttempt.assessment_id == assessment_id,
            ),
        )
        .where(
            ClassEnrollment.class_id == assessment.class_id,
            ClassEnrollment.is_active.is_(True),
        )
        .order_by(StudentAttempt.overall_score.asc().nullsfirst())
    )).all()

    attempts = [
        StudentAttemptSummary(
            attempt_id=row.attempt_id,   # None for NOT_STARTED — no sentinel UUID
            student_id=row.student_id,
            student_name=f"{row.first_name or ''} {row.last_name or ''}".strip() or "Unknown",
            score=float(row.overall_score) if row.overall_score is not None else None,
            submitted_at=row.completed_at,
            status=row.status or "NOT_STARTED",
        )
        for row in rows
    ]

    return AssessmentResultsSummary(
        assessment_id=assessment.id,
        assessment_title=assessment.title,
        assessment_type=assessment.assessment_type,
        class_id=assessment.class_id,
        class_name=class_.name,
        total_students=len(attempts),
        submitted_count=sum(1 for a in attempts if a.status == "SUBMITTED"),
        attempts=attempts,
    )
```

**Frontend must check `attempt_id !== null` before rendering "View answers →":**
```tsx
{attempt.status === "SUBMITTED" && attempt.attemptId !== null && (
  <Link to={`/teacher/assessments/${assessmentId}/results/${attempt.studentId}?attempt=${attempt.attemptId}`}>
    View answers →
  </Link>
)}
```

**Acceptance:**
- `GET /api/v1/assessments/{id}/results` returns 200 with all enrolled students.
- NOT_STARTED students appear with `score: null`, `attempt_id: null`, `status: "NOT_STARTED"`.
- TEACHER gets 403 if they don't own the class.
- `AssessmentResultsPage` renders KPI row, distribution chart, student table.

---

### T-024 · Backend: GET /students/{student_id}/attempts
**File:** `backend/app/api/v1/routes/attempts.py`
**Schemas:** `backend/app/schemas/attempts.py`

**New schema:**
```python
class StudentAttemptHistoryItem(BaseModel):
    attempt_id: UUID
    assessment_id: UUID
    assessment_title: str
    assessment_type: str
    class_id: UUID
    class_name: str
    score: float | None
    status: str
    submitted_at: datetime | None
    created_at: datetime
```

**Route — all imports at file top, not inside function:**
```python
# Add to TOP of attempts.py with existing imports:
from sqlalchemy import func
from app.models.school import Class, ClassEnrollment
from app.models.user import ParentStudent

@router.get(
    "/students/{student_id}/attempts",
    response_model=Page[StudentAttemptHistoryItem],
)
async def get_student_attempts(
    student_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> Page[StudentAttemptHistoryItem]:
    """
    Paginated attempt history for a student. Used by Student Profile → Assessments tab.
    Ordered newest first.
    """
    if current_user.role == UserRole.STUDENT:
        if current_user.id != student_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Students can only view their own attempts.")

    elif current_user.role == UserRole.TEACHER:
        result = await db.execute(
            select(ClassEnrollment.student_id)
            .join(Class, Class.id == ClassEnrollment.class_id)
            .where(
                ClassEnrollment.student_id == student_id,
                Class.teacher_id == current_user.id,
                ClassEnrollment.is_active.is_(True),
            )
            .limit(1)
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Student is not enrolled in any of your classes.")

    elif current_user.role == UserRole.SCHOOL_ADMIN:
        student = await db.get(User, student_id)
        if student is None or student.school_id != current_user.school_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    elif current_user.role == UserRole.PARENT:
        link = await db.execute(
            select(ParentStudent).where(
                ParentStudent.parent_id == current_user.id,
                ParentStudent.student_id == student_id,
            )
        )
        if link.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="You can only view attempts for linked students.")

    base_query = (
        select(
            StudentAttempt,
            Assessment.title.label("assessment_title"),
            Assessment.assessment_type,
            Assessment.class_id,
            Class.name.label("class_name"),
        )
        .join(Assessment, Assessment.id == StudentAttempt.assessment_id)
        .join(Class, Class.id == Assessment.class_id)
        .where(StudentAttempt.student_id == student_id)
        .order_by(StudentAttempt.created_at.desc())
    )

    total = (await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )).scalar_one()

    rows = (await db.execute(
        base_query.offset((page - 1) * page_size).limit(page_size)
    )).all()

    items = [
        StudentAttemptHistoryItem(
            attempt_id=row.StudentAttempt.id,
            assessment_id=row.StudentAttempt.assessment_id,
            assessment_title=row.assessment_title,
            assessment_type=row.assessment_type,
            class_id=row.class_id,
            class_name=row.class_name,
            score=float(row.StudentAttempt.overall_score)
                  if row.StudentAttempt.overall_score is not None else None,
            status=row.StudentAttempt.status,
            submitted_at=row.StudentAttempt.completed_at,
            created_at=row.StudentAttempt.created_at,
        )
        for row in rows
    ]

    return Page(data=items, total=total, page=page, page_size=page_size)
```

**Acceptance:**
- Returns paginated attempt history, newest first.
- TEACHER gets 403 if student not in their class.
- Student Profile Assessments tab renders correctly.

---

### T-025 · Backend: Extend ClassSummary with students_below_threshold
**Files:** `backend/app/schemas/gap_map.py`, `backend/app/services/gap_service.py`

**Schema change (non-breaking):**
```python
class ClassSummary(BaseModel):
    class_id: UUID
    avg_mastery: float | None
    student_count: int
    students_below_threshold: int = 0  # count with avg mastery < 0.4, defaults to 0
```

Compute from the same gap_states data already queried in `get_class_summary()` — no extra DB round trip.

**Acceptance:** Dashboard Needs Attention banners show class-level data without extra API calls. Field defaults to 0 — no existing consumers break.

---

## 🧪 P6 — Testing

---

### T-026 · Unit Tests for ClassCard Redesign
**File:** New — `src/tests/class-card.test.tsx`

- All 3 quick links render with correct hrefs (no `:classId` literal)
- View → renders with correct href
- Mastery color classes per band (Strong/Developing/Needs Work)
- Skeleton renders without crashing
- Focus-visible classes present on all interactive elements

---

### T-027 · E2E Smoke Tests for New Routes
**File:** New — `src/tests/navigation.spec.ts`

- `/teacher/classes` renders, no dashboard redirect
- `/teacher/students` renders student list
- `/teacher/assessments` renders assessments list
- Gap Map quick link on ClassCard navigates to correct URL
- Back navigation from GapMapPage goes to Class Detail, not dashboard
- Breadcrumb segments are all working links

---

## 🔮 Future Tasks (Next Sprint)

---

### T-028 · Extend /teachers/me/students With avg_mastery
**Owner:** Backend + Frontend
**Priority:** P3 — without this the students list is a name directory

Extend `TeacherStudentsResponse.StudentSummary` with `avg_mastery: float | None = None` computed server-side from gap_states. Single join — no extra frontend calls. Once shipped: re-add mastery column to `StudentsTable.tsx` and reinstate `mastery-asc` as default sort.

---

### T-029 · Mastery Trend Indicators on Student Profile
**Owner:** Backend + Frontend
**Priority:** P4 — transforms Kaihle from a gradebook into a teaching partner

Show delta between current mastery score and previous assessment score per subtopic on Student Profile:
```
Algebra & graphs    31%   ↑ +14% since last assessment
Functions           45%   ↓ -3%  since last assessment
```

Requires gap_states to store historical snapshots or derive from attempt history. Makes it visible whether a teacher's intervention is working.

---

## Quick Wins — Start Here

| Task | File | Effort | Impact |
|---|---|---|---|
| T-005 Remove debugger | `App.tsx` | 1 min | Stops app freezing in DevTools |
| T-003 Enable View Results | `AssessmentListPage.tsx` | 5 min | Unlocks fully built feature |
| T-004 Remove global button | `App.tsx` | 5 min | Cleaner nav |
| T-020 Fix min-h on tr + inline styles + URL tabs | Multiple | 10 min | Code correctness + design |
| T-019 Fix color tokens | Results pages | 10 min | Design system compliance |

---

## Dependency Map

```
T-001 (Routing fix)
  └── T-007 (Fix dead links + ClassCard)
        └── T-010 (Classes list page)
              └── T-011 (Class detail page)
                    └── T-017 (Breadcrumbs)

T-002 (Fix dashboard data) — depends on T-025 (backend ClassSummary)
  └── T-009 (Dashboard redesign)

T-004 (Remove global button)
  └── T-021 (Shell function cleanup)

T-008 (Sidebar restructure)
  └── T-013 (Students page)
  └── T-015 (Lesson Plans placeholder)
  └── T-016 (Content Review global page)

T-003 (Enable View Results) — depends on T-023 (backend endpoint)
  └── T-018 (Post-publish banner)

T-023 (Backend: assessment results) — BLOCKING
T-024 (Backend: student attempts)
T-025 (Backend: ClassSummary extension)
```

---

## Out of Scope
- Study Plan browsing (M3 complete — assigned from Gap Map only, no list page)
- Lesson Plan editing (M4)
- Parent portal (M5)
- Platform analytics (M6)
- School impersonation (M6)
