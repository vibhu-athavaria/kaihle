# Design System Accessibility Addendum
**Version:** 2.1 (addendum to DESIGN_SYSTEM.md v2.0)
**Date:** March 2026
**Authority:** Pixel (UX/UI Lead)
**Status:** Authoritative — load alongside DESIGN_SYSTEM.md for every frontend task

> **This document extends `docs/design/DESIGN_SYSTEM.md`.**
> It adds two missing standards identified in the gap audit:
> 1. Modal focus trap pattern (required by WCAG 2.1 AA)
> 2. Loading state standards (prevents inconsistent UX across the platform)
>
> The CONSTITUTION.md update to add Rule 21 (modal focus trap mandate) is included
> at the bottom of this document. Apply it to CONSTITUTION.md in the same commit
> that merges this file.

---

## §9 Addition — Modal Focus Trap Pattern

### Why this is non-negotiable

WCAG 2.1 Success Criterion 2.1.2 (Keyboard, Level AA): "If keyboard focus can be moved
to a component of the page using a keyboard interface, then focus can be moved away from
that component using only a keyboard interface."

Without a focus trap, pressing Tab in an open modal will cycle through the entire page
behind the modal. Screen readers and keyboard users lose context immediately. This is
a WCAG AA failure — not a nice-to-have.

### The canonical modal pattern for Kaihle

All modals in all five apps must follow this pattern. The recommended implementation
is **Radix UI `Dialog`** (`@radix-ui/react-dialog`) which handles focus management,
focus trapping, Escape key dismissal, and ARIA attributes automatically.

**Why Radix UI Dialog, not a custom implementation:**
- Handles focus trap automatically — Tab cycles within the dialog only
- Restores focus to the trigger element on close
- Ships with correct `role="dialog"`, `aria-modal="true"`, and `aria-labelledby`
- Used internally by shadcn/ui (which some components already reference)
- Headless — no conflicting CSS
- Zero additional bundle cost if already used elsewhere

### Installation

```bash
pnpm --filter @kaihle/ui add @radix-ui/react-dialog
```

Add to `packages/ui/package.json`:
```json
"dependencies": {
  "@radix-ui/react-dialog": "^1.0.5"
}
```

### Kaihle Modal wrapper component

Export a pre-styled `Modal` from `packages/ui` so individual app developers never
interact with Radix directly:

```tsx
// packages/ui/src/components/Modal.tsx
import React from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'

interface ModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  children: React.ReactNode
  maxWidth?: 'sm' | 'md' | 'lg'  // default 'md'
}

const maxWidthClasses = {
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
}: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        {/* Overlay */}
        <Dialog.Overlay
          className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40
                     data-[state=open]:animate-in data-[state=closed]:animate-out
                     data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0
                     motion-safe:transition-all"
        />
        {/* Content */}
        <Dialog.Content
          className={`fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2
                      w-full ${maxWidthClasses[maxWidth]} z-50
                      bg-white rounded-2xl shadow-xl p-6
                      data-[state=open]:animate-in data-[state=closed]:animate-out
                      data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0
                      data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95
                      motion-safe:transition-all
                      focus:outline-none`}
        >
          {/* Close button */}
          <Dialog.Close
            className="absolute right-4 top-4 rounded-full p-1
                       text-gray-400 hover:text-gray-600
                       focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1"
            aria-label="Close"
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </Dialog.Close>

          {/* Title */}
          <Dialog.Title className="font-fraunces text-xl text-brand-ink font-bold mb-1 pr-8">
            {title}
          </Dialog.Title>

          {/* Optional description */}
          {description && (
            <Dialog.Description className="text-sm text-gray-500 mb-4">
              {description}
            </Dialog.Description>
          )}

          {/* Modal body */}
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
```

**Note for KaihleAdmin:** Kaihle Admin uses Inter only. The `Dialog.Title` above uses
`font-fraunces`. When using `Modal` in `apps/kaihle-admin`, override the title class:

```tsx
// In kaihle-admin usage — pass a custom title via children instead of title prop,
// or add a role prop to Modal that switches the heading font class.
// The pattern is: Modal accepts a titleClassName prop defaulting to 'font-fraunces'
// KaihleAdmin passes titleClassName='font-inter font-bold'
```

### Usage pattern in task files

All task files that create modals must reference this pattern. Example:

```tsx
// ✅ Correct — uses Modal from packages/ui
import { Modal } from '@kaihle/ui'

function AdminExtendTrialModal({ open, onClose, school }) {
  return (
    <Modal
      open={open}
      onOpenChange={onClose}
      title={`Extend trial — ${school.name}`}
      description="Extension is applied immediately and logged in the audit trail."
    >
      {/* modal body */}
    </Modal>
  )
}

// ❌ Wrong — custom div with onClick handler, no focus trap
function BadModal({ onClose }) {
  return (
    <div onClick={onClose} className="fixed inset-0 ...">
      <div>...content...</div>
    </div>
  )
}
```

### Keyboard behaviour (guaranteed by Radix Dialog)

