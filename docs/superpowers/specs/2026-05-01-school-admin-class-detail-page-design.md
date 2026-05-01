# School Admin — Class Detail Page (Tabbed)
**Date:** 2026-05-01
**Status:** Approved
**Branch:** feat/class-detail-page (child of current bug-fix branch)

---

## 1. Problem

Clicking a class in the School Admin class list navigates directly to `/school-admin/classes/:classId/gap-map`, which:

1. Returns **422 Unprocessable Entity** because the gap-map API requires `subject_id` as a query parameter, and the current `AdminGapMapPage` does not pass it.
2. Shows **only the gap map** — no class header, no KPI stats, no student roster. School admins have no at-a-glance view of a class.

---

## 2. Solution

Replace the direct-to-gap-map navigation with a **tabbed class detail page** at `/school-admin/classes/:classId`. Three tabs: Overview · Students · Gap Map.

---

## 3. Routing

| Old route | New behaviour |
|---|---|
| `/school-admin/classes/:classId/gap-map` | Redirect to `/school-admin/classes/:classId?tab=gap-map` |
| `/school-admin/classes/:classId` | New `ClassDetailPage` component |

Active tab stored in URL query param `?tab=overview` (default) `| ?tab=students | ?tab=gap-map`. Browser back/forward and URL sharing work correctly.

`ClassManagement.tsx` `onClick` changes from `navigate(\`/school-admin/classes/${c.id}/gap-map\`)` to `navigate(\`/school-admin/classes/${c.id}\`)`.

---

## 4. Page Structure

```
┌─────────────────────────────────────────────────────┐
│  ← Classes  (breadcrumb)                            │
│                                                     │
│  English 9B                              [Read only]│
│  English Language · Grade 9 · Ms. Nguyen · 2025/26 │
│                                                     │
│  ┌──────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐  │
│  │  24  │ │  58%     │ │  18/24   │ │   4      │  │
│  │Studs │ │Avg Mstry │ │Diagnostic│ │ At Risk  │  │
│  └──────┘ └──────────┘ └───────────┘ └──────────┘  │
│                                                     │
│  [ Overview ]  [ Students ]  [ Gap Map ]            │
│  ─────────────────────────────────────────────────  │
│  (tab content)                                      │
└─────────────────────────────────────────────────────┘
```

The class header (breadcrumb + title row + KPI cards) is **always visible** regardless of active tab.

---

## 5. Data & API Calls

### On mount (fires immediately, required before any tab renders)
- `GET /classes/:classId` → `ClassResponse`
  - Provides: `name`, `subject_id`, `subject_name`, `grade_name`, `teacher_name`, `academic_year`
  - `subject_id` is stored in component state — required by the Gap Map tab to avoid 422

### KPI cards
- Source: `ClassSummary` from the already-cached `useSchoolClasses()` query (matched by `classId`)
- Fields used: `student_count`, `avg_mastery`, `students_below_threshold`
- Diagnostic count (e.g. "18/24"): not in `ClassSummary` — omit or show "—" until a dedicated endpoint exists. **Do not block the page on this.**

### Overview tab
- No additional fetch
- At-risk students list: students from the Students tab data where `worst_mastery < 0.4`; lazy — only computed once Students tab data is available

### Students tab
- `GET /classes/:classId/enrollments` → list of enrolled students with mastery
- Hook: `useClassEnrollments(classId)` — new hook in `useSchoolAdmin.ts`

### Gap Map tab
- `GET /classes/:classId/gap-map?subject_id=<subject_id>` — fires only after class detail fetch resolves
- Reuses existing gap map rendering logic from `AdminGapMapPage`

---

## 6. Tab Content

### Overview tab (default)

**At-a-glance section** — KPI cards (already in the header, not repeated).

**At-risk students list**
- Filtered from enrollment data: students with `worst_mastery < 0.4`
- Columns: Name · Mastery %
- Mastery rendered as colored dot + label via `getMasteryStyle()`
- Limited to 5 rows with "View all in Students tab →" link if more exist
- Empty state: "No students below the at-risk threshold" (shown when all students are above 40%)

**Diagnostic status**
- If `diagnostic_status === "pending"`: info card "Students haven't completed the class diagnostic yet. Results will appear here once they do."
- If `diagnostic_status === "setup_needed"`: warning card "No teacher assigned. Assign a teacher to enable the diagnostic."

### Students tab

Full enrolled student roster.

- Source: `useClassEnrollments(classId)`
- Columns: Name · Mastery · Diagnostic
- Mastery: colored dot + label (`getMasteryStyle()`) or "Pending" if null
- Diagnostic: "Done ✓" or "Pending"
- Default sort: mastery ascending (lowest = most at risk, surfaces to top)
- Empty state: "No students enrolled in this class yet."
- Loading: skeleton rows

