# M0-8-T7 — Shared Modal Component (packages/ui)
**Milestone:** M0 — Foundations
**Epic:** M0-8 — Pre-flight Fixes
**Task ID:** M0-8-T7
**Depends on:** M0-8-T4 (packages/ui foundation exists), M0-8-T6 (Radix UI chosen as dependency pattern)
**Blocks:** Every task that creates a modal: M0-7-T4 (InviteUserModal, CreateClassModal), M0-7-T5 (AdminCreateSchoolModal, AdminExtendTrialModal), M3-2-T4 (AssignStudyPlanModal), M6-2-T1 (billing modals)
**Estimated effort:** 2–3 hours
**Design sprint:** Pixel (component spec + accessibility) · Kramer (implementation) · Vidhya (label language review)

> **Why this task exists:**
> `docs/design/DESIGN_SYSTEM_ACCESSIBILITY_ADDENDUM.md` §9 specifies a canonical
> `Modal` component using Radix UI `Dialog` that guarantees: Tab traps inside the
> modal, Escape closes it, focus returns to the trigger on close. CONSTITUTION Rule 21
> mandates all modals use it.
>
> The component is specified but never built. Six existing task files reference modals
> (InviteUserModal, CreateClassModal, AdminCreateSchoolModal, AdminExtendTrialModal,
> AssignStudyPlanModal, DeactivateUserModal) — all of them will produce non-accessible
> custom div-based implementations unless this task ships first.
>
> This must complete before any modal-using task begins.

---

## Pixel — Component Specification

### Design approach

The `Modal` component is a thin Kaihle-styled wrapper around Radix UI `Dialog`. It
handles all focus management, keyboard behaviour, and ARIA automatically. Developers
using it write only the modal body content — they never touch focus traps or aria
attributes directly.

The component must support the visual language of all five role design systems because
modals are used across all apps. The heading font varies by role: Fraunces for Teacher,
Student, School Admin, Parent; Inter for Kaihle Admin.

### Component Spec

```
Component: Modal
File: packages/ui/src/components/Modal.tsx
Exports: { Modal } from '@kaihle/ui'
─────────────────────────────────────────────────────
Props:
  open:         boolean               — controlled open state
  onOpenChange: (open: boolean) => void — called on close (Escape, overlay click, close button)
  title:        string                — required; displayed as heading; linked via aria-labelledby
  description?: string               — optional; displayed below title; linked via aria-describedby
  children:     React.ReactNode       — modal body content
  maxWidth?:    'sm' | 'md' | 'lg'   — default 'md'
  hideCloseButton?: boolean          — default false; set true for non-dismissable modals
  titleClassName?: string            — override heading class (use for KaihleAdmin Inter font)
─────────────────────────────────────────────────────
Max widths:
  sm: max-w-sm  (384px)
  md: max-w-md  (448px)
  lg: max-w-lg  (512px)
─────────────────────────────────────────────────────
Visual spec:

Overlay:
  fixed inset-0 z-40
  bg-black/40 backdrop-blur-[2px]
  Fade animation:
    data-[state=open]:animate-in data-[state=open]:fade-in-0
    data-[state=closed]:animate-out data-[state=closed]:fade-out-0
    motion-safe: transition-opacity duration-200

Content panel:
  fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2
  z-50 w-full {maxWidth}
  bg-white rounded-2xl shadow-xl
  p-6
  Entrance animation:
    data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95
    data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95
    motion-safe: transition-all duration-200

Close button (top-right):
  absolute right-4 top-4
  w-8 h-8 rounded-full
  flex items-center justify-center
  text-gray-400 hover:text-gray-600 hover:bg-gray-100
  transition-colors
  focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1
  aria-label="Close"
  Icon: X from lucide-react, w-4 h-4 aria-hidden="true"

Title:
  Default: font-fraunces text-xl text-brand-ink font-bold mb-1 pr-8
  Override via titleClassName prop (KaihleAdmin uses: "font-inter text-xl font-bold text-gray-900 mb-1 pr-8")

Description (optional):
  text-sm text-gray-500 mb-4

Children:
  Rendered below title/description
─────────────────────────────────────────────────────
Keyboard behaviour (all from Radix UI Dialog — zero custom code needed):
  Tab         → cycles forward through focusable elements inside the modal ONLY
  Shift+Tab   → cycles backward
  Escape      → closes modal, calls onOpenChange(false)
  Enter       → activates focused button/control inside modal
  Click outside → closes modal, calls onOpenChange(false)
                  (only when modal body is not a form — configure via Radix onInteractOutside)
─────────────────────────────────────────────────────
Accessibility (all automatic via Radix Dialog):
  role="dialog"
  aria-modal="true"
  aria-labelledby → links to title element
  aria-describedby → links to description element (when provided)
  Focus: on open → first focusable element inside modal receives focus
  Focus restore: on close → focus returns to the element that triggered the modal
─────────────────────────────────────────────────────
Mobile:
  Same layout — Radix Dialog works at any viewport
  On very small screens (< 380px): maxWidth is 'calc(100vw - 32px)' with mx-4
  The -translate-x/y centering always keeps it on screen
```

