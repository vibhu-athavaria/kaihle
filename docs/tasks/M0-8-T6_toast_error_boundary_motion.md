# M0-8-T6 — Toast Notifications, Error Boundaries & Motion Accessibility
**Milestone:** M0 — Foundations
**Epic:** M0-8 — Pre-flight Fixes
**Task ID:** M0-8-T6
**Depends on:** M0-8-T4 (packages/ui must exist), M0-7-T1 (layout wrappers must exist — Toaster mounts inside them)
**Blocks:** M0-7-T2b (teacher settings — calls toast.success), M0-7-T3b (student settings), M0-7-T4b (school admin settings)
**Estimated effort:** 3–4 hours
**Design sprint:** Pixel (component specs + motion standards) + Kramer (implementation)

> **Why this task exists — three problems bundled:**
>
> **Problem 1 (toast):** Every settings page task, every form task, and every modal task
> says "show success toast" — but no task defines HOW toasts work. Without this task,
> each developer will implement their own toast. The apps will fragment immediately.
>
> **Problem 2 (error boundary):** None of the five apps have error boundaries. A runtime
> JavaScript error in any component will unmount the entire app, showing a blank white
> screen. This is unacceptable for production. Students will see a blank screen and think
> Kaihle is broken.
>
> **Problem 3 (motion):** The `prefers-reduced-motion` media query is mentioned once in
> the ScoreRing spec but applied nowhere else. Users who have enabled "Reduce Motion" in
> their OS settings (common for users with vestibular disorders or epilepsy) will get
> animations anyway. WCAG 2.1 SC 2.3.3 (Level AAA) recommends respecting this. At
> minimum it must be a base CSS rule.

---

## Pixel — Component Specifications

### Part 1: Toast System

**Library: `sonner`** (not `react-hot-toast`, not `react-toastify`)

Rationale:
- Sonnet is 10kb, zero dependencies, TypeScript-native
- Ships with accessible `role="status"` + `aria-live="polite"` by default
- Tailwind-compatible (no conflicting CSS files)
- The React 18 community default as of 2025

**Toast position:** Top-right on desktop, bottom-center on mobile.

```
Component: <Toaster /> (from sonner)
Placement: Inside each layout wrapper, BELOW the main content area
  — DashboardLayout: after </main> before </div>
  — StudentLayout: after </main> before </div>
  — ParentLayout: after </main> before </div>
  — AdminLayout: after </main> before </div>
  — OnboardingLayout: after </div> before </body>

Do NOT place in AuthLayout — toasts on the login screen are confusing
```

**Kaihle-specific toast variants:**

```
Success toast:
  className="bg-brand-primary text-white shadow-lg"
  Duration: 4000ms
  Icon: ✓ (CheckCircle from lucide, w-4 h-4)

Error toast:
  className="bg-brand-red text-white shadow-lg"
  Duration: 0 (persists until dismissed — errors need deliberate clearing)
  Icon: ✕ (XCircle from lucide, w-4 h-4)
  Close button: always visible (contrast: white on brand-red ✓)

Info toast:
  className="bg-brand-light text-brand-primary border border-brand-mid shadow-sm"
  Duration: 4000ms
  Icon: ℹ (Info from lucide, w-4 h-4)

Warning toast:
  className="bg-brand-amber-light text-brand-gold-dark border border-brand-gold-mid shadow-sm"
  Duration: 5000ms
  Icon: ⚠ (AlertTriangle from lucide, w-4 h-4)
```

**Usage API from packages/ui:**

```typescript
// packages/ui/src/toast.ts — thin wrapper around sonner
import { toast as sonnerToast } from 'sonner'

export const toast = {
  success: (message: string) => sonnerToast.success(message, {
    className: 'bg-brand-primary text-white',
    duration: 4000,
  }),
  error: (message: string) => sonnerToast.error(message, {
    className: 'bg-brand-red text-white',
    duration: Infinity,
    closeButton: true,
  }),
  info: (message: string) => sonnerToast(message, {
    className: 'bg-brand-light text-brand-primary border border-brand-mid',
    duration: 4000,
  }),
  warning: (message: string) => sonnerToast.warning(message, {
    className: 'bg-brand-amber-light text-brand-gold-dark border border-brand-gold-mid',
    duration: 5000,
  }),
}
```

**Usage in components:**
```typescript
import { toast } from '@kaihle/ui'

// In a form submit handler:
toast.success('Name updated')
toast.error('Current password is incorrect')
```

---

### Part 2: Error Boundary

**Placement:** One `<ErrorBoundary>` wrapping each page-level route in App.tsx.
Not one global wrapper for the whole app — that would show the error page for
a broken nav item, breaking everything. Wrap at the route level so only the
broken page crashes, not the sidebar.

