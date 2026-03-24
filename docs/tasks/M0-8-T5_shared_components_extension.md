# M0-8-T5 — Shared Components Extension (ScoreRing + LearningStyleTag)
**Milestone:** M0 — Foundations
**Epic:** M0-8 — Pre-flight Fixes
**Task ID:** M0-8-T5
**Depends on:** M0-8-T4 (packages/ui foundation — Button, Card, Badge must exist)
**Blocks:** M1-3-T4 (assessment results — uses ScoreRing), M2-2-T1 (student roster — uses LearningStyleTag), M2-2-T2 (student profile — uses both)
**Estimated effort:** 2–3 hours
**Design sprint:** Pixel (component specs) + Kramer (implementation)

> **Why this task exists:**
> `ScoreRing` and `LearningStyleTag` are used across multiple apps and roles:
>
> | Component | Teacher app | Student app | Parent app |
> |---|---|---|---|
> | `ScoreRing` | Assessment results, Student profile | Assessment results page | — |
> | `LearningStyleTag` | Student roster, Student profile, Lesson plan sidebar | Settings (modality display) | — |
>
> Without this task, each app will implement its own version. The teacher app will spec
> one `ScoreRing`. The student app will spec a slightly different one. Within 2 milestones
> there will be 3 slightly inconsistent implementations. Moving these to `packages/ui`
> now costs 2 hours. The duplication debt compounds every sprint after.

---

## Pixel — Component Specifications

### ScoreRing

A reusable SVG progress ring that visualises a mastery score as a circular arc.

```
Component: ScoreRing
File: packages/ui/src/components/ScoreRing.tsx
Export: named export from packages/ui/src/index.ts
─────────────────────────────────────────────────────
Props:
  score:     number | null       — float 0.0–1.0 or null for "not assessed"
  size?:     'sm' | 'md' | 'lg' — default 'md'
  className?: string

Size map:
  sm:  48px × 48px   r=20  stroke-width=4   text: text-xs
  md:  80px × 80px   r=36  stroke-width=7   text: text-sm
  lg: 100px × 100px  r=45  stroke-width=10  text: text-lg

SVG setup (use size values from above):
  viewBox="0 0 {diameter} {diameter}"
  width={diameter} height={diameter}

Background arc:
  cx={r+strokeWidth/2+1} cy={r+strokeWidth/2+1}
  r={r} fill="none"
  stroke="#e5e7eb" stroke-width={strokeWidth}

Progress arc (same cx/cy/r, different stroke):
  fill="none" stroke-linecap="round"
  stroke-width={strokeWidth}
  transform="rotate(-90 {cx} {cy})"  — start at 12 o'clock
  stroke-dasharray={circumference}    — circumference = 2π × r
  stroke-dashoffset={circumference × (1 - (score ?? 0))}
  stroke = getMasteryStyle(score).strokeColour

Center text:
  <text x={cx} y={cy} text-anchor="middle" dominant-baseline="central"
    fill={getMasteryStyle(score).fillColour}
    font-weight="700" font-size={textSize}>
    {score === null ? "—" : `${Math.round(score * 100)}%`}
  </text>
─────────────────────────────────────────────────────
Stroke + fill colour mapping (extends getMasteryStyle):
  Strong (>0.7):    stroke="#16a34a"  fill="#15803d"
  Developing:       stroke="#f59e0b"  fill="#d97706"
  Needs Work (<0.4): stroke="#ef4444" fill="#dc2626"
  Not assessed (null): stroke="#9ca3af" fill="#9ca3af"
─────────────────────────────────────────────────────
Accessibility:
  role="img"
  aria-label="{Math.round(score*100)}% — {getMasteryStyle(score).label}"
  For null: aria-label="Not assessed"

Animation:
  stroke-dashoffset: 600ms ease-out on mount
  @media (prefers-reduced-motion) { no animation }
  CSS class `motion-safe:transition-all motion-safe:duration-600`
─────────────────────────────────────────────────────
States:
  score=0.85 → green arc, "85%"
  score=0.55 → amber arc, "55%"
  score=0.30 → red arc, "30%"
  score=null → gray full arc, "—"
```

