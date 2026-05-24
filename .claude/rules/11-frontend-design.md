# Frontend Design and Accessibility Rules

Before creating any UI component, read the actual source files being referenced — never build from a subagent summary. Summaries lose exact class names, dimensions, and structure.

Before writing or modifying any frontend code, read the project's design system documentation end-to-end. Check CONSTITUTION for the canonical paths.

## Core principles

- Each user role has its own app and its own visual spec. Never mix role-specific pages across apps.
- Brand lives in data and action elements — not in sidebar backgrounds or chrome fills.

## Mastery visualisation

- Never hand-pick color classes for mastery states inline. Always use the project's mastery helper function to derive dot, text, and background classes from a score.

## Components and UI kit

- Use the project's shared component library for common elements (Button, Card, Badge, Modal, Skeleton, EmptyState). Do not define your own versions inside an app.
- Do not introduce additional UI kits without an ADR and CONSTITUTION update.

## Accessibility: modals, loading, empty states

- All modals must use the shared Modal component (Radix Dialog wrapper). Custom div-based modals are prohibited — they violate WCAG 2.1 focus trap requirements.
- Keyboard focus must be trapped inside modals; Escape must close them; focus must return to the trigger on close.
- Page-level loading uses skeletons, not spinners. Button actions use button spinners. Background generation (LLM, > 2s) uses pulsing badges.
- Every list or collection must have an explicit empty state. Never a blank area.

Any frontend implementation that violates these rules is a bug, not a style preference.
