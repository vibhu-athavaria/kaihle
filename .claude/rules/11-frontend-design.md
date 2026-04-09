# Frontend Design and Accessibility Rules

These rules summarise the non-negotiable parts of:

- docs/design/DESIGN_SYSTEM.md
- docs/design/DESIGN_SYSTEM_ACCESSIBILITY_ADDENDUM.md

Before writing or modifying any React/TypeScript frontend code, read those two files end-to-end.

## Core design principles

- "White sidebars. Colored data. Not colored chrome." Brand lives in mastery/status data and action elements, not in background fills or sidebar blocks.
- Five distinct apps, one per role: Student, Teacher, School Admin, Parent, Kaihle Admin. Each has its own layout and visual spec. Do not mix role-specific pages across apps.

## Mastery visualisation

- Never hand-pick emerald/amber/red Tailwind classes for mastery states.
- Always use `getMasteryStyle(score)` from `@kaihle/types` to derive dot, text, and background classes.

## Components and UI kit

- Use shared components from `@kaihle/ui` for Button, Card, Badge, Modal, Skeleton, EmptyState, etc.
- Do not introduce additional UI kits (MUI, Chakra, shadcn, Bootstrap, Flowbite, DaisyUI, etc.) without an ADR and Constitution update.

## Accessibility: modals, loading, empty states

- All modals must use the `Modal` component from `@kaihle/ui` (Radix Dialog wrapper). Custom div-based modals are prohibited.
- Keyboard focus must be trapped inside modals; Escape must close them; focus must return to the trigger on close.
- Page-level loading uses skeletons, not giant spinners. Button actions use button spinners. Background generation uses pulsing badges.
- Every list or collection must have a clear Empty State using the standard `EmptyState` component.

Any frontend implementation that violates these rules is a bug, not a style preference.
