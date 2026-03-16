# M5-1-T3 — Parent Portal UI

**Milestone:** M5 — Parent Portal
**Epic:** M5-1 — Parent Narratives
**Task ID:** M5-1-T3
**Depends on:** M5-1-T2 (all parent API endpoints)
**Blocks:** Nothing — last task of M5

---

## User Story

As a parent, I want a simple, friendly dashboard that shows me my child's weekly progress in plain English with a colour-coded progress overview, so I can stay informed and support them at home.

---

## What To Build

The full parent app UI — dashboard, child selector, weekly reports, and simplified progress view. No jargon, no raw numbers. Mobile-first (parents are primarily on phones).

---

## Files To Create

```
/frontend/apps/parent/src/
  pages/
    dashboard/
      ParentDashboard.tsx           ← main landing page
    progress/
      ChildProgressPage.tsx         ← full progress view for one child
      WeeklyReportCard.tsx          ← expandable report card
      SimpleGapMap.tsx              ← traffic-light topic grid
  components/
    parent/
      ChildSelector.tsx             ← dropdown/tabs for multi-child families
      NarrativeCard.tsx             ← latest narrative highlighted card
      TopicTrafficLight.tsx         ← single topic with circle + label
  hooks/
    useParentData.ts                ← React Query hooks for parent endpoints
```

---

## Page Layouts

### `ParentDashboard.tsx` — route: `/parent/dashboard`

```
┌──────────────────────────────────────────────────────┐
│  👋 Hello Sarah                                       │
│                                                      │
│  [Emma Wilson ▾]    ← ChildSelector (if 2+ children) │
│                                                      │
│  ┌─ Latest Update ──────────────────────────────┐   │
│  │  📚 Mathematics · Week of 2 Mar 2026          │   │
│  │                                              │   │
│  │  "Emma had a great week in Mathematics!      │   │
│  │   She's made solid progress with fractions   │   │
│  │   and is building confidence with ratios.    │   │
│  │   Next week she'll be working on percentages │   │
│  │   — you can help at home by..."              │   │
│  │                                              │   │
│  │  [See full progress →]                       │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  Quick Overview                                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐             │
│  │  MATH   │  │ SCIENCE │  │ ENGLISH │             │
│  │   🟡    │  │   🟢    │  │   🔴    │             │
│  │Developing│  │  Strong │  │Needs Work│            │
│  └─────────┘  └─────────┘  └─────────┘             │
└──────────────────────────────────────────────────────┘
```

**Quick overview cards** — one per subject, click to go to `ChildProgressPage` filtered to that subject.

---

### `ChildProgressPage.tsx` — route: `/parent/children/:studentId/progress`

```
┌──────────────────────────────────────────────────────┐
│  [← Dashboard]  Emma Wilson · Grade 9                │
│                                                      │
│  [Mathematics] [Science] [English Language]  ← tabs  │
│                                                      │
│  Progress Overview                                   │
│  ┌─ SimpleGapMap ───────────────────────────────┐   │
│  │  Algebra          🟡 Developing              │   │
│  │  Geometry         🟢 Strong                  │   │
│  │  Fractions        🔴 Needs Work              │   │
│  │  Statistics       🟢 Strong                  │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  Weekly Reports                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │ ▼ Week of 2 Mar 2026   (click to expand)   │    │
│  │   [WeeklyReportCard — full narrative]       │    │
│  ├─────────────────────────────────────────────┤    │
│  │ ▶ Week of 23 Feb 2026                       │    │
│  ├─────────────────────────────────────────────┤    │
│  │ ▶ Week of 16 Feb 2026                       │    │
│  └─────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

---

## Component Details

### `ChildSelector.tsx`
- Only rendered when parent has 2+ children
- Dropdown on mobile, tabs on desktop (≥768px)
- Changing selection navigates to `/parent/children/{studentId}/progress`

### `TopicTrafficLight.tsx`
```tsx
interface TopicTrafficLightProps {
  topicName: string
  status: "Strong" | "Developing" | "Needs Work"
  statusLabel: "green" | "amber" | "red"
}