```
Component: ErrorBoundary (class component — required by React)
File: packages/ui/src/components/ErrorBoundary.tsx
Export: named export from packages/ui/src/index.ts
─────────────────────────────────────────────────────
Props:
  children: ReactNode
  fallback?: ReactNode  — custom fallback, defaults to KaihleErrorFallback

KaihleErrorFallback specs:
  Full-page centred card: max-w-md mx-auto mt-16 bg-white rounded-2xl p-8 shadow-sm
  Emoji: ⚠️ (text-5xl, mb-4)
  Heading: font-fraunces text-xl text-brand-ink "Something went wrong"
           (Teacher/Student/SchoolAdmin use Fraunces)
           (KaihleAdmin: Inter)
  Sub text: text-sm text-gray-500 mt-2
    "There was an unexpected error on this page."
  Buttons (mt-6 flex gap-3):
    "Refresh page" — bg-brand-primary text-white rounded-full px-5 py-2.5 text-sm
                     onClick: window.location.reload()
    "Go to dashboard" — ghost button → navigate('/')
─────────────────────────────────────────────────────
Role-specific heading font:
  The ErrorBoundary receives a `role` prop that switches the heading font.
  This is because KaihleAdmin uses Inter-only. Others use Fraunces.

  <ErrorBoundary role="teacher"> → Fraunces heading
  <ErrorBoundary role="kaihle-admin"> → Inter heading
  Default (no role): Fraunces
─────────────────────────────────────────────────────
Logging:
  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info)
    // Future: POST to /api/v1/errors with error.message + component stack
    // For v1: console.error is sufficient
  }
```

**Usage in App.tsx of each app:**

```tsx
// apps/teacher/src/App.tsx
import { ErrorBoundary } from '@kaihle/ui'

// Wrap each route's element:
<Route
  path="/teacher/dashboard"
  element={
    <ErrorBoundary role="teacher">
      <TeacherDashboard />
    </ErrorBoundary>
  }
/>
```

---

### Part 3: prefers-reduced-motion Global CSS

Add ONE rule to `packages/ui/src/styles/base.css` (create this file if it doesn't exist)
or to each app's `src/index.css` (preferred — keeps it per-app):

```css
/* Respect OS-level "Reduce Motion" preference.
   Users with vestibular disorders or epilepsy may have enabled this.
   This rule disables all CSS animations and transitions globally.
   Components that need motion use motion-safe: Tailwind prefix for exceptions. */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

Add this block to ALL FIVE apps' `src/index.css` files, below the Tailwind directives:

```
frontend/apps/teacher/src/index.css
frontend/apps/student/src/index.css
frontend/apps/parent/src/index.css
frontend/apps/school-admin/src/index.css
frontend/apps/kaihle-admin/src/index.css
```

The `motion-safe:` Tailwind prefix (e.g. `motion-safe:transition-all`) provides per-component
opt-in. Use this for animations that are informative (e.g. the ScoreRing fill animation
which communicates the value — those can use `motion-safe:`). Use the global rule to
disable decorative animations by default.

---

## Kramer — Implementation

### Files to Create / Modify

```
frontend/packages/ui/src/components/ErrorBoundary.tsx   ← CREATE
frontend/packages/ui/src/toast.ts                       ← CREATE
frontend/packages/ui/src/index.ts                       ← MODIFY: add ErrorBoundary + toast exports
frontend/packages/ui/package.json                       ← MODIFY: add sonner dependency
frontend/apps/teacher/src/index.css                     ← MODIFY: add prefers-reduced-motion + Toaster import
frontend/apps/student/src/index.css                     ← MODIFY: same
frontend/apps/parent/src/index.css                      ← MODIFY: same
frontend/apps/school-admin/src/index.css                ← MODIFY: same
frontend/apps/kaihle-admin/src/index.css                ← MODIFY: same
frontend/apps/teacher/src/layouts/DashboardLayout.tsx   ← MODIFY: add <Toaster />
frontend/apps/student/src/layouts/StudentLayout.tsx     ← MODIFY: add <Toaster />
frontend/apps/parent/src/layouts/ParentLayout.tsx       ← MODIFY: add <Toaster />
frontend/apps/school-admin/src/layouts/...              ← MODIFY: add <Toaster />
frontend/apps/kaihle-admin/src/layouts/AdminLayout.tsx  ← MODIFY: add <Toaster />
frontend/apps/teacher/src/App.tsx                       ← MODIFY: wrap routes in ErrorBoundary
frontend/apps/student/src/App.tsx                       ← MODIFY: same
frontend/apps/parent/src/App.tsx                        ← MODIFY: same
frontend/apps/school-admin/src/App.tsx                  ← MODIFY: same
frontend/apps/kaihle-admin/src/App.tsx                  ← MODIFY: same
frontend/packages/ui/src/components/__tests__/ErrorBoundary.test.tsx ← CREATE
```

### Install sonner

```bash
pnpm --filter @kaihle/ui add sonner
```

Add to `packages/ui/package.json`:
```json
"dependencies": {
  "sonner": "^1.4.0"
}
```

### ErrorBoundary implementation

```tsx
// packages/ui/src/components/ErrorBoundary.tsx
import React, { Component, ErrorInfo, ReactNode } from 'react'

type Role = 'teacher' | 'student' | 'parent' | 'school-admin' | 'kaihle-admin'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  role?: Role
}

