# M2-1-T3 — Teacher Gap Map Heatmap UI
**Milestone:** M2 · **Epic:** M2-1 · **Task:** T3
**Depends on:** M2-1-T2 (gap map routes), M0-3-T4 (auth frontend)

---

## User Story
As a teacher, I want to see a colour-coded heatmap of my class's mastery scores per subtopic so I can instantly spot which students need help with which topics.

---

## Files to Create

```
frontend/apps/teacher/src/pages/gap-map/ClassGapMap.tsx
frontend/apps/teacher/src/pages/gap-map/StudentSidePanel.tsx
frontend/apps/teacher/src/hooks/useClassGapMap.ts
frontend/apps/teacher/src/tests/gap-map.spec.ts
```

---

## Route

`/teacher/classes/:classId/gap-map`

---

## Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  [← Back]  Mathematics — Grade 9       [Export CSV]            │
│                                                                 │
│  Subject: [Math ▼]  Grade: [9 ▼]                               │
├──────────────────┬─────┬─────┬─────┬─────┬─────────────────────┤
│  Subtopic        │Aisha│ Ben │Citra│...  │ Class Avg           │
├──────────────────┼─────┼─────┼─────┼─────┼─────────────────────┤
│  Algebra                                                        │
│    Alg. Fractions│ 🔴  │ 🟡  │ 🟢  │...  │  54%               │
│    Quadratics    │ 🟡  │ 🟢  │ 🟢  │...  │  71%               │
├──────────────────┼─────┼─────┼─────┼─────┼─────────────────────┤
│  Geometry        │     │     │     │...  │                     │
│    Pythagoras    │ ⬜  │ 🔴  │ 🟡  │...  │  45%               │
└──────────────────┴─────┴─────┴─────┴─────┴─────────────────────┘
```

---

## Cell Colours

Use `getMasteryStyle()` from `packages/types/src/mastery.ts` to derive Tailwind classes.
Do NOT hardcode color class names — use the helper.

| Score | Tailwind bg class | Label |
|---|---|---|
| > 0.7 | `bg-brand-green` | Strong |
| 0.4–0.7 | `bg-brand-amber` | Developing |
| < 0.4 | `bg-brand-red` | Needs Work |
| No data | `bg-brand-muted/30` | — |

Cells are 40×40px squares. No text inside cells — colour only. Tooltip on hover.

```tsx
import { getMasteryStyle } from '@kaihle/types'

// In the cell component:
const { dotClass, label } = getMasteryStyle(score)
<td
  className={`w-10 h-10 ${dotClass} cursor-pointer`}
  title={`${studentName} · ${label}`}
  aria-label={`${studentName}: ${label}`}
/>
```
---

## Hover Tooltip

On hover over any coloured cell:
```
Aisha Rahman
Algebraic Fractions
Mastery: 65%   Confidence: High
Last assessed: 2 Mar 2026
```

---

## Student Side Panel (`StudentSidePanel.tsx`)

Clicking any cell opens a right-side drawer (slides in from right, 380px wide):

```
┌──────────────────────────────────┐
│  Aisha Rahman               [✕]  │
│  Grade 9 — Mathematics           │
│                                  │
│  Algebraic Fractions             │
│  Mastery: 65%  🟡 Developing     │
│  Last assessed: 2 Mar 2026       │
│                                  │
│  ─── Learning Style ───          │
│  👁 Visual learner               │
│  ❤️ Interests: Football, Music   │
│                                  │
│  [Assign Study Plan]             │
└──────────────────────────────────┘
```

### Learning Style Display
- Load from `GET /api/v1/onboarding/learning-profile?student_id={id}`
- Dominant modality: `argmax(modality_scores)` → show icon + label
  - visual → 👁 Visual learner
  - auditory → 👂 Auditory learner
  - reading_writing → 📖 Reading/Writing learner
  - kinesthetic → 🤲 Hands-on learner
- Top 3 interests from `interests[]`, shown as small tags
- If no profile: show "Learning profile not yet completed" — do not crash

### "Assign Study Plan" Button
- Opens assignment modal (wired in M3-2-T4 — stub for now, just log click)

---

## Export CSV

"Export CSV" button downloads a file:
```csv
Student,Topic,Subtopic,Mastery,LastAssessed
Aisha Rahman,Algebra,Algebraic Fractions,0.65,2026-03-02
...
```

---

## Acceptance Criteria

- [ ] E2E: teacher views gap map → cells render with correct colours
- [ ] E2E: hover tooltip shows student name, subtopic, mastery %, last assessed date
- [ ] E2E: click red cell → side panel opens with correct student + subtopic data
- [ ] E2E: side panel shows dominant learning modality icon
- [ ] E2E: side panel shows top interests as tags
- [ ] E2E: student with no learning profile → "not yet completed" message, no crash
- [ ] Unit: mastery=0.35 → red cell, 0.55 → amber, 0.85 → green, null → grey
- [ ] Unit: `argmax({visual: 0.8, auditory: 0.3})` → shows visual icon
- [ ] Performance: 40 × 50 grid renders in < 2 seconds
- [ ] CSV export produces correctly formatted file

---

## Tests to Write (Playwright)

```typescript
test('gap_map_cells_render_with_correct_colours')
test('hover_tooltip_shows_student_data')
test('click_cell_opens_side_panel')
test('side_panel_shows_learning_style')
test('side_panel_no_profile_shows_fallback_message')
test('export_csv_downloads_file')
```
