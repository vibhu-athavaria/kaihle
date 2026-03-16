# M0-8-T4 — Shared UI Foundation (packages/ui components + packages/api-client)
**Milestone:** M0 — Foundations
**Epic:** M0-8 — Pre-flight Fixes
**Task ID:** M0-8-T4
**Depends on:** M0-8-T3 (fonts + tailwind tokens must exist), M0-3-T4 (auth package)
**Blocks:** M0-7-T1 (layout wrappers import from packages/ui), M0-6-T4 (onboarding UI needs Button, Card, Skeleton)
**Estimated effort:** 4–5 hours

---

## Context

`packages/ui` has only a `tailwind.config.js` — no actual components. Every UI task
from M0-6-T4 onwards will either (a) fail to import from `@kaihle/ui`, or (b) define
their own local Button/Card components — creating the exact duplication the package
was meant to prevent.

`packages/api-client` is empty. Currently UI tasks use `apiClient` from `@kaihle/auth`
which works but is architecturally wrong (auth package shouldn't own the general HTTP client).

This task creates the minimum component set needed for M0-6-T4 (onboarding UI) and
M0-7-T1 (layout wrappers). Not a full design system build — just the primitives.

Read `docs/design/DESIGN_SYSTEM.md` §4 before implementing every component.

---

## Part A — `packages/ui` Core Components

### Package setup

**`frontend/packages/ui/package.json`**:
```json
{
  "name": "@kaihle/ui",
  "version": "0.1.0",
  "main": "src/index.ts",
  "types": "src/index.ts",
  "exports": {
    ".": "./src/index.ts",
    "./tailwind.config.js": "./tailwind.config.js"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "lucide-react": "^0.383.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "typescript": "^5.5.0"
  }
}
```

### Components to build

All files go in `frontend/packages/ui/src/components/`.

---

#### `Button.tsx`

```tsx
import React from 'react'

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'
type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  icon?: React.ReactNode
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:   'bg-brand-primary hover:bg-brand-dark text-white shadow-btn',
  secondary: 'bg-white hover:bg-gray-50 text-brand-ink border border-brand-border',
  danger:    'bg-brand-red hover:bg-red-600 text-white',
  ghost:     'bg-white/15 hover:bg-white/25 text-white border border-white/30',
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-4 py-2 text-xs',
  md: 'px-5 py-2.5 text-sm',
  lg: 'px-7 py-3.5 text-base',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  children,
  className = '',
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={[
        'inline-flex items-center justify-center gap-2 font-sans font-bold',
        'rounded-full transition-colors',
        'focus-visible:outline-none focus-visible:ring-2',
        'focus-visible:ring-brand-primary focus-visible:ring-offset-2',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        variantClasses[variant],
        sizeClasses[size],
        className,
      ].join(' ')}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" aria-hidden="true" />
      ) : icon ? (
        <span className="w-4 h-4" aria-hidden="true">{icon}</span>
      ) : null}
      {children}
    </button>
  )
}
```

---

#### `Card.tsx`

```tsx
import React from 'react'

type CardVariant = 'default' | 'interactive' | 'highlighted' | 'ghost'

interface CardProps {
  variant?: CardVariant
  children: React.ReactNode
  className?: string
  onClick?: () => void
}

const variantClasses: Record<CardVariant, string> = {
  default:     'bg-white border border-brand-border shadow-card',
  interactive: 'bg-white border border-brand-border shadow-card hover:shadow-card-hover hover:-translate-y-0.5 transition-all cursor-pointer',
  highlighted: 'bg-brand-light border border-brand-mid',
  ghost:       'bg-transparent border border-brand-border',
}

export function Card({ variant = 'default', children, className = '', onClick }: CardProps) {
  return (
    <div
      className={['rounded-2xl p-5', variantClasses[variant], className].join(' ')}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => e.key === 'Enter' && onClick() : undefined}
    >
      {children}
    </div>
  )
}
```

---

#### `Badge.tsx`

```tsx
import React from 'react'

type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'gold'

interface BadgeProps {
  variant?: BadgeVariant
  children: React.ReactNode
  pulse?: boolean
}

const variantClasses: Record<BadgeVariant, string> = {
  success: 'bg-brand-green-light text-brand-green',
  warning: 'bg-brand-amber-light text-brand-amber',
  danger:  'bg-brand-red-light text-brand-red',
  info:    'bg-brand-light text-brand-primary border border-brand-mid',
  neutral: 'bg-gray-100 text-brand-body',
  gold:    'bg-brand-gold-light text-brand-gold-dark border border-brand-gold-mid',
}

export function Badge({ variant = 'neutral', children, pulse = false }: BadgeProps) {
  return (
    <span className={[
      'inline-flex items-center gap-1.5 px-3 py-1 rounded-full',
      'text-xs font-bold',
      variantClasses[variant],
    ].join(' ')}>
      {pulse && (
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" aria-hidden="true" />
      )}
      {children}
    </span>
  )
}
```

---

#### `Input.tsx`

```tsx
import React from 'react'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
  hint?: string
}

export function Input({ label, error, hint, id, className = '', ...props }: InputProps) {
  const inputId = id ?? label.toLowerCase().replace(/\s+/g, '-')
  return (
    <div className="w-full">
      <label
        htmlFor={inputId}
        className="block text-sm font-semibold text-brand-ink mb-1.5"
      >
        {label}
      </label>
      <input
        id={inputId}
        className={[
          'w-full bg-white border rounded-xl px-4 py-2.5',
          'text-brand-ink placeholder:text-brand-muted text-sm font-normal',
          'transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          error ? 'border-brand-red' : 'border-brand-border',
          className,
        ].join(' ')}
        aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
        aria-invalid={error ? 'true' : undefined}
        {...props}
      />
      {error && (
        <p id={`${inputId}-error`} className="text-xs text-brand-red mt-1.5 flex items-center gap-1" role="alert">
          {error}
        </p>
      )}
      {hint && !error && (
        <p id={`${inputId}-hint`} className="text-xs text-brand-muted mt-1.5">
          {hint}
        </p>
      )}
    </div>
  )
}
```

---

#### `Skeleton.tsx`

```tsx
import React from 'react'

interface SkeletonProps {
  className?: string
  lines?: number   // render N stacked skeleton lines
}

export function Skeleton({ className = '', lines }: SkeletonProps) {
  if (lines) {
    return (
      <div className="animate-pulse space-y-3">
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className={`h-4 bg-brand-border rounded-full ${i === lines - 1 ? 'w-2/3' : 'w-full'}`}
          />
        ))}
      </div>
    )
  }
  return <div className={`animate-pulse bg-brand-border rounded-xl ${className}`} />
}

export function SkeletonCard() {
  return (
    <div className="bg-white rounded-2xl border border-brand-border p-5 animate-pulse">
      <div className="h-4 bg-brand-border rounded-full w-1/3 mb-4" />
      <div className="h-8 bg-brand-border rounded-full w-1/2 mb-2" />
      <div className="h-3 bg-brand-border rounded-full w-2/3" />
    </div>
  )
}
```

---

#### `EmptyState.tsx`

```tsx
import React from 'react'

interface EmptyStateProps {
  emoji: string
  title: string
  description: string
  action?: React.ReactNode
}

export function EmptyState({ emoji, title, description, action }: EmptyStateProps) {
  return (
    <div className="text-center py-16 px-6">
      <div className="text-4xl mb-4" role="img" aria-label={title}>{emoji}</div>
      <h3 className="font-display font-bold text-xl text-brand-ink mb-2">{title}</h3>
      <p className="text-brand-body text-sm max-w-sm mx-auto leading-relaxed">{description}</p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}
```

---

#### `ProgressBar.tsx`

```tsx
import React from 'react'

interface ProgressBarProps {
  value: number          // 0–100
  max?: number
  label?: string
  colorClass?: string    // default: bg-brand-primary
  size?: 'sm' | 'md'
}

export function ProgressBar({
  value,
  max = 100,
  label,
  colorClass = 'bg-brand-primary',
  size = 'sm',
}: ProgressBarProps) {
  const pct = Math.min(100, Math.max(0, Math.round((value / max) * 100)))
  const heightClass = size === 'sm' ? 'h-2' : 'h-3'
  return (
    <div>
      {label && (
        <div className="flex justify-between text-xs font-semibold text-brand-body mb-1.5">
          <span>{label}</span>
          <span>{pct}%</span>
        </div>
      )}
      <div className={`w-full bg-brand-border-soft rounded-full ${heightClass}`}>
        <div
          className={`${colorClass} ${heightClass} rounded-full transition-all duration-500`}
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={label}
        />
      </div>
    </div>
  )
}
```

---

### `packages/ui/src/index.ts` — exports

```typescript
// Components
export { Button } from './components/Button'
export { Card } from './components/Card'
export { Badge } from './components/Badge'
export { Input } from './components/Input'
export { Skeleton, SkeletonCard } from './components/Skeleton'
export { EmptyState } from './components/EmptyState'
export { ProgressBar } from './components/ProgressBar'
// LoginForm (already built in M0-3-T5)
export { LoginForm } from './LoginForm'
// Layouts — exported when M0-7-T1 is complete
// export { DashboardLayout } from './layouts/DashboardLayout'
// export { StudentLayout } from './layouts/StudentLayout'
// export { ParentLayout } from './layouts/ParentLayout'
// export { AdminLayout } from './layouts/AdminLayout'
// export { AuthLayout } from './layouts/AuthLayout'
// export { OnboardingLayout } from './layouts/OnboardingLayout'
```

---

## Part B — `packages/api-client` Scaffold

`packages/api-client` should re-export the `apiClient` from `@kaihle/auth` for now,
and define the typed base for future API hooks.

**`frontend/packages/api-client/src/index.ts`**:

```typescript
/**
 * Kaihle API client.
 * Re-exports the shared Axios instance from @kaihle/auth.
 * Future: typed React Query hooks will live here.
 */
export { apiClient } from '@kaihle/auth'
```

**`frontend/packages/api-client/package.json`**:
```json
{
  "name": "@kaihle/api-client",
  "version": "0.1.0",
  "main": "src/index.ts",
  "types": "src/index.ts",
  "dependencies": {
    "@kaihle/auth": "workspace:*",
    "@tanstack/react-query": "^5.0.0"
  }
}
```

This is intentionally minimal — its purpose is to give future tasks a clean import path
(`import { apiClient } from '@kaihle/api-client'`) so the auth package doesn't own the
HTTP client long-term. Full typed hooks are added in M1+ as needed.

---

## Files to Create

```
frontend/packages/ui/package.json
frontend/packages/ui/src/components/Button.tsx
frontend/packages/ui/src/components/Card.tsx
frontend/packages/ui/src/components/Badge.tsx
frontend/packages/ui/src/components/Input.tsx
frontend/packages/ui/src/components/Skeleton.tsx
frontend/packages/ui/src/components/EmptyState.tsx
frontend/packages/ui/src/components/ProgressBar.tsx
frontend/packages/ui/src/index.ts
frontend/packages/api-client/package.json
frontend/packages/api-client/src/index.ts
```

---

## Acceptance Criteria

- [ ] `import { Button, Card, Badge, Input, Skeleton, EmptyState, ProgressBar } from '@kaihle/ui'` resolves in teacher, student, and parent apps
- [ ] `import { apiClient } from '@kaihle/api-client'` resolves in all three apps
- [ ] `Button variant="primary"` renders with `bg-brand-primary` (#1a5c38) background
- [ ] `Button loading={true}` shows spinner and is disabled
- [ ] `Button` has visible focus ring: `focus-visible:ring-2 focus-visible:ring-brand-primary`
- [ ] `Input` renders with visible label, error state shows red border + red error message
- [ ] `Input` has `aria-invalid="true"` when error is set
- [ ] `Skeleton lines={3}` renders 3 animated gray lines
- [ ] `ProgressBar value={73}` renders 73% fill width with smooth transition
- [ ] `EmptyState` renders emoji + title + description + optional action
- [ ] `tsc --noEmit` passes with zero errors in all apps and packages
- [ ] `pnpm --filter @kaihle/ui test` passes (add basic render tests with RTL)
- [ ] All touch targets: `min-h-[44px]` on Button md and lg sizes