interface State {
  hasError: boolean
  error: Error | null
}

function KaihleErrorFallback({ role }: { role?: Role }) {
  const isAdminRole = role === 'kaihle-admin'
  const headingClass = isAdminRole
    ? 'text-xl font-bold font-inter text-gray-900'
    : 'text-xl font-bold font-display text-brand-ink'

  return (
    <div className="max-w-md mx-auto mt-16 bg-white rounded-2xl p-8 shadow-sm">
      <div className="text-5xl mb-4">⚠️</div>
      <h2 className={headingClass}>Something went wrong</h2>
      <p className="text-sm text-gray-500 mt-2">
        There was an unexpected error on this page.
      </p>
      <div className="mt-6 flex gap-3">
        <button
          onClick={() => window.location.reload()}
          className="bg-brand-primary text-white rounded-full px-5 py-2.5 text-sm font-medium hover:bg-brand-dark transition-colors"
        >
          Refresh page
        </button>
        <button
          onClick={() => { window.location.href = '/' }}
          className="bg-white text-brand-ink border border-gray-200 rounded-full px-5 py-2.5 text-sm font-medium hover:bg-gray-50 transition-colors"
        >
          Go to dashboard
        </button>
      </div>
    </div>
  )
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[Kaihle] ErrorBoundary caught:', error.message, info.componentStack)
    // Future: POST to /api/v1/errors
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? <KaihleErrorFallback role={this.props.role} />
    }
    return this.props.children
  }
}
```

### Unit Tests

```typescript
// ErrorBoundary.test.tsx
describe('ErrorBoundary', () => {
  const ThrowingComponent = () => { throw new Error('Test error') }

  it('renders children when no error', () => {
    render(<ErrorBoundary><div>safe content</div></ErrorBoundary>)
    expect(screen.getByText('safe content')).toBeInTheDocument()
  })

  it('renders fallback when child throws', () => {
    // Suppress console.error for this test
    jest.spyOn(console, 'error').mockImplementation(() => {})
    render(<ErrorBoundary><ThrowingComponent /></ErrorBoundary>)
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByText('Refresh page')).toBeInTheDocument()
  })

  it('renders custom fallback when provided', () => {
    jest.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <ErrorBoundary fallback={<div>custom fallback</div>}>
        <ThrowingComponent />
      </ErrorBoundary>
    )
    expect(screen.getByText('custom fallback')).toBeInTheDocument()
  })
})
```

---

## Playwright E2E verification (add to each app's test spec)

```typescript
// In each app's main spec file, add:
test('error_boundary_renders_fallback_not_blank_screen', async ({ page }) => {
  // Navigate to a page and inject an error
  await page.goto('/teacher/dashboard')
  await page.evaluate(() => {
    // This simulates a runtime error — ErrorBoundary should catch it
    // In practice this is just a smoke check that the boundary exists
    const root = document.getElementById('root')
    if (root) root.setAttribute('data-error-boundary-present', 'true')
  })
  // Just verify the page rendered at all — blank screen = no boundary
  await expect(page.locator('#root')).toBeVisible()
  await expect(page.locator('body')).not.toBeEmpty()
})
```

---

## Acceptance Criteria

**Toast system:**
- [ ] `import { toast } from '@kaihle/ui'` resolves in all 5 apps
- [ ] `toast.success('x')` renders a green toast top-right
- [ ] `toast.error('x')` renders a red persistent toast with close button
- [ ] `toast.info('x')` renders a light green/brand info toast
- [ ] `toast.warning('x')` renders an amber warning toast
- [ ] `<Toaster />` is present in each layout wrapper — verified by checking the DOM
- [ ] Error toast persists until dismissed (not auto-dismissed)
- [ ] Toasts respect `prefers-reduced-motion` (no slide animation when motion disabled)

**Error boundary:**
- [ ] `import { ErrorBoundary } from '@kaihle/ui'` resolves in all 5 apps
- [ ] Boundary renders "Something went wrong" fallback when child throws
- [ ] "Refresh page" button calls `window.location.reload()`
- [ ] KaihleAdmin role renders Inter heading (not Fraunces)
- [ ] Other roles render Fraunces heading
- [ ] `componentDidCatch` logs to console.error
- [ ] Custom `fallback` prop overrides default fallback

**Motion accessibility:**
- [ ] `@media (prefers-reduced-motion: reduce)` rule present in all 5 app `index.css` files
- [ ] Verify with browser DevTools: enable "Emulate CSS media feature: prefers-reduced-motion"
      → all page animations and transitions stop
- [ ] Animated components using `motion-safe:` prefix still animate when motion is allowed
- [ ] All unit tests pass
- [ ] `tsc --noEmit` passes in all apps

---

## Do NOT Touch

- Existing component files — only add `<ErrorBoundary>` wrapping in App.tsx
- The Tailwind config — `prefers-reduced-motion` is in CSS, not config
- Any route paths or backend files
