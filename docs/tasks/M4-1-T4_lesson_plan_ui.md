# M4-1-T4 — Lesson Plan UI (Teacher App) (UPDATED)

**Milestone:** M4 — Teacher Copilot
**Epic:** M4-1 — Lesson Plan Generation
**Task ID:** M4-1-T4
**Depends on:** M4-1-T3 (all lesson plan API endpoints)
**Blocks:** Nothing — last task of M4

> **UPDATED March 2026:** Layout spec replaced with rich anatomy matching
> the lesson plan output quality now produced by the updated prompt (M4-1-T1).
> Previous layout (4-section flat view with StudentGroupTabs as primary structure)
> is deprecated — do NOT build it.
> New layout: header card → diagnostic gap strip → timeline spine →
> learning objectives + resources grid → teacher notes.
> Reference mockup: Pixel's `kaihle_teacher_lesson_plan_view` widget (March 2026).

---

## User Story

As a teacher, I want to view my weekly AI-generated lesson plan in a clear, structured
layout — seeing which diagnostic gaps are targeted, the full lesson timeline with
activity details, and the resources I need — so I can pick it up and teach it without
further prep work.

---

## Files To Create

```
/frontend/apps/teacher/src/
  pages/
    lesson-plans/
      LessonPlansPage.tsx           ← main page (route: /teacher/classes/:classId/lesson-plans)
      LessonPlanDetail.tsx          ← full plan view (current week) — PRIMARY new component
      LessonPlanHistory.tsx         ← accordion list of past plans (unchanged from original spec)
  components/
    lesson-plans/
      PlanHeaderCard.tsx            ← title, AI badge, chips, stat pills
      DiagnosticGapStrip.tsx        ← gap list with mastery dots + where/when labels
      LessonTimeline.tsx            ← vertical timeline spine
      TimelineItem.tsx              ← single activity block
      LearningObjectivesGrid.tsx    ← 2-col LO grid with Cambridge code badges
      ResourceList.tsx              ← resource items with icons
      TeacherNotesCard.tsx          ← gold left-border note blocks
      PlanStatusBadge.tsx           ← GENERATED | EDITED | USED | ARCHIVED
      RegenerateModal.tsx           ← confirm before regenerating
      EditableSection.tsx           ← click-to-edit inline field (for timeline descriptions)
  hooks/
    useLessonPlans.ts               ← React Query hooks for all lesson plan endpoints
  types/
    lessonPlan.ts                   ← TypeScript interfaces mirroring Pydantic schema
```

---

## TypeScript Types (`types/lessonPlan.ts`)

```typescript
export type LessonPhase =
  | 'warmup' | 'bridge' | 'station' | 'debrief' | 'exit' | 'activity'

export type LearningStyleSlug =
  | 'visual' | 'kinesthetic' | 'auditory' | 'reading_writing' | 'mixed'

export type PlanStatus = 'GENERATED' | 'EDITED' | 'USED' | 'ARCHIVED'

export interface LearningObjective {
  code: string         // e.g. "7Pf.01"
  description: string
}

export interface DiagnosticGapTarget {
  gap_description: string
  addressed_where: string
  addressed_how:   string
  mastery_band?:   'needs_work' | 'developing' | null
}

export interface TimelineItemData {
  phase:          LessonPhase
  start_min:      number
  duration_min:   number
  title:          string
  description:    string
  gap_targeted?:  string | null
  kinesthetic_tag?: string | null
  assess_tag?:    string | null
}

export interface ResourceItem {
  description: string
}

export interface LessonPlanData {
  week_start:          string   // "YYYY-MM-DD"
  class_summary:       string
  learning_style:      LearningStyleSlug
  lesson_duration_min: number
  learning_objectives: LearningObjective[]
  diagnostic_gaps:     DiagnosticGapTarget[]
  timeline:            TimelineItemData[]
  resources:           ResourceItem[]
  teacher_notes:       string
  student_groups?:     Record<string, { count: number; focus: string }> | null
}

export interface LessonPlanResponse {
  id:           string
  class_id:     string
  week_start:   string
  status:       PlanStatus
  plan:         LessonPlanData
  generated_at: string
  ai_model:     string   // e.g. "claude-sonnet-4-6" — shown in AI badge
}

export interface LessonPlanSummary {
  id:            string
  week_start:    string
  status:        PlanStatus
  class_summary: string
  learning_style: LearningStyleSlug
  gap_count:     number
  generated_at:  string
}
```

