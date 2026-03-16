# M0-7-T2 — Teacher Dashboard
**Milestone:** M0 — Foundations
**Epic:** M0-7 — Frontend Foundations
**Task ID:** M0-7-T2
**Depends on:** M0-8-T3 (packages/types mastery helper), M0-7-T1 (layout wrappers), M0-4-T3 (grade/class API), M0-3-T4 (auth frontend)

REASON: ClassCard uses `getMasteryStyle()` from `@kaihle/types` (created by M0-8-T3).
Without M0-8-T3, the import will fail to resolve at build time.

ALSO ADD this implementation note to the ClassCard section (after the card layout spec):

```
Implementation note:
  Use getMasteryStyle() from @kaihle/types to derive color classes — do not hardcode.
  import { getMasteryStyle, scoreToPercent } from '@kaihle/types'

  const { dotClass, textClass, label } = getMasteryStyle(avgMastery)
  // dotClass  → e.g. 'bg-brand-amber'  (for the mastery dot)
  // textClass → e.g. 'text-brand-amber' (for the percentage text)
  // label     → e.g. 'Developing'       (for the status text)
  const displayPct = scoreToPercent(avgMastery)  // → "61%" or "—"
```
**Blocks:** Nothing — but this is the landing page after teacher login
**Estimated effort:** 3–4 hours

---

## Context

`/teacher/dashboard` is currently a placeholder. This is the first page a teacher sees
every day. It needs to be genuinely useful as a daily starting point: show which classes
exist, surface any urgent gaps or pending actions, and make the most common actions
(create assessment, view gap map) one click away.

Read `docs/design/DESIGN_SYSTEM.md` §5.3 (Teacher) before writing any code.
Use `DashboardLayout variant="teacher"` from `packages/ui`.

---

## User Story

As a teacher, when I log in I want to immediately see the health of my classes and
know what needs attention today, so I can start my day without hunting through menus.

---

## Files to Create

```
frontend/apps/teacher/src/pages/dashboard/
  TeacherDashboard.tsx          ← main page
  ClassCard.tsx                 ← one card per class
  PendingActionBanner.tsx       ← urgent attention prompts

frontend/apps/teacher/src/hooks/
  useTeacherDashboard.ts        ← React Query data hooks

frontend/apps/teacher/src/tests/
  teacher-dashboard.spec.ts     ← Playwright E2E
```

---

## Route

`/teacher/dashboard` — default landing after login for TEACHER role.
School Admins landing here → redirect to `/school/overview`.

---

## Page Layout

```
┌──────────────────────────────────────────────────────────────┐
│  TOPNAV: Good morning, Ms. Ravi  [+ Assessment] [avatar]     │
├───────────────┬──────────────────────────────────────────────┤
│  SIDEBAR      │                                              │
│               │  ── Pending actions (conditional) ─────────  │
│  Dashboard ●  │  ┌──────────────────────────────────────┐   │
│  Gap Map      │  │  ⚠  4 students need study plans     │   │
│  Assessments  │  │  assigned in Mathematics 9B          │   │
│  ...          │  │                              [Go →]  │   │
│               │  └──────────────────────────────────────┘   │
│               │                                              │
│               │  ── My classes ──────────────────────────    │
│               │  ┌──────────────┐  ┌──────────────┐         │
│               │  │ Maths 9B     │  │ Maths 8A     │         │
│               │  │ 28 students  │  │ 24 students  │         │
│               │  │ Avg: 61% 🟡  │  │ Avg: 74% 🟢  │         │
│               │  │ ─────────── │  │ ────────────  │         │
│               │  │ [Gap Map]   │  │ [Gap Map]    │         │
│               │  │ [Assess]    │  │ [Assess]     │         │
│               │  └──────────────┘  └──────────────┘         │
│               │                                              │
│               │  ── This week ───────────────────────────    │
│               │  ┌────────────────────────────────────┐     │
│               │  │ Lesson plan ready · Maths 9B       │     │
│               │  │ Plan covers: Algebra, Statistics   │     │
│               │  │                     [View plan →]  │     │
│               │  └────────────────────────────────────┘     │
└───────────────┴──────────────────────────────────────────────┘
```

---

## Pending Action Banner (`PendingActionBanner.tsx`)