**Add to getMasteryStyle return type** (update `packages/types/src/mastery.ts`):
```typescript
export interface MasteryStyle {
  dotClass: string
  textClass: string
  bgClass: string
  label: MasteryLabel
  strokeColour: string   // NEW — for ScoreRing SVG stroke
  fillColour: string     // NEW — for ScoreRing text fill
}

// Update getMasteryStyle to include:
if (score > 0.7) return {
  ...,
  strokeColour: '#16a34a',
  fillColour: '#15803d',
}
// etc. for each band
```

---

### LearningStyleTag

A compact pill badge showing a student's dominant learning modality with an icon.

```
Component: LearningStyleTag
File: packages/ui/src/components/LearningStyleTag.tsx
Export: named export from packages/ui/src/index.ts
─────────────────────────────────────────────────────
Props:
  modality:  'visual' | 'auditory' | 'reading_writing' | 'kinesthetic' | null
  size?:     'sm' | 'md'   — default 'sm'
  variant?:  'teacher' | 'student' | 'neutral'  — default 'neutral'
             controls background/text colour scheme

Size:
  sm: text-xs px-2.5 py-1 rounded-full
  md: text-sm px-3 py-1.5 rounded-full

Modality map:
  visual          → emoji "👁"  aria-label "Visual"       label "Visual"
  auditory        → emoji "👂"  aria-label "Auditory"      label "Auditory"
  reading_writing → emoji "📖"  aria-label "Reading & Writing"  label "Reading & Writing"
  kinesthetic     → emoji "🤲"  aria-label "Hands-on"      label "Hands-on"
  null            → render "—" text-gray-400, no pill wrapper

Variant colour map:
  neutral: bg-gray-100 text-gray-700   — default, all roles
  teacher: bg-amber-50 text-amber-700  — teacher app context (gold tones)
  student: bg-green-50 text-brand-primary — student app context (green tones)
─────────────────────────────────────────────────────
Accessibility:
  Emoji spans: aria-hidden="true"  — emoji is decorative
  Pill wrapper: no extra role needed (text label is sufficient)
  For null: renders plain text "—", no interactive element
─────────────────────────────────────────────────────
Usage examples:
  <LearningStyleTag modality="visual" />
  → 👁 Visual  (gray pill)

  <LearningStyleTag modality="kinesthetic" variant="teacher" />
  → 🤲 Hands-on  (amber pill — teacher context)

  <LearningStyleTag modality={null} />
  → — (plain dash, no pill)
```

---

## Kramer — Implementation

### Files to Create / Modify

```
frontend/packages/ui/src/components/ScoreRing.tsx          ← CREATE
frontend/packages/ui/src/components/LearningStyleTag.tsx   ← CREATE
frontend/packages/ui/src/index.ts                          ← MODIFY: add exports
frontend/packages/types/src/mastery.ts                     ← MODIFY: add strokeColour, fillColour to MasteryStyle
frontend/packages/types/src/__tests__/mastery.test.ts      ← MODIFY: add tests for new fields
frontend/packages/ui/src/components/__tests__/
  ScoreRing.test.tsx          ← CREATE
  LearningStyleTag.test.tsx   ← CREATE
```

### ScoreRing implementation