### Usage examples

**Standard destructive modal (Deactivate User):**
```tsx
import { Modal } from '@kaihle/ui'

function DeactivateUserModal({ open, onClose, userName, onConfirm }) {
  return (
    <Modal
      open={open}
      onOpenChange={onClose}
      title={`Deactivate ${userName}?`}
      description="This will prevent them from logging in. School admin can reactivate them."
      maxWidth="sm"
    >
      <div className="flex gap-3 mt-4 justify-end">
        <button onClick={onClose} className="...ghost...">Cancel</button>
        <button onClick={onConfirm} className="...bg-red-600...">Deactivate</button>
      </div>
    </Modal>
  )
}
```

**KaihleAdmin modal (Inter font):**
```tsx
<Modal
  open={open}
  onOpenChange={onClose}
  title="Extend trial"
  titleClassName="font-inter text-xl font-bold text-gray-900 mb-1 pr-8"
  maxWidth="md"
>
  {/* form content */}
</Modal>
```

**Non-dismissable modal (password setup — cannot Escape out):**
```tsx
// Disable Escape and overlay click for critical flows
<Modal
  open={open}
  onOpenChange={() => {}} // no-op — prevent accidental close
  title="Set your password"
  hideCloseButton={true}
>
  <PasswordSetupForm ... />
</Modal>
```

---

## Vidhya — Label Language Review

For any modal that involves student data or educational context, the title and
description must follow these principles:

**Modal titles:**
- Use action + object: "Deactivate {name}?" / "Extend trial — {school}" / "Assign study plan"
- Never technical IDs: ❌ "DELETE /users/123" ✅ "Remove Emma from this class"
- Sentence case, not title case for descriptions
- Question mark on destructive confirms only: "Delete this assessment?" ✓

**Destructive modal descriptions must:**
- State the consequence clearly: "This cannot be undone." where true
- State the recovery path when one exists: "School admin can reactivate them."
- Never use technical jargon: ❌ "This will set is_active=false" ✅ "They won't be able to log in."

**Form modals:**
- Required fields should be marked "(required)" below the label, not with asterisk alone
- Error messages in modals must use plain language, same standards as settings pages

---

## Kramer — Implementation

### Install dependency

```bash
pnpm --filter @kaihle/ui add @radix-ui/react-dialog
```

Add to `frontend/packages/ui/package.json`:
```json
{
  "dependencies": {
    "@radix-ui/react-dialog": "^1.0.5",
    "lucide-react": "^0.383.0"
  }
}
```

### Full implementation

