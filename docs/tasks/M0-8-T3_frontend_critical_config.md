# M0-8-T3 — Frontend Critical Config Fixes
**Milestone:** M0 — Foundations
**Epic:** M0-8 — Pre-flight Fixes
**Task ID:** M0-8-T3
**Depends on:** M0-1-T1 (frontend workspace), M0-3-T4 (auth package)
**Blocks:** M0-8-T4 (shared components need fonts working first), M0-6-T4
**Estimated effort:** 2–3 hours

---

## Context

Four critical frontend issues found in the M0 audit. These are all config-level fixes
— no new components, no new pages. They must land before any UI work (including shared
components) because everything downstream assumes fonts and token types exist.

Read `docs/design/DESIGN_SYSTEM.md` before implementing.

---

## Fix 1 — Add Google Fonts import to all three app `index.css` files

### Problem

All three `index.css` files contain only Tailwind directives. Without the Google Fonts
import, Nunito and Fraunces (the Kaihle brand fonts) will not load. Every page falls
back to `system-ui`, which looks nothing like the design. This is the single most
visible visual regression in the entire codebase.

### Fix

**Add this import as the FIRST line** of each app's `src/index.css` (before `@tailwind base`):

```css
@import url('https://fonts.googleapis.com/css2?family=Nunito:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,400&family=Fraunces:ital,opsz,wght@0,9..144,600;0,9..144,700;1,9..144,400;1,9..144,600&family=Inter:wght@400;500;600;700&family=Lora:ital,wght@0,600;1,400&display=swap');

@tailwind base;
@tailwind components;
@tailwind utilities;
```

**Also add a design system reference comment** (see Fix 4):

```css
/* Design system: docs/design/DESIGN_SYSTEM.md */
@import url('https://fonts.googleapis.com/...');

@tailwind base;
@tailwind components;
@tailwind utilities;
```

Apply to all three files:
- `frontend/apps/teacher/src/index.css`
- `frontend/apps/student/src/index.css`
- `frontend/apps/parent/src/index.css`

---

## Fix 2 — Extend student and parent `tailwind.config.js` to use shared base

### Problem

Only `apps/teacher/tailwind.config.js` extends the shared base config from
`packages/ui`. Student and parent apps still have the old empty config:
```js
export default { content: ['./src/**/*.{ts,tsx}'], theme: { extend: {} }, plugins: [] }
```

Brand tokens (`bg-brand-primary`, `text-role-student-bg`, etc.) are not available
in the student or parent apps. Any component using brand tokens in those apps will
render with no background color or wrong color.

### Fix

**`frontend/apps/student/tailwind.config.js`** — replace entirely:
```js
import baseConfig from '@kaihle/ui/tailwind.config.js'

export default {
  ...baseConfig,
  content: [
    './src/**/*.{ts,tsx}',
    '../../packages/ui/src/**/*.{ts,tsx}',
  ],
}
```

**`frontend/apps/parent/tailwind.config.js`** — replace entirely:
```js
import baseConfig from '@kaihle/ui/tailwind.config.js'

export default {
  ...baseConfig,
  content: [
    './src/**/*.{ts,tsx}',
    '../../packages/ui/src/**/*.{ts,tsx}',
  ],
}
```

(Teacher app already has this — no change needed.)

---

## Fix 3 — Create `packages/types/src/mastery.ts`

### Problem

`packages/types/` is an empty directory. `getMasteryStyle()` is referenced in:
- DESIGN_SYSTEM.md §2
- M2-1-T3 gap map heatmap task (patched to import from `@kaihle/types`)
- M2-1-T4 student gap profile task (patched to import from `@kaihle/types`)
- M0-7-T2 teacher dashboard task
- M0-7-T3 student dashboard task

Any agent starting any of these tasks will have a broken import. The type needs to
exist before components are built.

### Fix

**`frontend/packages/types/src/mastery.ts`** — create:

```typescript
/**
 * Mastery score colour band utilities.
 * Single source of truth for mastery label + Tailwind class derivation.
 *
 * Usage:
 *   import { getMasteryStyle } from '@kaihle/types'
 *   const { dotClass, textClass, bgClass, label } = getMasteryStyle(0.72)
 *   // → { dotClass: 'bg-brand-green', textClass: 'text-brand-green',
 *   //     bgClass: 'bg-brand-green-light', label: 'Strong' }
 *
 * NEVER hardcode mastery colors in components — always call this helper.
 * See docs/design/DESIGN_SYSTEM.md §2 for the full color token reference.
 */

export type MasteryLabel = 'Strong' | 'Developing' | 'Needs Work' | 'Not assessed'

export interface MasteryStyle {
  /** Tailwind class for the colored dot/circle/cell */
  dotClass: string
  /** Tailwind class for text displaying the score */
  textClass: string
  /** Tailwind class for tinted card/row background */
  bgClass: string
  /** Human-readable label */
  label: MasteryLabel
}

/**
 * Derive Tailwind color classes from a mastery score.
 *
 * @param score - Float 0.0–1.0, or null if not yet assessed
 * @returns MasteryStyle with Tailwind classes and label
 *
 * Bands (per CONSTITUTION §10 and DESIGN_SYSTEM.md §2):
 *   > 0.7   → Strong      (#16a34a — brand-green)
 *   0.4–0.7 → Developing  (#f59e0b — brand-amber)
 *   < 0.4   → Needs Work  (#ef4444 — brand-red)
 *   null    → Not assessed (#9ca3af — brand-muted)
 */
export function getMasteryStyle(score: number | null): MasteryStyle {
  if (score === null) {
    return {
      dotClass: 'bg-brand-muted',
      textClass: 'text-brand-muted',
      bgClass: 'bg-gray-50',
      label: 'Not assessed',
    }
  }
  if (score > 0.7) {
    return {
      dotClass: 'bg-brand-green',
      textClass: 'text-brand-green',
      bgClass: 'bg-brand-green-light',
      label: 'Strong',
    }
  }
  if (score >= 0.4) {
    return {
      dotClass: 'bg-brand-amber',
      textClass: 'text-brand-amber',
      bgClass: 'bg-brand-amber-light',
      label: 'Developing',
    }
  }
  return {
    dotClass: 'bg-brand-red',
    textClass: 'text-brand-red',
    bgClass: 'bg-brand-red-light',
    label: 'Needs Work',
  }
}

/**
 * Convert a float score (0.0–1.0) to a display percentage string.
 * Always use this — never display raw floats to users.
 *
 * @example scoreToPercent(0.72) → "72%"
 * @example scoreToPercent(null) → "—"
 */
export function scoreToPercent(score: number | null): string {
  if (score === null) return '—'
  return `${Math.round(score * 100)}%`
}
```