```tsx
// packages/ui/src/components/ScoreRing.tsx
import React from 'react'
import { getMasteryStyle } from '@kaihle/types'

type ScoreRingSize = 'sm' | 'md' | 'lg'

interface ScoreRingProps {
  score: number | null
  size?: ScoreRingSize
  className?: string
}

const sizeConfig: Record<ScoreRingSize, {
  diameter: number
  radius: number
  strokeWidth: number
  fontSize: string
}> = {
  sm: { diameter: 48,  radius: 20, strokeWidth: 4,  fontSize: '0.75rem' },
  md: { diameter: 80,  radius: 36, strokeWidth: 7,  fontSize: '0.875rem' },
  lg: { diameter: 100, radius: 45, strokeWidth: 10, fontSize: '1.125rem' },
}

export function ScoreRing({ score, size = 'md', className = '' }: ScoreRingProps) {
  const { diameter, radius, strokeWidth, fontSize } = sizeConfig[size]
  const cx = diameter / 2
  const cy = diameter / 2
  const circumference = 2 * Math.PI * radius
  const offset = score === null ? 0 : circumference * (1 - score)

  const style = getMasteryStyle(score)
  const displayText = score === null ? '—' : `${Math.round(score * 100)}%`
  const ariaLabel = score === null
    ? 'Not assessed'
    : `${Math.round(score * 100)}% — ${style.label}`

  return (
    <svg
      width={diameter}
      height={diameter}
      viewBox={`0 0 ${diameter} ${diameter}`}
      role="img"
      aria-label={ariaLabel}
      className={className}
    >
      {/* Background arc */}
      <circle
        cx={cx} cy={cy} r={radius}
        fill="none"
        stroke="#e5e7eb"
        strokeWidth={strokeWidth}
      />
      {/* Progress arc */}
      <circle
        cx={cx} cy={cy} r={radius}
        fill="none"
        stroke={style.strokeColour}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${cx} ${cy})`}
        className="motion-safe:transition-all motion-safe:duration-600 motion-safe:ease-out"
      />
      {/* Center text */}
      <text
        x={cx} y={cy}
        textAnchor="middle"
        dominantBaseline="central"
        fill={style.fillColour}
        fontWeight="700"
        fontSize={fontSize}
      >
        {displayText}
      </text>
    </svg>
  )
}
```

### LearningStyleTag implementation

```tsx
// packages/ui/src/components/LearningStyleTag.tsx
import React from 'react'

type Modality = 'visual' | 'auditory' | 'reading_writing' | 'kinesthetic' | null
type TagVariant = 'neutral' | 'teacher' | 'student'
type TagSize = 'sm' | 'md'

interface LearningStyleTagProps {
  modality: Modality
  size?: TagSize
  variant?: TagVariant
}

const modalityMap: Record<NonNullable<Modality>, { emoji: string; label: string }> = {
  visual:          { emoji: '👁',  label: 'Visual' },
  auditory:        { emoji: '👂', label: 'Auditory' },
  reading_writing: { emoji: '📖', label: 'Reading & Writing' },
  kinesthetic:     { emoji: '🤲', label: 'Hands-on' },
}

const variantClasses: Record<TagVariant, string> = {
  neutral: 'bg-gray-100 text-gray-700',
  teacher: 'bg-amber-50 text-amber-700',
  student: 'bg-green-50 text-brand-primary',
}

const sizeClasses: Record<TagSize, string> = {
  sm: 'text-xs px-2.5 py-1 rounded-full',
  md: 'text-sm px-3 py-1.5 rounded-full',
}

export function LearningStyleTag({
  modality,
  size = 'sm',
  variant = 'neutral',
}: LearningStyleTagProps) {
  if (modality === null) {
    return <span className="text-gray-400 text-xs">—</span>
  }

  const { emoji, label } = modalityMap[modality]

  return (
    <span
      className={`inline-flex items-center gap-1 font-medium ${sizeClasses[size]} ${variantClasses[variant]}`}
    >
      <span aria-hidden="true">{emoji}</span>
      {label}
    </span>
  )
}
```

### Update `packages/ui/src/index.ts`

Add these exports alongside existing exports:
```typescript
export { ScoreRing }        from './components/ScoreRing'
export { LearningStyleTag } from './components/LearningStyleTag'
export type { } // no new types needed — uses existing MasteryStyle from @kaihle/types
```

### Update `packages/types/src/mastery.ts`

Extend `MasteryStyle` and `getMasteryStyle`:
```typescript
export interface MasteryStyle {
  dotClass: string
  textClass: string
  bgClass: string
  label: MasteryLabel
  strokeColour: string   // SVG stroke for ScoreRing
  fillColour: string     // SVG text fill for ScoreRing
}