```tsx
// frontend/packages/ui/src/components/Modal.tsx
import React from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'

type ModalMaxWidth = 'sm' | 'md' | 'lg'

interface ModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  children: React.ReactNode
  maxWidth?: ModalMaxWidth
  hideCloseButton?: boolean
  titleClassName?: string
}

const maxWidthMap: Record<ModalMaxWidth, string> = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
}

export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
  maxWidth = 'md',
  hideCloseButton = false,
  titleClassName,
}: ModalProps) {
  const defaultTitleClass =
    'font-fraunces text-xl text-brand-ink font-bold mb-1 pr-8'

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        {/* Backdrop overlay */}
        <Dialog.Overlay
          className={[
            'fixed inset-0 z-40',
            'bg-black/40 backdrop-blur-[2px]',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0',
            'motion-safe:transition-opacity motion-safe:duration-200',
          ].join(' ')}
        />

        {/* Modal panel */}
        <Dialog.Content
          className={[
            'fixed left-1/2 top-1/2 z-50',
            '-translate-x-1/2 -translate-y-1/2',
            'w-[calc(100vw-32px)]', // full width minus 16px margins on mobile
            maxWidthMap[maxWidth],
            'bg-white rounded-2xl shadow-xl p-6',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95',
            'motion-safe:transition-all motion-safe:duration-200',
            'focus:outline-none',
          ].join(' ')}
        >
          {/* Close button */}
          {!hideCloseButton && (
            <Dialog.Close
              className={[
                'absolute right-4 top-4',
                'w-8 h-8 rounded-full',
                'flex items-center justify-center',
                'text-gray-400 hover:text-gray-600 hover:bg-gray-100',
                'transition-colors',
                'focus-visible:outline-none focus-visible:ring-2',
                'focus-visible:ring-brand-primary focus-visible:ring-offset-1',
              ].join(' ')}
              aria-label="Close"
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </Dialog.Close>
          )}

          {/* Title */}
          <Dialog.Title className={titleClassName ?? defaultTitleClass}>
            {title}
          </Dialog.Title>

          {/* Optional description */}
          {description && (
            <Dialog.Description className="text-sm text-gray-500 mb-4">
              {description}
            </Dialog.Description>
          )}

          {/* Body content */}
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
```

### Update `packages/ui/src/index.ts`

Add this export alongside existing exports:
```typescript
export { Modal } from './components/Modal'
```

The current index.ts exports Button, Card, Badge, Input, Skeleton, SkeletonCard,
EmptyState, ProgressBar, LoginForm, PasswordSetupForm, DashboardLayout, StudentLayout,
ParentLayout, AdminLayout, AuthLayout, OnboardingLayout, NavItem, Sidebar, TopNav,
BottomNav. Add Modal to this list.

### Files to Create / Modify

```
frontend/packages/ui/src/components/Modal.tsx          ← CREATE
frontend/packages/ui/src/index.ts                      ← MODIFY: add Modal export
frontend/packages/ui/package.json                      ← MODIFY: add @radix-ui/react-dialog
frontend/packages/ui/src/components/__tests__/
  Modal.test.tsx                                        ← CREATE
```

---

## Unit Tests

