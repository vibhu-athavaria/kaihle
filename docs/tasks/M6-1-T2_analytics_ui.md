# M6-1-T2 — Analytics Dashboard UI (School Admin)

**Milestone:** M6 — Analytics, Billing & Launch Polish
**Epic:** M6-1 — School Admin Analytics Dashboard
**Task ID:** M6-1-T2
**Depends on:** M6-1-T1 (analytics endpoint)
**Blocks:** Nothing in this epic

---

## User Story

As a school admin, I want a clear dashboard showing platform usage so I can understand adoption, identify which classes are active, and report progress to school leadership.

---

## What To Build

A school admin analytics page in the teacher app (school admins use the same app as teachers but see additional admin views). KPI cards at top, a mastery trend chart, and a class-by-class table.

---

## Files To Create

```
/frontend/apps/teacher/src/
  pages/
    admin/
      AnalyticsDashboard.tsx        ← main analytics page
  components/
    analytics/
      KpiCard.tsx                   ← reusable KPI metric card
      OnboardingRateCard.tsx        ← special card with progress bar
      MasteryBySubjectChart.tsx     ← bar chart (Recharts)
      ClassBreakdownTable.tsx       ← sortable table
  hooks/
    useSchoolAnalytics.ts           ← React Query hook
```

**Route:** `/admin/analytics` (protected by `SchoolAdmin | KaihleAdmin` role check in `RoleRoute`)

---

## Page Layout

```
┌─────────────────────────────────────────────────────────────┐
│  School Analytics                          Last updated: now │
│                                                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │ Total   │ │ Active  │ │Assessmts│ │Study    │          │
│  │Students │ │ (7days) │ │Completed│ │Plans    │          │
│  │   147   │ │   89    │ │  412    │ │  63     │          │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
│                                                             │
│  ┌─ Onboarding Completion ───────────────────────────────┐ │
│  │  73% of students fully onboarded                      │ │
│  │  [████████████████████░░░░░░░░] 107 / 147             │ │
│  │  27 students still pending onboarding                 │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌─ Average Mastery by Subject ──────────────────────────┐ │
│  │  [MasteryBySubjectChart — horizontal bar chart]       │ │
│  │  Mathematics  ████████████░░  62%                     │ │
│  │  Science      █████████░░░░░  54%                     │ │
│  │  English      ██████████████  71%                     │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌─ Class Breakdown ─────────────────────────────────────┐ │
│  │  [ClassBreakdownTable — sortable]                     │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Details

### `KpiCard.tsx`
```tsx
interface KpiCardProps {
  label: string
  value: number | string
  subtext?: string          // e.g. "last 7 days"
  icon?: React.ReactNode
  trend?: "up" | "down" | "neutral"
}
// Simple card: white bg, shadow, large number, label below
// Optional trend arrow (not required for v1 — just pass neutral)
```

### `OnboardingRateCard.tsx`
```tsx
// Special KPI card for onboarding completion
// Shows: percentage (large), progress bar, "X students pending" subtext
// Progress bar uses green (#10B981) for filled portion
// If rate < 0.5 → show amber warning "More than half your students haven't completed onboarding"
// If rate >= 0.9 → show green "Almost all students are ready!"
```

### `MasteryBySubjectChart.tsx`
```tsx
// Uses Recharts BarChart (horizontal)
// Data: avg_mastery_by_subject array from analytics response
// X axis: 0% to 100% (convert mastery 0.0–1.0 to percentage)
// Bar colour: same mastery thresholds as CONSTITUTION §11
//   < 40% → red, 40–70% → amber, > 70% → green
// Tooltip: "Subject: X% average mastery across N students"
// No y-axis labels needed — use bars only with subject name on left

import { BarChart, Bar, XAxis, Cell, Tooltip, ResponsiveContainer } from "recharts"

const getMasteryColour = (mastery: number) => {
  if (mastery < 0.4) return "#EF4444"
  if (mastery <= 0.7) return "#F59E0B"
  return "#10B981"
}
```

### `ClassBreakdownTable.tsx`
```tsx
// Columns: Class Name | Subject | Grade | Teacher | Students | Avg Mastery | Assessments
// Sortable by clicking column header
// Avg Mastery shown as coloured badge (red/amber/green) + percentage
// Empty state: "No classes with assessment data yet"
// Pagination: show all if < 20 rows; paginate (10/page) if ≥ 20
```

### `useSchoolAnalytics.ts`
```ts
const useSchoolAnalytics = (schoolId: string) =>
  useQuery({
    queryKey: ["analytics", schoolId],
    queryFn: () => apiClient.get(`/schools/${schoolId}/analytics`),
    staleTime: 5 * 60 * 1000,    // 5 min — matches server-side Redis TTL
    refetchOnWindowFocus: false,  // analytics doesn't need to be real-time
  })
```

---

## Acceptance Criteria

- [ ] E2E test: school admin navigates to `/admin/analytics` → sees all 4 KPI cards
- [ ] E2E test: onboarding rate of 73% → progress bar shows correct fill
- [ ] E2E test: mastery chart renders bars for each subject
- [ ] E2E test: mastery bar for subject with avg 0.35 → red bar
- [ ] E2E test: class table renders with correct teacher and student counts
- [ ] E2E test: clicking column header sorts table
- [ ] E2E test: Teacher role accessing `/admin/analytics` → redirected (403 or `/unauthorised`)
- [ ] Unit test: `getMasteryColour(0.4)` → amber `#F59E0B` (boundary)
- [ ] Unit test: `KpiCard` renders label and value correctly
- [ ] Unit test: `OnboardingRateCard` with rate=0.45 → shows amber warning
- [ ] Responsive: KPI cards wrap to 2×2 grid at 768px, stack to 1 column at 375px

---

## Output (what M6-2-T1 needs)

- School admin analytics fully visible — adoption visible at a glance
- Onboarding completion rate visible, which will drive admin conversations about pending students
- Class breakdown table gives admin visibility for billing conversations