---

## Page Layout: `LessonPlansPage.tsx`

Route: `/teacher/classes/:classId/lesson-plans`

```
┌──────────────────────────────────────────────────────────────────┐
│  Topbar breadcrumb: Lesson Plans › [Subject] › [Topic]           │
│  Topbar actions:  [Regenerate]  [Preview]  [Mark as used ▸]      │
├──────────────────────────────────────────────────────────────────┤
│  This Week's Plan  (week of DD Mon YYYY)                         │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  LessonPlanDetail  (see section below)                     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Previous Plans                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  LessonPlanHistory  (accordion — unchanged from v1 spec)   │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

**Loading state:** Skeleton cards (use `bg-gray-100 animate-pulse rounded-lg`).
**Empty state:** "No lesson plan yet for this week. Plans generate every Monday at 6am."
  with a `[Generate now]` gold button → calls `POST /lesson-plans/:mostRecentId/regenerate`
  or, if no plan exists at all, `POST /classes/:classId/lesson-plans/generate`.

---

## `LessonPlanDetail.tsx` — Full Component Anatomy

### Section 1: `PlanHeaderCard`

```
┌─────────────────────────────────────────────────────────────────┐
│  [AI badge: • AI-generated · claude-sonnet-4-6]                 │
│                                                                 │
│  Forces and Motion                          ┌──────┐ ┌──────┐  │
│  Cambridge Lower Secondary — Stage 7 ·      │  4   │ │  5   │  │
│  Kinesthetic · 60 min                       │ Obj. │ │ Act. │  │
│                                             └──────┘ └──────┘  │
│  [Physics] [Stage 7] [Kinesthetic] [3 gaps targeted]      ┌──┐  │
│                                                           │ 3 │  │
│                                                           │gaps│  │
│                                                           └──┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Tokens to use:**
- AI badge: `bg-brand-gold-light text-brand-gold-dark` pill with gold dot
- Title: `font-display font-bold text-2xl text-brand-ink` (Fraunces)
- Subtitle: `text-sm text-brand-body`
- Stat pills: `bg-brand-bg rounded-lg px-4 py-2 text-center`
  - "gaps fixed" pill: `bg-brand-green-light text-brand-primary`
- Chips: `bg-brand-bg border border-brand-border text-brand-body text-xs font-semibold rounded-md px-2 py-1`
- Kinesthetic chip: `bg-brand-gold-light border-brand-gold-mid text-brand-gold-dark`
- Gaps chip: `bg-brand-green-light border-brand-mid text-brand-primary`

**`ai_model` display rules:**
- `claude-sonnet-4-6` → "Claude Sonnet 4.6"
- `gemini-2.5-pro` → "Gemini 2.5 Pro"
- `deepseek-chat` → "DeepSeek Chat"
- Fallback: display raw string, strip `openrouter/` prefix

---

### Section 2: `DiagnosticGapStrip`

```
DIAGNOSTIC GAPS TARGETED
● Confusing mass and weight                 Station 1 · Teacher checkpoint min 15
● Difficulty reading distance-time graphs   Station 3 · Exit Task Part C
○ Unit conversion errors (km/h vs m/s)      Station 2 · Speed Slider manipulative
```

**Dot colors:**
- `mastery_band === 'needs_work'` → `bg-brand-red` (filled dot)
- `mastery_band === 'developing'` → `bg-brand-amber` (filled dot)
- `mastery_band === null` → `bg-brand-muted` (outline dot)

**Layout:** `flex items-center gap-3` per row. Gap description `font-medium text-brand-ink flex-1`. Where label `text-xs text-brand-muted text-right`.

---

### Section 3: `LessonTimeline`