// Render:
// - Filled circle: green=#10B981, amber=#F59E0B, red=#EF4444
// - Topic name in bold
// - Status text below (smaller, muted)
// - NEVER show numeric scores — only visual + text label
// - Include aria-label for accessibility: "Algebra: Developing"
```

### `SimpleGapMap.tsx`
```tsx
// Renders a list of TopicTrafficLight rows
// Sorted: Needs Work first, then Developing, then Strong
// (Most urgent at top — parents should see what needs attention first)
// "Last updated: [date]" shown at bottom in small muted text
```

### `WeeklyReportCard.tsx`
```tsx
// Accordion item — collapsed by default except the most recent
// Header shows: week date, subject name
// Expanded content:
//   - Full narrative text
//   - "Highlights this week:" bullet list (from highlights array)
// No scores, no percentages anywhere
```

### `NarrativeCard.tsx`
```tsx
// Dashboard highlight card — most recent report only
// Truncates narrative to 3 lines with "Read more →" link
// Displayed with a warm background (e.g. bg-role-parent-bg (#fdf8f0) — warm cream, see DESIGN_SYSTEM.md §5.5)
```

---

## `useParentData.ts` Hooks

```ts
const useParentChildren = () =>
  useQuery({
    queryKey: ["parent", "children"],
    queryFn: () => apiClient.get("/parent/children"),
  })

const useChildReports = (studentId: string) =>
  useQuery({
    queryKey: ["parent", "reports", studentId],
    queryFn: () => apiClient.get(`/parent/children/${studentId}/reports?limit=10`),
    enabled: !!studentId,
  })

const useChildGapMap = (studentId: string) =>
  useQuery({
    queryKey: ["parent", "gap-map", studentId],
    queryFn: () => apiClient.get(`/parent/children/${studentId}/gap-map`),
    enabled: !!studentId,
  })
```

---

## Mobile-First Rules

- All layouts must work at 375px width
- Touch targets ≥ 44px height
- No horizontal overflow — all cards stack vertically on mobile
- Subject tabs scroll horizontally on narrow screens (overflow-x: auto)
- Accordion rows have ≥ 48px tap targets

---

## Accessibility

- All traffic-light circles have `aria-label` — colour alone is never the only indicator
- Status text always accompanies colour: "🟡 Developing" — screen reader reads "Developing"
- Accordion uses `aria-expanded` and `aria-controls`
- Child selector uses native `<select>` on mobile for accessibility

---

## Acceptance Criteria

- [ ] E2E test: parent logs in → sees dashboard with latest narrative and subject overview
- [ ] E2E test: parent clicks subject overview card → navigates to ChildProgressPage
- [ ] E2E test: traffic-light grid shows correct colours matching status from API
- [ ] E2E test: parent clicks accordion → weekly report expands with full narrative
- [ ] E2E test: parent with 2 children → ChildSelector shown; switching child updates all data
- [ ] E2E test: parent with 1 child → ChildSelector NOT shown
- [ ] Unit test: `TopicTrafficLight` with status="Needs Work" → red circle renders
- [ ] Unit test: `SimpleGapMap` sorts Needs Work topics before Strong topics
- [ ] Unit test: `NarrativeCard` truncates long narrative and shows "Read more" link
- [ ] Responsive: dashboard correct at 375px (no overflow, no cut-off text)
- [ ] Responsive: progress page tabs scroll correctly at 375px
- [ ] Accessibility: `TopicTrafficLight` aria-label includes topic name and status text

---

## Output (what M6 needs)

- Parent portal fully functional and tested
- Parents can access their children's progress independently (reduces teacher support burden)
- Weekly email delivery confirmed working end-to-end (Resend → parent inbox)
- `parent_report_snapshots` table has real data for M6 analytics to count
