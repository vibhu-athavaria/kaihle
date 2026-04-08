# M0-8-T8 — Mastery 4-Band Design Tokens & getMasteryStyle Update
**Milestone:** M0-8 — Shared Component Foundation
**Epic:** M0-8 — Frontend Infrastructure
**Task:** T8
**Executor:** Coding agent
**Depends on:** M0-8-T5 (getMasteryStyle already extended with strokeColour/fillColour)
**Must complete before:** M2-1-T3 (teacher heatmap), M3-2-T3 (student study plan UI),
                         M4-1-T4 (teacher lesson plan UI), M4-2-T2 (student pack UI)

> **Run this before any milestone that renders mastery data.**
> The 4-band system is a confirmed product decision. Every UI task that calls
> getMasteryStyle() assumes 4 bands exist. If this task is not complete,
> the "Approaching" band will crash with a type error or render incorrectly.

---

## Context

The original Kaihle mastery system used 3 bands (Needs Work / Developing / Strong).
After the mastery scoring algorithm was finalised, a 4-band system was confirmed:

| Score | Label | Meaning |
|---|---|---|
| 0.00–0.39 | Critical Gap | Foundational knowledge missing; immediate intervention |
| 0.40–0.69 | Developing | Partial understanding; targeted support needed |
| 0.70–0.84 | Approaching | Close to mastery; minor gaps remain |
| 0.85–1.00 | Mastered | Secure, confident understanding |

**The 0.4 and 0.7 boundaries are preserved.** The only change is that the old
"Strong" band (>0.7) is split into "Approaching" (0.70–0.84) and "Mastered" (≥0.85),
and "Needs Work" (<0.4) is renamed "Critical Gap". This is backward-compatible for
any code that tests `score > 0.7` or `score < 0.4` — those thresholds are unchanged.

**Parent portal exception:** The parent portal (M5) uses a simplified 3-band display.
The mapping from 4 internal bands to 3 parent labels happens in the service layer:
- Critical Gap → "Needs Work"
- Developing → "Developing" (unchanged)
- Approaching → "Developing" (maps down, not up — parents see "still working")
- Mastered → "Strong"

This mapping lives in `backend/app/services/parent_service.py`, not in getMasteryStyle.

---

## User Story

As a developer building any UI that displays mastery data, I want a getMasteryStyle
function that returns correct colours and labels for all 4 mastery bands, so that
students, teachers, and admins see consistent mastery visualisation across the platform.

---

## Files to Create / Modify

```
MODIFY  frontend/packages/types/src/mastery.ts       ← add Approaching band
MODIFY  frontend/packages/ui/tailwind.config.js       ← add brand-lime token
MODIFY  frontend/packages/ui/src/components/ScoreRing.tsx  ← no logic change needed
                                                             (uses getMasteryStyle, auto-updates)
CREATE  frontend/packages/types/src/__tests__/mastery_4band.test.ts
```

---

## Part 1 — New Design Token

Add to `frontend/packages/ui/tailwind.config.js` in the `extend.colors` block,
alongside existing brand tokens:

```js
// Add to extend.colors in tailwind.config.js
'brand-lime':       '#84cc16',   // Approaching mastery — lime green
'brand-lime-light': '#f7fee7',   // Approaching tint background
'brand-lime-mid':   '#bef264',   // Approaching border/subtle
```

> **Why lime, not yellow?**
> The design system avoids generic Tailwind colour names (`yellow-*`, `lime-*`)
> per DESIGN_SYSTEM.md §2. All brand colours must be custom tokens in
> `tailwind.config.js` with hex values. `brand-lime` is the correct token name.
> Yellow (`#eab308`) is too close to amber (`#f59e0b`, the Developing band colour)
> and would cause visual confusion when both bands appear adjacent in a heatmap.
> Lime (`#84cc16`) is clearly distinct from amber while remaining in the warm-green
> direction appropriate for "almost there".

---

## Part 2 — Updated getMasteryStyle

Replace the existing function in `frontend/packages/types/src/mastery.ts`:

