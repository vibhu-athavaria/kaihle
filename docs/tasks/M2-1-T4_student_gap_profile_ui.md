# M2-1-T4 — Student Gap Profile UI
**Milestone:** M2 · **Epic:** M2-1 · **Task:** T4
**Depends on:** M2-1-T2 (gap map routes), M0-3-T4 (auth frontend)

---

## User Story
As a student, I want to see my own progress in each subject with clear visual indicators so I know where I'm strong and where I need to focus.

---

## Files to Create

```
frontend/apps/student/src/pages/progress/MyProgress.tsx
frontend/apps/student/src/pages/progress/SubjectProgress.tsx
frontend/apps/student/src/hooks/useStudentGapMap.ts
frontend/apps/student/src/tests/my-progress.spec.ts
```

---

## Route

`/student/my-progress`

---

## Layout

```
┌──────────────────────────────────────────┐
│  My Progress                             │
│                                          │
│  [Mathematics] [Science] [English]       │  ← subject tabs
│                                          │
│  ALGEBRA                                 │
│  ├── Algebraic Fractions   🟡  65%  →   │
│  ├── Quadratics            🟢  82%  →   │
│  └── Linear Equations      🔴  38%  →   │
│                                          │
│  GEOMETRY                                │
│  ├── Pythagoras Theorem    🟡  58%  →   │
│  └── Area & Perimeter      ⬜  —        │  ← not yet assessed
│                                          │
│  ─── Suggested Next Steps ───            │
│  📚 You have 2 study plans waiting       │
│  [Go to Study Plans →]                   │
└──────────────────────────────────────────┘
```

---

## Topic Groups

- Topics used as section headers (from `topic_name` in gap map nodes)
- Subtopics listed under each topic as rows
- Each row:
  - Traffic light circle (colour matches CONSTITUTION §10)
  - Subtopic name
  - Score label: `65%` (not shown as 0.65 — always convert to percentage)
  - **IMPORTANT:** If not assessed → show `—` not `0%` — these are different things
  - Chevron → expands to show "Last assessed: 2 Mar 2026" and a sparkline (simple bar chart of last 3 scores if data exists)
  - Accessibility: colour circle has `aria-label="Developing"` — not colour only

---

## Colour + Label Mapping (Client-side)

Do NOT define this function locally. Import from the shared types package:

```typescript
import { getMasteryStyle } from '@kaihle/types'

// Usage:
const { dotClass, textClass, bgClass, label } = getMasteryStyle(score)

// dotClass  → for the coloured circle: bg-brand-green / bg-brand-amber / bg-brand-red
// textClass → for the score text:      text-brand-green etc.
// bgClass   → for row tint backgrounds (if used)
// label     → "Strong" / "Developing" / "Needs Work" / "Not assessed"
```

The circle must use `aria-label={label}` — not colour alone as the only indicator.

---

## "Suggested Next Steps" Section

- Shown at the bottom of the page (below topic groups)
- If student has active study plans: "You have N study plans waiting → [Go to Study Plans]"
- If no study plans: "Your teacher will assign study plans for areas that need work."
- Do NOT show this if `study_plans` API not yet built (M3) — render conditionally, graceful if API 404s

---

## useStudentGapMap Hook

```typescript
const { gapMap, isLoading } = useStudentGapMap(subjectId)
// Calls GET /api/v1/students/{current_user.id}/gap-map?subject_id={subjectId}
// Switches automatically when subject tab changes
```

---

## Acceptance Criteria

- [ ] E2E: student views progress after completing diagnostic → correct colours shown
- [ ] E2E: switching subject tabs loads correct subject's data
- [ ] E2E: expanding a subtopic row shows last assessed date
- [ ] Unit: `score=null` → grey circle + "Not assessed" (not "0%")
- [ ] Unit: `score=0.35` → red circle + "Needs Work"
- [ ] Unit: `score=0.65` → amber circle + "Developing"
- [ ] Unit: `score=0.85` → green circle + "Strong"
- [ ] Accessibility: traffic light circles have `aria-label` with text label
- [ ] Responsive: correct at 375px mobile

---

## Tests to Write

```typescript
// Playwright E2E
test('student_progress_shows_correct_colours_after_diagnostic')
test('subject_tab_switch_loads_correct_data')

// Jest unit
test('mastery_null_shows_not_assessed_not_zero_percent')
test('mastery_0_35_shows_needs_work')
test('colour_circles_have_aria_labels')
```
