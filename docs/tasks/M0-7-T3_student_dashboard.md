# M0-7-T3 — Student Dashboard
**Milestone:** M0 — Foundations
**Epic:** M0-7 — Frontend Foundations
**Task ID:** M0-7-T3
**Depends on:** M0-8-T3 (packages/types mastery helper), M0-7-T1 (layout wrappers), M0-6-T3 (onboarding completion), M0-3-T4 (auth frontend)

REASON: SubjectScoreCard derives border and text classes from mastery scores using
getMasteryStyle() from @kaihle/types (created by M0-8-T3).

**Blocks:** Nothing — but this is the post-onboarding landing for students
**Estimated effort:** 3–4 hours

---

## Context

`/student/dashboard` is currently a placeholder unlocked only after onboarding completes.
This page needs to be a genuine daily companion for a student: show their subject scores
at a glance, surface what's waiting for them (study plans, new assessments), and make
them feel progress rather than just showing them a wall of data.

Read `docs/design/DESIGN_SYSTEM.md` §5.4 (Student) before writing any code.
Use `StudentLayout` from `packages/ui`. This is a mobile-first page.

---

## User Story

As a student who just completed onboarding, I want a home screen that shows my overall
progress and tells me what to do next, without overwhelming me with data.

---

## Files to Create

```
frontend/apps/student/src/pages/dashboard/
  StudentDashboard.tsx          ← main page
  SubjectScoreCard.tsx          ← compact subject card with colored border
  NextStepCard.tsx              ← single action card ("You have N study plans")
  StreakBadge.tsx               ← consecutive days active (optional, shows if > 1)

frontend/apps/student/src/hooks/
  useStudentDashboard.ts        ← React Query data hooks

frontend/apps/student/src/tests/
  student-dashboard.spec.ts     ← Playwright E2E
```

---

## Route

`/student/dashboard` — the destination after onboarding completes and on every login
once onboarding is done. Protected by `OnboardingRoute`.

---

## Page Layout

```
┌──────────────────────────────────────────┐
│  TOPNAV: Kaihle logo  [Progress][Study]  │   ← horizontal nav tabs on desktop
├──────────────────────────────────────────┤
│  p-4                                     │
│                                          │
│  Hi Emma 👋                              │   ← greeting, Fraunces font
│  Grade 9 · Cambridge IGCSE               │   ← muted subtitle
│                                          │
│  ┌────────┐ ┌────────┐ ┌────────┐        │   ← subject score cards
│  │ MATHS  │ │SCIENCE │ │ENGLISH │        │
│  │  72%   │ │  58%   │ │  81%   │        │
│  │ Strong │ │Develop.│ │ Strong │        │
│  └────────┘ └────────┘ └────────┘        │
│                                          │
│  ── What's waiting for you ──────────── │
│  ┌──────────────────────────────────┐   │
│  │ 📚 2 study plans ready           │   │
│  │ Start learning where it counts   │   │
│  │                   [View plans →] │   │
│  └──────────────────────────────────┘   │
│                                          │
│  ┌──────────────────────────────────┐   │
│  │ 📝 1 assessment due              │   │
│  │ Mathematics · Due 15 March       │   │
│  │                  [Start now →]  │   │
│  └──────────────────────────────────┘   │
│                                          │
│  ── Keep going ──────────────────────── │
│  Your weakest area: Statistics (38%)    │
│  [See what to work on →]                │
│                                          │
├──────────────────────────────────────────┤
│  BOTTOM NAV (mobile): Home|Progress|     │
│                        Study|Assess      │
└──────────────────────────────────────────┘
```

---

## Greeting (`StudentDashboard.tsx`)

```tsx
// Format: "Good morning/afternoon/evening, [first name]"
// Time-based:  0-11  → "Good morning"
//             12-17  → "Good afternoon"
//             18-23  → "Good evening"

// Subtitle: "{gradeName} · {curriculumName}"
// e.g. "Grade 9 · Cambridge IGCSE"
```

Typography:
```
Greeting: font-display font-bold text-2xl text-brand-ink
Subtitle: font-sans text-sm text-brand-muted mt-1
```

---

## Subject Score Cards (`SubjectScoreCard.tsx`)

Compact 3-column grid. Border color derived from mastery band.

```tsx
interface SubjectScoreCardProps {
  subjectName: string     // "Mathematics"
  subjectCode: string     // "MATH" (drives icon color, see DESIGN_SYSTEM §9)
  score: number | null    // 0.0–1.0
}
```