### Gap Map tab

- Renders gap map heatmap — reuse the rendering portion of `AdminGapMapPage`
- While `subject_id` is loading (class detail fetch in flight): show skeleton
- Once `subject_id` is available: fire `useClassGapMap(classId, subjectId)` and render normally
- Error state if gap map fetch fails: "Could not load gap map. Please refresh."

---

## 7. New Hook — `useClassEnrollments`

```typescript
// in useSchoolAdmin.ts
export interface EnrolledStudent {
  id: string;
  first_name: string;
  last_name: string;
  worst_mastery: number | null;
  diagnostic_completed: boolean;
}

export function useClassEnrollments(classId: string) {
  return useQuery({
    queryKey: ["class", classId, "enrollments"],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/classes/${classId}/enrollments`);
      return res.data as EnrolledStudent[];
    },
    enabled: !!classId,
  });
}
```

---

## 8. New Hook — `useClassDetail`

```typescript
export interface ClassDetail {
  id: string;
  name: string;
  subject_id: string;
  subject_name: string;
  grade_name: string;
  teacher_name: string | null;
  academic_year: string;
}

export function useClassDetail(classId: string) {
  return useQuery({
    queryKey: ["class", classId, "detail"],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/classes/${classId}`);
      return res.data as ClassDetail;
    },
    enabled: !!classId,
  });
}
```

---

## 9. Component Tree

```
ClassDetailPage                         (new file: src/pages/ClassDetailPage.tsx)
  ├── ClassDetailHeader                 (inline in ClassDetailPage or sub-component)
  │     ├── breadcrumb ← Classes link
  │     ├── title + meta row
  │     └── KPI cards (4)
  ├── TabBar                            (inline — three buttons, ?tab param)
  └── TabPanel
        ├── OverviewTab                 (inline or src/pages/ClassOverviewTab.tsx)
        ├── StudentsTab                 (inline or src/pages/ClassStudentsTab.tsx)
        └── GapMapTab                  (extracts rendering logic from AdminGapMapPage)
```

Prefer a single file (`ClassDetailPage.tsx`) with tab panels as named sub-components exported from the same file, unless the file exceeds ~300 lines — split into separate files then.

---

## 10. Design System

Follows School Admin spec from `docs/design/DESIGN_SYSTEM.md §5.2`:

- Layout: `DashboardLayout variant="school-admin"`
- Background: `role-school-bg` (`#f5f7f1`)
- Borders: `role-school-border` (`#d4e4d8`)
- Section labels: `role-school-muted` (`#6b9e79`), `text-xs font-bold uppercase tracking-wider`
- Page heading: `font-display font-bold text-2xl text-brand-ink`
- Meta row: `font-sans text-sm text-brand-muted`
- KPI cards: `bg-white border border-role-school-border rounded-xl p-4`
- KPI value: `font-sans text-3xl font-extrabold text-brand-ink`
- Active tab indicator: bottom border `border-b-2 border-brand-primary text-brand-primary font-semibold`
- Inactive tab: `text-brand-muted hover:text-brand-body`
- "Read only" pill: `text-xs font-bold uppercase tracking-wider text-brand-primary bg-[#f0fdf4] border border-role-school-border px-3 py-1 rounded-full`

---

## 11. Loading & Error States

| State | Behaviour |
|---|---|
| Class detail loading | Skeleton header (title + 4 KPI card outlines) |
| Class detail error | Full-page error: "Could not load class. Please refresh." |
| Students loading | Skeleton rows in Students tab |
| Gap map loading | Skeleton grid in Gap Map tab |
| No enrolled students | Empty state: person icon + "No students enrolled yet." |
| Gap map 422 guard | `subject_id` must be resolved before gap-map query fires (`enabled: !!subjectId`) |

---

## 12. Routing Changes (App.tsx)

```tsx
// Remove:
<Route path="classes/:classId/gap-map" element={<AdminGapMapPage />} />

// Add:
<Route path="classes/:classId" element={<ClassDetailPage />} />
```

`AdminGapMapPage` is kept as a file but its gap-map rendering logic is extracted into a shared sub-component used by `GapMapTab`. The standalone page is no longer linked from the class list.

---

## 13. Out of Scope

- Editing class details (teacher reassignment, rename) — existing modals handle this elsewhere
- Student drill-down from the Students tab (no student detail page in scope for this task)
- Diagnostic count KPI (no API field available yet — show "—")
- Pagination on the Students tab (class sizes are small in v1 pilot, ≤ 40 students)