```tsx
// Modal.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Modal } from '../Modal'

function TestModal({ open = true, onOpenChange = jest.fn() }) {
  return (
    <Modal open={open} onOpenChange={onOpenChange} title="Test modal">
      <button>Inside button</button>
    </Modal>
  )
}

describe('Modal', () => {
  it('test_renders_title_when_open', () => {
    render(<TestModal />)
    expect(screen.getByText('Test modal')).toBeInTheDocument()
  })

  it('test_renders_children_when_open', () => {
    render(<TestModal />)
    expect(screen.getByRole('button', { name: 'Inside button' })).toBeInTheDocument()
  })

  it('test_not_rendered_when_closed', () => {
    render(<TestModal open={false} />)
    expect(screen.queryByText('Test modal')).not.toBeInTheDocument()
  })

  it('test_close_button_calls_onOpenChange', async () => {
    const onOpenChange = jest.fn()
    render(<TestModal onOpenChange={onOpenChange} />)
    await userEvent.click(screen.getByLabelText('Close'))
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('test_escape_key_calls_onOpenChange', async () => {
    const onOpenChange = jest.fn()
    render(<TestModal onOpenChange={onOpenChange} />)
    await userEvent.keyboard('{Escape}')
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('test_has_dialog_role', () => {
    render(<TestModal />)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('test_title_linked_via_aria_labelledby', () => {
    render(<TestModal />)
    const dialog = screen.getByRole('dialog')
    const titleId = dialog.getAttribute('aria-labelledby')
    expect(titleId).toBeTruthy()
    const title = document.getElementById(titleId!)
    expect(title?.textContent).toBe('Test modal')
  })

  it('test_description_linked_via_aria_describedby_when_provided', () => {
    render(
      <Modal open={true} onOpenChange={jest.fn()} title="Test" description="Test desc">
        <div />
      </Modal>
    )
    const dialog = screen.getByRole('dialog')
    const descId = dialog.getAttribute('aria-describedby')
    expect(descId).toBeTruthy()
    const desc = document.getElementById(descId!)
    expect(desc?.textContent).toBe('Test desc')
  })

  it('test_hide_close_button_removes_close_button', () => {
    render(<TestModal />)
    // Default: close button visible
    expect(screen.getByLabelText('Close')).toBeInTheDocument()

    const { rerender } = render(
      <Modal open={true} onOpenChange={jest.fn()} title="T" hideCloseButton={true}>
        <div />
      </Modal>
    )
    expect(screen.queryByLabelText('Close')).not.toBeInTheDocument()
  })

  it('test_custom_title_class_applied', () => {
    render(
      <Modal open={true} onOpenChange={jest.fn()} title="Admin title"
             titleClassName="font-inter text-xl font-bold">
        <div />
      </Modal>
    )
    const title = screen.getByText('Admin title')
    expect(title).toHaveClass('font-inter')
  })
})
```

---

## Acceptance Criteria

- [ ] `import { Modal } from '@kaihle/ui'` resolves in all 5 apps
- [ ] Modal renders with `role="dialog"` and `aria-modal="true"` (from Radix)
- [ ] Modal title is linked via `aria-labelledby`
- [ ] Modal description (when provided) is linked via `aria-describedby`
- [ ] Close button calls `onOpenChange(false)`
- [ ] Escape key calls `onOpenChange(false)` (Radix handles this)
- [ ] `hideCloseButton={true}` removes the X button
- [ ] `titleClassName` prop overrides heading class (enables Inter for KaihleAdmin)
- [ ] Overlay and content have `motion-safe:` prefixed animations
- [ ] `@radix-ui/react-dialog` added to `packages/ui/package.json`
- [ ] `Modal` added to `packages/ui/src/index.ts` exports
- [ ] All Jest unit tests pass
- [ ] `tsc --noEmit` passes in packages/ui and all 5 apps

---

## What changes in existing task files post-merge

All task files that specify a custom modal must now reference `<Modal>` instead.
The following existing task files should have this note added to their "Do NOT Touch"
or "Context" section:

- `M0-7-T4` → `InviteUserModal`, `CreateClassModal` must use `<Modal from '@kaihle/ui'>`
- `M0-7-T5` → `AdminCreateSchoolModal`, `AdminExtendTrialModal` must use `<Modal>`
- `M0-7-T5d` → `DeactivateUserModal` must use `<Modal>`
- `M3-2-T4` → `AssignStudyPlanModal` must use `<Modal>`

This does not require those task files to be rewritten — just note it in the handoff
to coding agents: "Use `<Modal>` from `@kaihle/ui` per CONSTITUTION Rule 21."

---

## Do NOT Touch

- Any existing component implementations — only adding Modal
- Any app-level code — only packages/ui changes here
- Radix UI internals — use the library's API, never monkey-patch