| Key | Behaviour |
|---|---|
| Tab | Cycles forward through focusable elements inside the modal only |
| Shift+Tab | Cycles backward |
| Escape | Closes the modal, restores focus to the trigger element |
| Enter | Activates the focused button/control inside the modal |
| Click outside | Closes the modal (configurable via `onPointerDownOutside`) |

### Export from packages/ui

Add to `packages/ui/src/index.ts`:
```typescript
export { Modal } from './components/Modal'
```

---

## §10 Addition — Loading State Standards

The platform must use a consistent loading pattern. The current state: some task files
say "show skeleton," some say "show spinner," some say nothing. This leads to
inconsistency that degrades the perceived quality of the product.

### The Rule

| Situation | Pattern | Component |
|---|---|---|
| **Page initial load** (data not yet fetched) | Skeleton — never spinner | `<SkeletonCard />` from `@kaihle/ui` |
| **Inline form action** (< 2s, button click) | Button spinner | `<Button loading={true} />` from `@kaihle/ui` |
| **Background generation** (> 2s, LLM task) | Pulsing status badge | `<Badge variant="warning" pulse={true}>Generating...</Badge>` |
| **Full page reload** (navigation) | Browser native | No component — rely on browser |
| **Table row action** (delete, archive) | Row-level skeleton replacement | `<Skeleton />` replacing the row |
| **Modal submit** | Button spinner inside modal | Same as inline form action |

### Never use a spinner for initial page data load

The spinner pattern (`className="animate-spin"` centered on the page) signals to users
"something is loading but I don't know what." The skeleton pattern shows the structure
of the page that is loading — users understand what is about to appear. This reduces
perceived load time and prevents layout shift when data arrives.

The **only** acceptable full-page spinner is in the `AuthLayout` while verifying a magic
link token — that is a special case where we don't know where to navigate yet.

### Loading state checklists for PR reviewers

Every frontend PR that adds a data-fetching component should be reviewed with this checklist:

```
□ Does the component show a skeleton (not spinner) while useQuery is loading?
□ Does the component handle the `isError` state gracefully (not just blank)?
□ Does the component handle empty data gracefully (empty state, not blank)?
□ Do buttons with async actions use loading={true} while awaiting?
□ Does background generation use a pulsing badge, not a spinner?
```

### Empty state standard

Every list or data component must have an explicit empty state. The `EmptyState`
component from `@kaihle/ui` is the standard:

```tsx
<EmptyState
  emoji="📋"
  title="No assessments yet"
  description="Create your first assessment to see results here."
  cta={<Button onClick={...}>Create assessment</Button>}
/>
```

Never show a blank area for an empty list. Always explain WHY it's empty and WHAT to do.

---

## CONSTITUTION.md — Rule 21 (to be added in same commit)

Add the following as Rule 21 in CONSTITUTION.md §4 Absolute Rules, after Rule 20:

```markdown
**Rule 21 — All modals must trap focus.** Any component that opens as a modal overlay
MUST use the `Modal` component from `packages/ui` (which wraps Radix UI Dialog). This
guarantees: (a) Tab key cycles within the modal only, (b) Shift+Tab cycles backward,
(c) Escape closes the modal, (d) focus returns to the triggering element on close.
Custom modal implementations without focus trapping are WCAG 2.1 Level AA violations.
No modal may be merged without keyboard navigation verification: open modal → Tab cycles
inside → Escape closes → focus returns to trigger. This applies to all five apps.

**Rule 22 — Loading states must follow the loading state standard.** See
`docs/design/DESIGN_SYSTEM_ACCESSIBILITY_ADDENDUM.md` §10. Page initial loads use
skeletons, button actions use button spinners, background generation uses pulsing
badges. No spinner on full-page initial data load. Every list component must have
an explicit empty state using `EmptyState` from `packages/ui`.
```

---

## Files affected by this addendum

When implementing modals and loading states, reference this document. The following
task files need to be updated to reference `Modal` from `@kaihle/ui` instead of
custom div-based implementations:

| Task | Modal component | Update needed |
|---|---|---|
| `M0-7-T5d` (Kaihle Admin config/users) | `DeactivateUserModal` | Use `<Modal>` |
| `M0-7-T5b` (Kaihle Admin billing) | None (no modals) | — |
| `M0-7-T4` (School Admin UI) | `InviteUserModal`, `CreateClassModal` | Use `<Modal>` |
| `M0-7-T5` (Kaihle Admin UI) | `AdminCreateSchoolModal`, `AdminExtendTrialModal` | Use `<Modal>` |
| `M3-2-T4` (Teacher assignment UI) | `AssignStudyPlanModal` | Use `<Modal>` |

All future task files that introduce a modal must include:
```
Depends on: M0-8-T6 (Modal component from packages/ui must exist)
```

---

## Packages to add

```bash
pnpm --filter @kaihle/ui add @radix-ui/react-dialog
```

This is the only new package. All other changes are CSS/component additions with no
new dependencies.

---

*Design System Accessibility Addendum v2.1 · Pixel (UX/UI Lead) · March 2026*
*Apply CONSTITUTION.md Rule 21 + Rule 22 in the same commit that adds this file.*
