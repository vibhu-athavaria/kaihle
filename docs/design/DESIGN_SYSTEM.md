# Kaihle Design System
**Version:** 2.2 · March 2026
**Authority:** Single source of truth for all frontend visual decisions.
**Load alongside CONSTITUTION.md for every frontend task. Do not invent colors, fonts, or layout patterns.**

---

## 1. Core Rules

- All hex values live **only** in `packages/ui/tailwind.config.js`. Components use token names only.
- Never use raw `gray-*`, `emerald-*`, or `indigo-*` for brand or mastery colors.
- Never use px for font sizes — always rem via Tailwind text scale.
- No `@apply` in component files — utility classes in JSX only.
- No per-page layout shells — use shared wrappers from `packages/ui/src/layouts/`.

---

## 2. Shared Brand Palette

| Token | Usage |
|---|---|
| `brand-primary` | Forest Green — mastery Strong, Student/School-Admin actions |
| `brand-gold` | Gold — Teacher primary action, Parent CTAs |
| `brand-red` | Mastery Needs Work |
| `brand-amber` | Mastery Developing |
| `brand-green` | Mastery Strong dot/bar |
| `brand-ink` | Primary text |
| `brand-body` | Secondary body text |
| `brand-muted` | Placeholder, disabled |
| `brand-border` | Default border |

Role-specific tokens (`role-admin-*`, `role-school-*`, `role-teacher-*`, `role-student-*`, `role-parent-*`) are in `tailwind.config.js` — open it when implementing a role-specific component.

> Full hex values for all role tokens: `brv query "Kaihle design system role-specific specs"`

### Mastery Colour Bands

Thresholds: > 0.7 = Strong · 0.4–0.7 = Developing · < 0.4 = Needs Work · null = Not assessed.
Boundary: `score = 0.7` → Developing. `score = 0.71` → Strong.

**TypeScript helper — never inline mastery colour logic:**

```typescript
// packages/types/src/mastery.ts
export function getMasteryStyle(score: number | null): MasteryStyle {
  if (score === null) return { label: 'Not assessed', dotClass: 'bg-brand-muted', textClass: 'text-brand-muted', bgClass: 'bg-gray-50' }
  if (score > 0.7)   return { label: 'Strong',       dotClass: 'bg-brand-green', textClass: 'text-brand-green', bgClass: 'bg-brand-green-light' }
  if (score >= 0.4)  return { label: 'Developing',   dotClass: 'bg-brand-amber', textClass: 'text-brand-amber', bgClass: 'bg-brand-amber-light' }
  return                    { label: 'Needs Work',   dotClass: 'bg-brand-red',   textClass: 'text-brand-red',   bgClass: 'bg-brand-red-light'   }
}
```

---

## 3. Typography

| Token | Family | Roles |
|---|---|---|
| `font-sans` | Nunito | ALL roles — body, labels, buttons, nav |
| `font-display` | Fraunces | School Admin, Teacher, Student — headings only |
| `font-['Lora']` | Lora | Parent ONLY — narrative text, headings, sidebar logo |
| `font-['Inter']` | Inter | Kaihle Admin ONLY — all text, no serifs |

**Google Fonts — add to every app's `src/index.css` above Tailwind directives:**

```css
@import url('https://fonts.googleapis.com/css2?family=Nunito:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&family=Fraunces:ital,opsz,wght@0,9..144,600;0,9..144,700;1,9..144,400;1,9..144,600&family=Inter:wght@400;500;600;700&family=Lora:ital,wght@0,600;1,400&display=swap');
@tailwind base;
@tailwind components;
@tailwind utilities;
```

> Type scale (rem values): `brv query "Kaihle design system type scale spacing subject colors"`

---

## 4. Shared Component Patterns

Lives in `packages/ui/src/components/`. No app defines its own version.

### Mastery Dot
```tsx
const { dotClass, label } = getMasteryStyle(score)
<span className={`w-5 h-5 rounded-full flex-shrink-0 ${dotClass}`} aria-label={label} role="img" />
```

### Progress Bar
```tsx
<div className="w-full bg-brand-border-soft rounded-full h-2">
  <div className="bg-brand-primary h-2 rounded-full transition-all duration-500"
    style={{ width: `${pct}%` }} role="progressbar"
    aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} />
</div>
```

### Loading Skeleton
```tsx
<div className="animate-pulse space-y-3">
  <div className="h-4 bg-brand-border rounded-full w-3/4" />
  <div className="h-4 bg-brand-border rounded-full w-1/2" />
</div>
```

### Empty State
```tsx
<div className="text-center py-16 px-6">
  <div className="text-4xl mb-4">{emoji}</div>
  <h3 className="font-display font-bold text-xl text-brand-ink mb-2">{title}</h3>
  <p className="text-brand-body text-sm max-w-sm mx-auto">{description}</p>
  {cta && <div className="mt-6">{cta}</div>}
</div>
```

### Icons
Lucide React only. Sizes: `w-5 h-5` default, `w-4 h-4` in buttons, `w-6 h-6` in KPI cards. Always `aria-hidden="true"` on decorative icons. Never icon-only interactive elements without a label.

---