```typescript
export type MasteryLabel =
  | 'Mastered'
  | 'Approaching'
  | 'Developing'
  | 'Critical Gap'
  | 'Not assessed'

export interface MasteryStyle {
  label: MasteryLabel
  dotClass: string
  textClass: string
  bgClass: string
  // Added in M0-8-T5 — preserved here
  strokeColour: string
  fillColour: string
}

/**
 * Returns display style for a mastery score using the 4-band system.
 *
 * Band boundaries (confirmed product decision — do not change without ADR):
 *   score >= 0.85               → Mastered     (green)
 *   0.70 <= score < 0.85        → Approaching  (lime)
 *   0.40 <= score < 0.70        → Developing   (amber)
 *   score < 0.40                → Critical Gap (red)
 *   null                        → Not assessed (grey)
 *
 * Boundary edge cases:
 *   score = 0.85 → Mastered   (>= 0.85, not just > 0.85)
 *   score = 0.70 → Approaching (>= 0.70, not just > 0.70)
 *   score = 0.40 → Developing  (>= 0.40)
 *
 * Parent portal mapping (handled in backend parent_service.py, NOT here):
 *   Mastered + Approaching → "Strong"
 *   Developing             → "Developing"
 *   Critical Gap           → "Needs Work"
 */
export function getMasteryStyle(score: number | null): MasteryStyle {
  if (score === null || score === undefined) {
    return {
      label: 'Not assessed',
      dotClass: 'bg-brand-muted',
      textClass: 'text-brand-muted',
      bgClass: 'bg-gray-50',
      strokeColour: '#9ca3af',
      fillColour: '#d1d5db',
    }
  }
  if (score >= 0.85) {
    return {
      label: 'Mastered',
      dotClass: 'bg-brand-green',
      textClass: 'text-brand-green',
      bgClass: 'bg-brand-green-light',
      strokeColour: '#16a34a',
      fillColour: '#15803d',
    }
  }
  if (score >= 0.70) {
    return {
      label: 'Approaching',
      dotClass: 'bg-brand-lime',
      textClass: 'text-brand-lime',
      bgClass: 'bg-brand-lime-light',
      strokeColour: '#84cc16',
      fillColour: '#65a30d',
    }
  }
  if (score >= 0.40) {
    return {
      label: 'Developing',
      dotClass: 'bg-brand-amber',
      textClass: 'text-brand-amber',
      bgClass: 'bg-brand-amber-light',
      strokeColour: '#f59e0b',
      fillColour: '#d97706',
    }
  }
  // score < 0.40
  return {
    label: 'Critical Gap',
    dotClass: 'bg-brand-red',
    textClass: 'text-brand-red',
    bgClass: 'bg-brand-red-light',
    strokeColour: '#ef4444',
    fillColour: '#dc2626',
  }
}

/**
 * Returns true if a mastery score indicates the student needs active support.
 * Used for gap map cell highlighting and study plan assignment triggers.
 */
export function needsSupport(score: number | null): boolean {
  return score === null || score < 0.70
}

/**
 * Returns true if this score represents a critical knowledge gap
 * that should surface as a priority in the teacher gap map.
 */
export function isCriticalGap(score: number | null): boolean {
  return score === null || score < 0.40
}
```

---

## Part 3 — Backend Alignment

The backend `lesson_plan_service.py` and `gap_map_service.py` both use hardcoded
thresholds `0.4` and `0.7` for student grouping. These thresholds are **unchanged**
by this task — the 4-band system does not shift these boundaries.

However, the student grouping labels in `lesson_plan_service.py` must be updated
to use the new band names in the prompt template:

In `M4-1-T1_lesson_plan_celery_task.md`, the user prompt currently says:
```
- Group A ({{ group_a_count }} students, mastery < 40%): foundational support needed
- Group B ({{ group_b_count }} students, mastery 40–70%): developing
- Group C ({{ group_c_count }} students, mastery > 70%): ready for extension
```

Update the Jinja2 template `lesson_plan_user.jinja2` to:
```
- Group A ({{ group_a_count }} students, mastery < 40% — Critical Gap): foundational re-teaching needed
- Group B ({{ group_b_count }} students, mastery 40–70% — Developing or Approaching): consolidation activities
- Group C ({{ group_c_count }} students, mastery ≥ 85% — Mastered): extension and enrichment
```

> Note: Group C boundary is 0.85 in the updated template (Mastered) rather than
> 0.7 (old "Strong"). The Python grouping logic still uses `avg > 0.7` for Group C
> assignment — this is correct because "Approaching" students (0.70–0.84) are placed
> in Group B for targeted consolidation, not Group C extension. The prompt wording
> change reflects the more precise labelling.

---

## Part 4 — DESIGN_SYSTEM.md Update

In `docs/design/DESIGN_SYSTEM.md` §2, replace the mastery band table:

```markdown
### Mastery Score Colour Bands ⚠️ NEVER use generic emerald-*/amber-*/red-*/lime-*

| Score | Label | Dot class | Text class | Tint bg |
|---|---|---|---|---|
| ≥ 0.85 | Mastered | `bg-brand-green` | `text-brand-green` | `bg-brand-green-light` |
| 0.70–0.84 | Approaching | `bg-brand-lime` | `text-brand-lime` | `bg-brand-lime-light` |
| 0.40–0.69 | Developing | `bg-brand-amber` | `text-brand-amber` | `bg-brand-amber-light` |
| < 0.40 | Critical Gap | `bg-brand-red` | `text-brand-red` | `bg-brand-red-light` |
| null | Not assessed | `bg-brand-muted` | `text-brand-muted` | `bg-gray-50` |
```

Also update the TypeScript helper block in §2 to match the new getMasteryStyle
function defined in Part 2 of this task.

---