Vertical timeline. Each item rendered by `TimelineItem`.

```
0 min  ●  Warm-up · 5 min
       │  Force Freeze — Body Simulation
       │  Students respond to force types with full-body movements...
       │  [Kinesthetic opener]
       │
5 min  ●  Bridge · 3 min
       │  Rope Tug — Balanced vs Unbalanced Forces
       ...
8 min  ●  Station 1 · 12 min
       │  Mass vs Weight — Feel the Difference
       │  [Gap: mass vs weight]
       │
...
50 min ●  Exit Task · 10 min
          3-Part Kinesthetic Assessment
          [Diagnostic data collected]
```

**`TimelineItem` dot colors by phase:**
```typescript
const PHASE_DOT: Record<LessonPhase, string> = {
  warmup:   'bg-brand-amber',
  bridge:   'bg-brand-muted',
  station:  'bg-brand-gold',
  debrief:  'bg-brand-primary',
  exit:     'bg-brand-primary',
  activity: 'bg-brand-gold',
}
```

**Phase label colors:**
```typescript
const PHASE_LABEL: Record<LessonPhase, string> = {
  warmup:   'text-brand-gold-dark',
  bridge:   'text-brand-muted',
  station:  'text-brand-gold-dark',
  debrief:  'text-brand-primary',
  exit:     'text-brand-primary',
  activity: 'text-brand-gold-dark',
}
```

**Tags:**
- `gap_targeted` is set → `bg-brand-red-light text-red-800 text-xs font-semibold px-2 py-0.5 rounded`
- `kinesthetic_tag` is set → `bg-brand-gold-light text-brand-gold-dark text-xs font-semibold px-2 py-0.5 rounded`
- `assess_tag` is set → `bg-brand-green-light text-brand-primary text-xs font-semibold px-2 py-0.5 rounded`

**Connector line:** `w-px bg-brand-border flex-1 my-1` (vertical line between dots)

**Hover state:** `hover:bg-brand-bg rounded-lg transition-colors duration-100` on body div

**`EditableSection` integration:** Wrap `description` text in `EditableSection`.
On click → textarea with `border border-brand-gold rounded-md`. On blur → `PATCH /lesson-plans/:id`
with `{ timeline_edits: { [index]: updatedDescription } }`. Plan status badge updates to EDITED.

---

### Section 4: Two-column grid — `LearningObjectivesGrid` + `ResourceList`

```
grid grid-cols-2 gap-4
```

**`LearningObjectivesGrid`:**
- 2-column inner grid `grid grid-cols-2 gap-2`
- Each item: `bg-brand-bg rounded-lg p-2 flex gap-2`
- Code badge: `bg-brand-green-light text-brand-primary text-xs font-bold px-2 py-0.5 rounded`
- Description: `text-xs text-brand-body leading-relaxed`

**`ResourceList`:**
- Each row: `flex items-center gap-2 text-xs text-brand-body`
- Icon container: `w-6 h-6 bg-brand-bg rounded-md flex items-center justify-center`
- Use lucide-react icons: `FileText`, `Ruler`, `SquarePen`, `Layers`, `CheckSquare`
  (cycle through or map by keyword in description)

---

### Section 5: `TeacherNotesCard`

Each sentence of `teacher_notes` split on `\n` or double-space.
Each note rendered as:
```
border-l-[3px] border-brand-gold bg-brand-gold-light/40 rounded-r-lg px-3 py-2
text-xs text-brand-body leading-relaxed
```
First sentence bolded: extract up to first `:` as `<strong>` label.

---

## `PlanStatusBadge.tsx`

```typescript
const STATUS_STYLES: Record<PlanStatus, string> = {
  GENERATED: 'bg-brand-bg text-brand-muted border border-brand-border',
  EDITED:    'bg-brand-gold-light text-brand-gold-dark border border-brand-gold-mid',
  USED:      'bg-brand-green-light text-brand-primary border border-brand-mid',
  ARCHIVED:  'bg-gray-100 text-gray-400 border border-gray-200',
}
```

Render as small pill `text-xs font-semibold px-2 py-0.5 rounded-full`.