## 5. Role-Specific Design Specs

> Full specs with hex tables, button styles, typography per role:
> `brv query "Kaihle design system role-specific specs"`

**Key rules per role (never violate):**

| Role | Layout | Action color | Font rule | Sidebar active |
|---|---|---|---|---|
| Kaihle Admin | `AdminLayout` | `brand-primary` green | Inter ONLY — no Fraunces/Lora | Gray fill + green dot |
| School Admin | `DashboardLayout variant="school-admin"` | `brand-primary` green | Fraunces headings | Left green stripe |
| Teacher | `DashboardLayout variant="teacher"` | `brand-gold` — NEVER green | Fraunces headings | Gold tint fill |
| Student | `StudentLayout` | `brand-primary` green | Fraunces headings | Green tint + green dot |
| Parent | `ParentLayout` | `brand-gold` | Lora headings/narrative | Cream tint + gold dot |

---

## 6. Layout Architecture

All five roles use a left sidebar (v2.1).

| Role | Layout | Sidebar border | Page bg |
|---|---|---|---|
| Kaihle Admin | `AdminLayout` | `#eaecf0` | `#f8f9fb` |
| School Admin | `DashboardLayout variant="school-admin"` | `#d4e4d8` | `#f5f7f1` |
| Teacher | `DashboardLayout variant="teacher"` | `#e5e7eb` | `#f5f7f1` |
| Student | `StudentLayout` | `#e5e7eb` | `#f9fafb` |
| Parent | `ParentLayout` | `#e8dcc8` | `#fdf8f0` |

### Sidebar Dimensions (all roles)
```
Width:         w-[200px]
Logo row:      h-[50px] border-b
Nav item:      px-3 py-[7px] mx-[6px] rounded-[6px] text-[12px] gap-2
Section label: px-3.5 pt-4 pb-1 text-[9px] font-bold uppercase tracking-[0.8px]
Profile card:  mt-auto border-t px-3.5 py-3
```

---

## 9. Accessibility & Modal Pattern

### Non-negotiable rules (all roles)
1. Mastery color indicators MUST have `aria-label` — color is never the only signal.
2. All interactive elements MUST have focus ring: `focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2`
3. All form inputs MUST have a visible `<label>` or `aria-label`.
4. Touch targets: `min-h-[44px] min-w-[44px]`
5. Contrast: `brand-gold` text on white fails (3.1:1) — use `brand-gold-dark` on gold backgrounds.

### Modal Focus Trap (CONSTITUTION Rule 21)

All modals MUST use `Modal` from `packages/ui` (wraps Radix UI `@radix-ui/react-dialog`). Never use a custom div-based modal.

```tsx
import { Modal } from '@kaihle/ui'
<Modal open={open} onOpenChange={setOpen} title="Confirm action">
  {/* body */}
</Modal>
```

Radix Dialog guarantees: Tab cycles within modal only · Escape closes · focus returns to trigger.

**KaihleAdmin note:** Pass `titleClassName="font-['Inter'] font-bold"` — Modal default uses `font-display`.

---

## 10. Loading State Standard (CONSTITUTION Rule 22)

| Situation | Pattern | Do NOT use |
|---|---|---|
| Page initial load | Skeleton (`animate-pulse`) | Spinner |
| Button action (< 2s) | Button spinner `loading={true}` | Full-page overlay |
| Background generation (LLM, > 2s) | Pulsing badge `Generating...` | Spinner |
| Table row action | Row-level skeleton | Page reload |

The only acceptable full-page spinner: `AuthLayout` during magic-link token verification.
Every list component MUST have an empty state — never a blank area.

---

## 11. Hard Rules

- ❌ No washed-out or gray data visuals — use tinted brand colors (`bg-brand-gold/30`, `bg-brand-primary/20`). `bg-gray-100`/`bg-gray-200` for track backgrounds only, never data fill.
- ❌ No colored sidebar backgrounds — all sidebars are `bg-white`
- ❌ No `indigo-*`, `emerald-*` for brand or mastery colors
- ❌ No green buttons in Teacher role — gold only for Teacher actions
- ❌ No Fraunces or Lora in Kaihle Admin — Inter only
- ❌ No Lora in any role except Parent
- ❌ No font-size in px — always rem via Tailwind
- ❌ No `!important`
- ❌ No `@apply` in component files
- ❌ No additional UI kits (MUI, Chakra, shadcn) — see CONSTITUTION Rule 14
- ❌ No lock icon on locked class items in Student sidebar — arrow icon only

---

## 12. File Map

| Need | Location |
|---|---|
| Tailwind tokens | `frontend/packages/ui/tailwind.config.js` |
| Google Fonts import | Each app's `src/index.css` |
| Layout wrappers | `frontend/packages/ui/src/layouts/` |
| Shared components | `frontend/packages/ui/src/components/` |
| Mastery helper | `frontend/packages/types/src/mastery.ts` |
| Screen specs per role | `docs/design/screens/` |
| Full role-specific hex + button specs | `brv query "Kaihle design system role-specific specs"` |
| Spacing, subject colors, type scale | `brv query "Kaihle design system type scale spacing subject colors"` |