export function getMasteryStyle(score: number | null): MasteryStyle {
  if (score === null) return {
    dotClass: 'bg-brand-muted', textClass: 'text-brand-muted', bgClass: 'bg-gray-50',
    label: 'Not assessed', strokeColour: '#9ca3af', fillColour: '#9ca3af',
  }
  if (score > 0.7) return {
    dotClass: 'bg-brand-green', textClass: 'text-brand-green', bgClass: 'bg-brand-green-light',
    label: 'Strong', strokeColour: '#16a34a', fillColour: '#15803d',
  }
  if (score >= 0.4) return {
    dotClass: 'bg-brand-amber', textClass: 'text-brand-amber', bgClass: 'bg-brand-amber-light',
    label: 'Developing', strokeColour: '#f59e0b', fillColour: '#d97706',
  }
  return {
    dotClass: 'bg-brand-red', textClass: 'text-brand-red', bgClass: 'bg-brand-red-light',
    label: 'Needs Work', strokeColour: '#ef4444', fillColour: '#dc2626',
  }
}
```

---

## Unit Tests

```typescript
// ScoreRing.test.tsx
describe('ScoreRing', () => {
  it('renders with role="img" and aria-label', () => {
    render(<ScoreRing score={0.72} />)
    expect(screen.getByRole('img')).toHaveAttribute('aria-label', '72% — Strong')
  })

  it('renders "—" and "Not assessed" label for null score', () => {
    render(<ScoreRing score={null} />)
    expect(screen.getByRole('img')).toHaveAttribute('aria-label', 'Not assessed')
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('renders correctly for each size', () => {
    const { rerender } = render(<ScoreRing score={0.5} size="sm" />)
    expect(document.querySelector('svg')).toHaveAttribute('width', '48')
    rerender(<ScoreRing score={0.5} size="lg" />)
    expect(document.querySelector('svg')).toHaveAttribute('width', '100')
  })
})

// LearningStyleTag.test.tsx
describe('LearningStyleTag', () => {
  it('renders emoji and label for visual', () => {
    render(<LearningStyleTag modality="visual" />)
    expect(screen.getByText('Visual')).toBeInTheDocument()
    const emoji = screen.getByText('👁')
    expect(emoji).toHaveAttribute('aria-hidden', 'true')
  })

  it('renders Reading & Writing label for reading_writing', () => {
    render(<LearningStyleTag modality="reading_writing" />)
    expect(screen.getByText('Reading & Writing')).toBeInTheDocument()
  })

  it('renders plain dash for null — no pill wrapper', () => {
    const { container } = render(<LearningStyleTag modality={null} />)
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(container.querySelector('.rounded-full')).toBeNull()
  })

  it('applies teacher variant colour classes', () => {
    const { container } = render(<LearningStyleTag modality="visual" variant="teacher" />)
    expect(container.firstChild).toHaveClass('bg-amber-50', 'text-amber-700')
  })
})
```

---

## Acceptance Criteria

- [ ] `import { ScoreRing } from '@kaihle/ui'` resolves in all 5 apps
- [ ] `import { LearningStyleTag } from '@kaihle/ui'` resolves in all 5 apps
- [ ] `getMasteryStyle` now returns `strokeColour` and `fillColour` fields
- [ ] Existing mastery tests still pass (no regressions to dotClass/textClass/bgClass/label)
- [ ] `ScoreRing` with score=null renders "—" and `aria-label="Not assessed"`
- [ ] `ScoreRing` with score=0.85 has `aria-label="85% — Strong"`
- [ ] `LearningStyleTag` emoji spans have `aria-hidden="true"`
- [ ] `LearningStyleTag` null renders plain dash with no pill wrapper
- [ ] `LearningStyleTag variant="teacher"` uses amber colours
- [ ] Animation has `motion-safe:` Tailwind prefix (respects prefers-reduced-motion)
- [ ] All unit tests pass
- [ ] `tsc --noEmit` passes in packages/ui and packages/types

---

## Do NOT Touch

- Any app-level component files — these components now live in packages/ui only
- Existing getMasteryStyle return values (dotClass, textClass, bgClass, label) — only adding new fields, not changing existing ones