Card layout:
```
bg-white rounded-2xl border-[1.5px] {masteryBorderClass} p-4 text-center

Value:   text-2xl font-extrabold {masteryTextClass}  — score as integer %
Label:   text-xs font-bold uppercase tracking-wide text-brand-muted mt-1
Status:  text-xs text-brand-muted mt-0.5  — "Strong" / "Developing" / "Needs Work"
```

Border color — use getMasteryStyle() from @kaihle/types, then map bgClass to a
border variant. Do NOT inline this mapping in the component:

```typescript
import { getMasteryStyle, scoreToPercent } from '@kaihle/types'

// Map mastery bgClass to colored border class:
const borderClassMap: Record<string, string> = {
  'bg-brand-green-light':  'border-brand-mid',        // green border
  'bg-brand-amber-light':  'border-brand-gold-mid',   // gold border
  'bg-brand-red-light':    'border-brand-red/30',     // soft red border
  'bg-gray-50':            'border-brand-border',     // not assessed
}

const { bgClass, textClass, label } = getMasteryStyle(score)
const borderClass = borderClassMap[bgClass] ?? 'border-brand-border'
const displayPct = scoreToPercent(score)   // "72%" or "—"
```

---

## Next Step Cards (`NextStepCard.tsx`)

Shown in priority order — highest priority first. Maximum 3 cards total.

Priority rules:
1. Active assessments due within 7 days → "N assessment due · [Subject]"
2. Study plans with status `ACTIVE` (not yet started) → "N study plans ready"
3. Study plans with status `IN_PROGRESS` (started but not finished) → "Continue your study plan"
4. Weakest subject (lowest mastery score) with no active study plan → "Your weakest area: [topic] ([pct]%)"

Each card:
```
bg-white rounded-2xl border border-role-student-border p-4
flex items-center justify-between

Left:  emoji (📝 assessment / 📚 study plan / 📈 progress) + title text (font-semibold text-brand-ink)
       + subtitle (text-xs text-brand-muted)
Right: "[Action →]" link — text-sm font-bold text-brand-primary
```

Empty state (no pending actions — unlikely but possible):
```
bg-brand-light rounded-2xl p-4 text-center
"You're all caught up! Check back after your next assessment."
```

---

## Data (`useStudentDashboard.ts`)

```typescript
// Queries:
// 1. GET /api/v1/students/me/gap-map  → subject scores
// 2. GET /api/v1/students/me/study-plans?status=active,in_progress&limit=10
// 3. GET /api/v1/classes/{classId}/assessments?status=ACTIVE&limit=5

// Derive from gap-map response:
// - Subject scores (aggregate mastery per subject from subtopic scores)
// - Weakest subject: min(subjectAverages) where score is not null

// React Query keys:
const QUERY_KEYS = {
  dashboard: (studentId: string) => ['student', 'dashboard', studentId],
  gapMap:    (studentId: string) => ['student', 'gap-map', studentId],
}
```

---

## Acceptance Criteria

- [ ] E2E: student who completed onboarding lands on `/student/dashboard`
- [ ] E2E: student without onboarding complete → redirected to `/student/onboarding`
- [ ] E2E: 3 subject score cards render with correct mastery colors
- [ ] E2E: card with score 0.72 → green border + "72%" + "Strong"
- [ ] E2E: subject with no data → shows "—" not "0%"
- [ ] E2E: active study plan card shows with "View plans →" link
- [ ] E2E: active assessment card shows with "Start now →" link
- [ ] E2E: no pending actions → shows "You're all caught up!" message
- [ ] Unit: greeting uses time-of-day ("Good morning" before noon)
- [ ] Unit: `SubjectScoreCard` score=0.38 → `border-brand-red/30` + red value text
- [ ] Unit: `SubjectScoreCard` score=null → neutral border + "—" value + "Not assessed"
- [ ] Responsive: 3-column card grid at all screen sizes ≥375px (use `grid-cols-3`)
- [ ] Responsive: NextStep cards stack vertically, full width on mobile
- [ ] Mobile: bottom nav visible and correct (md:hidden on bottom nav)
- [ ] Design: uses `StudentLayout` — no custom layout shell
- [ ] Design: greeting uses `font-display`, subject labels use Nunito
- [ ] Skeleton cards shown during loading