## Part 5 — CONSTITUTION.md Update (§11)

Replace §11 Mastery Thresholds table:

```markdown
## 11. Mastery Thresholds

Always use `getMasteryStyle(score)` from `packages/types/src/mastery.ts` —
never inline mastery color logic.

| Score range | Label | Tailwind classes |
|---|---|---|
| `score >= 0.85` | Mastered | `text-brand-green bg-brand-green-light` |
| `0.70 <= score < 0.85` | Approaching | `text-brand-lime bg-brand-lime-light` |
| `0.40 <= score < 0.70` | Developing | `text-amber-600 bg-brand-amber-light` |
| `score < 0.40` | Critical Gap | `text-brand-red bg-brand-red-light` |
| `null` | Not assessed | `text-gray-400 bg-gray-50` |

Boundary values: `0.85` → Mastered, `0.70` → Approaching, `0.40` → Developing.

Parent portal only: Backend `parent_service.py` maps 4 internal bands to 3 parent
labels: Mastered+Approaching → "Strong", Developing → "Developing",
Critical Gap → "Needs Work". This mapping is in the backend only — never in getMasteryStyle.
```

---

## Acceptance Criteria

- [ ] `brand-lime`, `brand-lime-light`, `brand-lime-mid` tokens exist in `tailwind.config.js`
- [ ] `getMasteryStyle(0.9)` returns `label: 'Mastered'`, green classes
- [ ] `getMasteryStyle(0.85)` returns `label: 'Mastered'` (boundary — inclusive)
- [ ] `getMasteryStyle(0.80)` returns `label: 'Approaching'`, lime classes
- [ ] `getMasteryStyle(0.70)` returns `label: 'Approaching'` (boundary — inclusive)
- [ ] `getMasteryStyle(0.65)` returns `label: 'Developing'`, amber classes
- [ ] `getMasteryStyle(0.40)` returns `label: 'Developing'` (boundary — inclusive)
- [ ] `getMasteryStyle(0.35)` returns `label: 'Critical Gap'`, red classes
- [ ] `getMasteryStyle(0.0)` returns `label: 'Critical Gap'`
- [ ] `getMasteryStyle(null)` returns `label: 'Not assessed'`, grey classes
- [ ] `getMasteryStyle(undefined)` returns `label: 'Not assessed'` (defensive)
- [ ] `needsSupport(0.69)` returns `true`
- [ ] `needsSupport(0.70)` returns `false` (Approaching no longer "needs support")
- [ ] `isCriticalGap(0.39)` returns `true`
- [ ] `isCriticalGap(0.40)` returns `false`
- [ ] All existing getMasteryStyle tests from M0-8-T5 still pass (no regressions)
- [ ] `tsc --noEmit` passes in `packages/types` and `packages/ui`
- [ ] `ScoreRing` renders "Approaching" band with lime stroke (no code change needed — inherits from getMasteryStyle)

---

## Tests to Write

**`frontend/packages/types/src/__tests__/mastery_4band.test.ts`**

```typescript
describe('getMasteryStyle — 4-band system', () => {
  test('score 0.9 returns Mastered with green classes')
  test('score 0.85 returns Mastered — boundary inclusive')
  test('score 0.84 returns Approaching — just below Mastered boundary')
  test('score 0.75 returns Approaching with lime classes')
  test('score 0.70 returns Approaching — boundary inclusive')
  test('score 0.69 returns Developing — just below Approaching boundary')
  test('score 0.55 returns Developing with amber classes')
  test('score 0.40 returns Developing — boundary inclusive')
  test('score 0.39 returns Critical Gap — just below Developing boundary')
  test('score 0.20 returns Critical Gap with red classes')
  test('score 0.0 returns Critical Gap')
  test('score null returns Not assessed with grey classes')
  test('score undefined returns Not assessed defensively')
  test('all returned objects have dotClass, textClass, bgClass, strokeColour, fillColour')
  test('needsSupport returns true for score below 0.70')
  test('needsSupport returns false for score 0.70 and above')
  test('isCriticalGap returns true for score below 0.40')
  test('isCriticalGap returns false for score 0.40 and above')
})
```

---

## Do NOT Touch

- The numeric thresholds `0.4` and `0.7` in `lesson_plan_service.py` grouping logic
  — Group A/B/C boundaries are unchanged
- `parent_service.py` — the 4→3 band mapping is handled in M5-1-T2, not here
- Any app-level component that calls `getMasteryStyle()` — they auto-inherit the
  new band because they call the function rather than hardcoding labels
- `MASTERY_THRESHOLD_RATIONALE.md` — update separately after this task ships,
  with the rationale for the Approaching band split from Strong

---

*Task M0-8-T8 · Pixel (UX/UI Lead) + Kramer (Technical Lead) · April 2026*
*Prerequisite for: M2-1-T3, M3-2-T3, M4-1-T4, M4-2-T2, M5-1-T3*