Shown only when there is something requiring the teacher's attention. Never shown if empty.

Conditions that trigger a banner (show the first matching one):
1. A class has students with no study plans and mastery < 0.4 → "N students need study plans in [Class]"
2. A published assessment has been completed but results not yet reviewed → "N students completed [Assessment] — view results"
3. No assessments have been created for a class yet → "No assessments yet for [Class] — create one to see gaps"

Banner style:
```
bg-brand-gold-light border border-brand-gold-mid rounded-xl p-4
flex items-center justify-between
Left: warning icon (Lucide AlertTriangle w-5 h-5 text-brand-gold) + message text
Right: text link "Go →" in brand-gold
```

---

## Class Cards (`ClassCard.tsx`)

One card per class the teacher is assigned to. Fetched from `GET /api/v1/schools/{school_id}/classes?teacher_id=me`.

```tsx
interface ClassCardProps {
  classId: string
  className: string       // e.g. "Mathematics 9B"
  subjectName: string
  gradeName: string
  studentCount: number
  avgMastery: number | null   // null if no assessments yet
  lessonPlanStatus: 'ready' | 'generating' | 'none'
}
```

Card layout:
```
bg-white rounded-2xl border border-role-teacher-border p-5
hover:-translate-y-0.5 hover:shadow-card-hover transition-all

Top row: Subject icon (colored dot per DESIGN_SYSTEM §9) + class name (font-display font-semibold)
         + grade badge (pill)

Middle: Student count + mastery score with getMasteryStyle() color

Divider line

Bottom: Two action links side by side:
  [Gap Map →]    → /teacher/classes/:classId/gap-map
  [Assessment →] → /teacher/classes/:classId/assessments
  Both: text-sm font-semibold text-brand-body hover:text-brand-primary
```

Empty state (no gap data yet):
```
Middle shows: "No assessments yet"
getMasteryStyle(null) → text-brand-muted "—"
```

---

## This Week Card

Shown if at least one class has a lesson plan with status `GENERATED` or `EDITED`.

```
bg-brand-light rounded-xl border border-brand-mid p-4
Left: book icon + "Lesson plan ready · [Class name]"
Sub: "Covers: [topic 1], [topic 2]"   (truncated to 2 topics)
Right: "View plan →" link → /teacher/classes/:classId/lesson-plans
```

If all classes have `lesson_plan_status = 'none'`:
```
Show: "Lesson plans generate every Monday at 6am. Create assessments first to get started."
```

---

## Data (`useTeacherDashboard.ts`)

```typescript
// Queries needed:
// 1. GET /api/v1/schools/{school_id}/classes?teacher_id=me
// 2. GET /api/v1/schools/{school_id}/analytics  (for avg mastery per class)
// 3. GET /api/v1/classes/{classId}/lesson-plans?limit=1  (per class, parallelised)

// React Query keys:
const QUERY_KEYS = {
  classes: (schoolId: string) => ['teacher', 'classes', schoolId],
  dashboard: (schoolId: string) => ['teacher', 'dashboard', schoolId],
}
```

Show skeleton cards while loading. Never show blank space.

---

## Acceptance Criteria

- [ ] E2E: teacher logs in → lands on `/teacher/dashboard`
- [ ] E2E: teacher with 2 classes → sees 2 class cards
- [ ] E2E: class with avg mastery < 0.4 → card shows red mastery band
- [ ] E2E: pending action banner appears when students need study plans
- [ ] E2E: pending action banner NOT shown when no pending actions
- [ ] E2E: "Gap Map →" link navigates to correct class gap map
- [ ] E2E: School Admin role → redirected to `/school/overview`
- [ ] Unit: `ClassCard` with `avgMastery=0.38` → renders red `text-brand-red` "38%"
- [ ] Unit: `ClassCard` with `avgMastery=null` → renders muted "—" (not "0%")
- [ ] Unit: `PendingActionBanner` with no actions → renders `null` (nothing)
- [ ] Responsive: cards are 1-column at 375px, 2-column at md:, 3-column at xl:
- [ ] Skeleton cards shown during loading (not blank space, not spinner)
- [ ] Design: uses `DashboardLayout variant="teacher"` — no custom layout shell
- [ ] Design: gold `[+ Assessment]` button in topnav
