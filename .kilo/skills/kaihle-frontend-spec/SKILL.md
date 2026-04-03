---
name: kaihle-frontend-spec
description: Use when implementing a Kaihle frontend component or page. Provides the implementation checklist, token reference, component patterns, and common mistakes. Trigger on any frontend task in apps/ or packages/. Especially important for first-time implementation of a role-specific component.
---

# Kaihle Frontend Implementation Guide

## Pre-Implementation Checklist

Before writing a single line of JSX or Tailwind:

```
□ Identified which role this serves (teacher / student / school-admin / kaihle-admin / parent)
□ Read DESIGN_SYSTEM.md §5 for that role's specific spec
□ Checked mockup HTML in docs/design/mockups/ — it overrules DESIGN_SYSTEM.md on pixel values
□ Confirmed which app/ directory this file goes in
□ Confirmed shared components go in packages/ui/src/components/ not in apps/
□ Confirmed layout wrapper exists in packages/ui/src/layouts/
```

---

## Token Reference (Quick Lookup)

### Mastery Colors — ALWAYS use these, never raw hex or emerald-*/red-*

```tsx
import { getMasteryStyle } from '@kaihle/types'

const { label, dotClass, textClass, bgClass } = getMasteryStyle(score)
// score > 0.7  → Strong   | bg-brand-green  | text-brand-green  | bg-brand-green-light
// score 0.4-0.7→ Developing| bg-brand-amber  | text-brand-amber  | bg-brand-amber-light
// score < 0.4  → Needs Work| bg-brand-red    | text-brand-red    | bg-brand-red-light
// null         → Not assessed| bg-brand-muted | text-brand-muted  | bg-gray-50
```

### Role-Specific Button Patterns

```tsx
// Teacher — GOLD primary (never green)
<button className="bg-brand-gold text-white hover:bg-brand-gold-dark rounded-full px-4 py-2 min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2">
  Action
</button>

// All other roles — GREEN primary
<button className="bg-brand-primary text-white hover:bg-brand-dark rounded-full px-4 py-2 min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2">
  Action
</button>
```

### Active Nav State by Role

```
Kaihle Admin: bg-gray-100 text-role-admin-ink + dot: w-1.5 h-1.5 bg-brand-primary
School Admin: border-l-[3px] border-brand-primary bg-brand-light text-brand-primary rounded-r-lg
Teacher:      bg-[#fffbeb] text-brand-gold-dark font-bold
Student:      bg-[#f0fdf4] text-brand-primary font-semibold + dot: w-[6px] h-[6px] bg-brand-primary
Parent:       bg-[#fdf8f0] text-role-parent-ink font-semibold + dot: w-[6px] h-[6px] bg-brand-gold
```

### Sidebar Dimensions (ALL roles — consistent)

```
Width:         w-[200px]
Logo row:      h-[50px] border-b (matches top nav height)
Nav item:      px-3 py-[7px] mx-[6px] rounded-[6px] text-[12px]
Section label: px-3.5 pt-4 pb-1 text-[9px] font-bold uppercase tracking-[0.8px]
```

---

## Shared Component Patterns

### Modal (Rule 21 — mandatory)
```tsx
import { Modal } from '@kaihle/ui'

<Modal
  open={isOpen}
  onOpenChange={setIsOpen}
  title="Modal Title"
  description="Optional description"
  maxWidth="md"  // sm | md | lg
>
  {/* modal body */}
</Modal>
```
Never use a custom div-based modal. Always use the Radix UI wrapper from packages/ui.

### Loading States (Rule 22)
```tsx
// Page initial load — skeleton, NOT spinner
<div className="animate-pulse space-y-3">
  <div className="h-4 bg-brand-border rounded-full w-3/4" />
</div>

// Button action — spinner inside button
<Button loading={isPending}>Save changes</Button>

// Background LLM generation — pulsing badge
<Badge variant="warning" pulse>Generating...</Badge>
```

### Empty State
```tsx
import { EmptyState } from '@kaihle/ui'

<EmptyState
  emoji="📋"
  title="No assessments yet"
  description="Create your first assessment to see results here."
  cta={<Button onClick={handleCreate}>Create assessment</Button>}
/>
```
Never show a blank area. Always explain why it's empty and what to do.

### Mastery Dot
```tsx
const { dotClass, label } = getMasteryStyle(score)
<span
  className={`w-5 h-5 rounded-full flex-shrink-0 ${dotClass}`}
  aria-label={label}
  role="img"
/>
```
Always pair color with aria-label — color is never the only indicator.

---

## Font Rules

```
font-sans      Nunito — body text, labels, buttons, nav (ALL roles)
font-display   Fraunces — headings only (School Admin, Teacher, Student)
font-['Lora']  Lora — Parent ONLY (ALL text incl. headings)
font-['Inter'] Inter — Kaihle Admin ONLY (ALL text, no serifs)
```

Font sizes: always rem via Tailwind scale (`text-xs`, `text-sm`, etc.) — never px.

---

## Accessibility Checklist (Required for Every Component)

```
□ All form inputs have visible <label> or aria-label
□ All color-only indicators have aria-label
□ All interactive elements have min-h-[44px] (touch target)
□ All interactive elements have focus-visible:ring-2 focus ring
□ Modals use Modal from packages/ui (focus trap guaranteed)
□ All decorative icons have aria-hidden="true"
□ No icon-only interactive elements (always pair with text or aria-label)
□ Progress bars have role="progressbar" aria-valuenow aria-valuemin aria-valuemax
```

---

## Common Mistakes That Silently Break the Design

| Wrong | Right |
|---|---|
| `bg-emerald-500` for mastery Strong | `bg-brand-green` |
| Green button in Teacher app | `bg-brand-gold` (gold) |
| `className="text-[9px]"` without registering token | Register in tailwind.config.js first |
| Color hex in component file | Use token name only |
| Custom modal div | `<Modal>` from `@kaihle/ui` |
| `getMasteryStyle` inline | Import from `@kaihle/types` |
| `apps/teacher/src/pages/admin/...` for School Admin | `apps/school-admin/src/pages/...` |
| Spinner on page initial load | Skeleton |
| Empty list with no message | `<EmptyState>` |
| `@apply` in component files | Utility classes in JSX only |

---

## When to Invoke @pixel

- Mockup exists but task file doesn't specify pixel values → invoke @pixel
- Design token name is unclear → invoke @pixel
- Two interpretations of the layout are possible → invoke @pixel
- A component needs a state (hover, focus, active, disabled) not specified in task → invoke @pixel