**`frontend/packages/types/src/index.ts`** — create or update to export:

```typescript
export { getMasteryStyle, scoreToPercent } from './mastery'
export type { MasteryLabel, MasteryStyle } from './mastery'
```

**`frontend/packages/types/package.json`** — ensure it exists with correct config:

```json
{
  "name": "@kaihle/types",
  "version": "0.1.0",
  "main": "src/index.ts",
  "types": "src/index.ts"
}
```

**Unit tests** — `frontend/packages/types/src/__tests__/mastery.test.ts`:

```typescript
import { getMasteryStyle, scoreToPercent } from '../mastery'

describe('getMasteryStyle', () => {
  test('score 0.85 → Strong + brand-green classes', () => {
    const s = getMasteryStyle(0.85)
    expect(s.label).toBe('Strong')
    expect(s.dotClass).toBe('bg-brand-green')
    expect(s.textClass).toBe('text-brand-green')
  })
  test('score 0.7 → Developing (boundary — not > 0.7)', () => {
    expect(getMasteryStyle(0.7).label).toBe('Developing')
  })
  test('score 0.71 → Strong (just over boundary)', () => {
    expect(getMasteryStyle(0.71).label).toBe('Strong')
  })
  test('score 0.4 → Developing (lower boundary — >= 0.4)', () => {
    expect(getMasteryStyle(0.4).label).toBe('Developing')
  })
  test('score 0.39 → Needs Work', () => {
    expect(getMasteryStyle(0.39).label).toBe('Needs Work')
    expect(getMasteryStyle(0.39).dotClass).toBe('bg-brand-red')
  })
  test('score null → Not assessed + muted classes', () => {
    const s = getMasteryStyle(null)
    expect(s.label).toBe('Not assessed')
    expect(s.dotClass).toBe('bg-brand-muted')
  })
})

describe('scoreToPercent', () => {
  test('0.72 → "72%"', () => expect(scoreToPercent(0.72)).toBe('72%'))
  test('0.0 → "0%"', () => expect(scoreToPercent(0.0)).toBe('0%'))
  test('1.0 → "100%"', () => expect(scoreToPercent(1.0)).toBe('100%'))
  test('null → "—"', () => expect(scoreToPercent(null)).toBe('—'))
  test('rounds correctly: 0.676 → "68%"', () => expect(scoreToPercent(0.676)).toBe('68%'))
})
```

---

## Fix 4 — Fix teal brand color in LoginForm

### Problem

`M0-3-T5` login UI uses `className="mt-4 text-sm text-teal-600 hover:underline"` on
the "Send again" magic link button. Teal is not in the Kaihle design system.

### Fix

In `frontend/packages/ui/src/LoginForm.tsx`, find and replace the teal class:

```tsx
// FIND:
className="mt-4 text-sm text-teal-600 hover:underline"

// REPLACE WITH:
className="mt-4 text-sm font-semibold text-brand-primary hover:text-brand-dark transition-colors"
```

---

## Files to Create / Modify

```
frontend/apps/teacher/src/index.css               ← ADD fonts import + design system comment
frontend/apps/student/src/index.css               ← ADD fonts import + design system comment
frontend/apps/parent/src/index.css                ← ADD fonts import + design system comment
frontend/apps/student/tailwind.config.js          ← REPLACE with shared base config extend
frontend/apps/parent/tailwind.config.js           ← REPLACE with shared base config extend
frontend/packages/types/src/mastery.ts            ← CREATE
frontend/packages/types/src/index.ts              ← CREATE
frontend/packages/types/package.json              ← CREATE/UPDATE
frontend/packages/types/src/__tests__/mastery.test.ts  ← CREATE
frontend/packages/ui/src/LoginForm.tsx            ← FIX teal → brand-primary
```

---

## Acceptance Criteria

- [ ] `pnpm dev:teacher` — browser renders Fraunces serif headings and Nunito body text (not system-ui)
- [ ] `pnpm dev:student` — same font check
- [ ] `pnpm dev:parent` — same font check
- [ ] `import { getMasteryStyle } from '@kaihle/types'` resolves in teacher, student, and parent apps
- [ ] Unit tests for `getMasteryStyle` and `scoreToPercent` all pass
- [ ] Boundary conditions: 0.7 → Developing, 0.71 → Strong, 0.4 → Developing, 0.39 → Needs Work
- [ ] `bg-brand-primary` resolves to `#1a5c38` in student app (confirms tailwind config working)
- [ ] `bg-role-parent-bg` resolves to `#fdf8f0` in parent app (confirms role tokens working)
- [ ] LoginForm "Send again" button renders in `#1a5c38` green, not teal
- [ ] `tsc --noEmit` passes with zero errors in all three apps and packages/types
- [ ] `jest` passes in packages/types