---

## `RegenerateModal.tsx`

Trigger: "Regenerate" button in topbar.

```
┌─────────────────────────────────────┐
│  Regenerate lesson plan?            │
│                                     │
│  This will discard the current      │
│  plan and any edits you've made.    │
│  A new plan will be generated       │
│  using today's gap data.            │
│                                     │
│       [Cancel]    [Regenerate ▸]    │
└─────────────────────────────────────┘
```

- Cancel: `btn-ghost` (secondary)
- Regenerate: `bg-brand-gold text-white rounded-full` (gold primary)
- On confirm → `POST /lesson-plans/:id/regenerate` → loading spinner in button → refetch plan

---

## `useLessonPlans.ts`

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/apiClient'
import type { LessonPlanResponse, LessonPlanSummary } from '../types/lessonPlan'

export const useLessonPlanList = (classId: string) =>
  useQuery<LessonPlanSummary[]>({
    queryKey: ['lesson-plans', classId],
    queryFn: () => apiClient.get(`/classes/${classId}/lesson-plans`),
  })

export const useLessonPlan = (planId: string) =>
  useQuery<LessonPlanResponse>({
    queryKey: ['lesson-plan', planId],
    queryFn: () => apiClient.get(`/lesson-plans/${planId}`),
  })

export const useEditLessonPlan = (planId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { timeline_edits?: Record<number, string>; teacher_notes?: string }) =>
      apiClient.patch(`/lesson-plans/${planId}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['lesson-plan', planId] })
    },
  })
}

export const useRegenerateLessonPlan = (planId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiClient.post(`/lesson-plans/${planId}/regenerate`, {}),
    onSuccess: (data: LessonPlanResponse) => {
      qc.setQueryData(['lesson-plan', data.id], data)
      qc.invalidateQueries({ queryKey: ['lesson-plans'] })
    },
  })
}

export const useMarkLessonPlanUsed = (planId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiClient.patch(`/lesson-plans/${planId}/status`, { status: 'USED' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['lesson-plan', planId] })
      qc.invalidateQueries({ queryKey: ['lesson-plans'] })
    },
  })
}
```

---

## Design System Compliance Checklist

Pixel will reject a PR that fails any of these:

- [ ] No `indigo-*` or `emerald-*` classes anywhere in lesson plan components
- [ ] No green buttons — "Mark as used" and "Regenerate" are `bg-brand-gold`
- [ ] Plan title uses `font-display` (Fraunces) — not `font-sans`
- [ ] Cambridge objective code badges use `bg-brand-green-light text-brand-primary`
- [ ] Mastery dots use `bg-brand-red` / `bg-brand-amber` / `bg-brand-muted` — never Tailwind defaults
- [ ] `EditableSection` focus ring: `focus-visible:ring-2 focus-visible:ring-brand-primary`
- [ ] All interactive elements min `44px` touch target
- [ ] `aria-label` on all mastery color indicators
- [ ] `PlanStatusBadge` renders correct color for each of 4 states

---

## Acceptance Criteria

- [ ] E2E: teacher navigates to `/teacher/classes/:id/lesson-plans` → sees current week's plan
- [ ] E2E: `PlanHeaderCard` displays AI model badge, title, subject chips, stat pills
- [ ] E2E: `DiagnosticGapStrip` shows all gaps with `addressed_where` label
- [ ] E2E: `LessonTimeline` renders all timeline items in order with correct phase dots
- [ ] E2E: clicking a timeline item description → `EditableSection` activates → blur → PATCH sent
- [ ] E2E: `PlanStatusBadge` updates to EDITED after a timeline edit is saved
- [ ] E2E: clicking "Regenerate" opens `RegenerateModal` → confirming calls regenerate endpoint
- [ ] E2E: "Mark as used" gold button → `PATCH /status` → badge updates to USED
- [ ] Unit: `PlanStatusBadge` renders correct class string for each `PlanStatus` value
- [ ] Unit: `ai_model` display helper strips "openrouter/" prefix correctly
- [ ] `tsc --noEmit` passes with zero errors in teacher app
