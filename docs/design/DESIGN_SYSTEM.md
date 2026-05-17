# Kaihle Design System
**Version:** 2.2 · March 2026 — merges DESIGN_SYSTEM.md v2.1 + DESIGN_SYSTEM_ACCESSIBILITY_ADDENDUM.md v2.1
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

All hex values live **only** in `frontend/packages/ui/tailwind.config.js`. Use token names in components — never raw hex. When you need a hex value, open `tailwind.config.js` directly.

**Most-used tokens (quick reference):**

| Token | Usage |
|---|---|
| `brand-primary` | Forest Green — mastery Strong, Student/School-Admin actions |
| `brand-gold` | Gold — Developing mastery, Teacher primary action |
| `brand-red` | Mastery Needs Work |
| `brand-amber` | Mastery Developing |
| `brand-green` | Mastery Strong dot/bar |
| `brand-ink` | Primary text |
| `brand-body` | Secondary body text |
| `brand-muted` | Placeholder, disabled |
| `brand-border` | Default border |
| `brand-bg` | Page background (Teacher, School Admin) |

Role-specific tokens (`role-admin-*`, `role-school-*`, `role-teacher-*`, `role-student-*`, `role-parent-*`) are in `tailwind.config.js` — load that file when implementing a role-specific component.

### Mastery Colour Bands

Thresholds: > 0.7 = Strong · 0.4–0.7 = Developing · < 0.4 = Needs Work · null = Not assessed.
Boundary: `score = 0.7` → Developing. `score = 0.71` → Strong. See `CONSTITUTION.md §12` for the full table.

**TypeScript helper — never inline mastery colour logic, always use this:**
**`packages/types/src/mastery.ts`:**

```typescript
export type MasteryLabel = 'Strong' | 'Developing' | 'Needs Work' | 'Not assessed'
export interface MasteryStyle { label: MasteryLabel; dotClass: string; textClass: string; bgClass: string }
export function getMasteryStyle(score: number | null): MasteryStyle {
  if (score === null) return { label: 'Not assessed', dotClass: 'bg-brand-muted', textClass: 'text-brand-muted', bgClass: 'bg-gray-50' }
  if (score > 0.7)   return { label: 'Strong',       dotClass: 'bg-brand-green', textClass: 'text-brand-green', bgClass: 'bg-brand-green-light' }
  if (score >= 0.4)  return { label: 'Developing',   dotClass: 'bg-brand-amber', textClass: 'text-brand-amber', bgClass: 'bg-brand-amber-light' }
  return                    { label: 'Needs Work',   dotClass: 'bg-brand-red',   textClass: 'text-brand-red',   bgClass: 'bg-brand-red-light'   }
}
```

---

## 3. Typography

### Font Families

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

### Type Scale

| Token | rem | Use |
|---|---|---|
| `text-xs` | 0.75 | Section labels, captions |
| `text-sm` | 0.875 | Secondary labels, metadata, nav items |
| `text-base` | 1.0 | Body, form labels |
| `text-lg` | 1.125 | Card titles |
| `text-xl` | 1.25 | Sub-headings |
| `text-2xl` | 1.5 | Page titles (+ font-display) |
| `text-3xl` | 1.875 | Large headings |

---

## 4. Shared Component Patterns

Lives in `packages/ui/src/components/`. No app defines its own version.

### Mastery Dot (always pair color with aria-label)
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

---

### 5.1 Kaihle Admin — Surgical Slate

**Layout:** `AdminLayout` · **Fonts:** Inter throughout — NO Fraunces, NO Lora.

| Token | Hex | Usage |
|---|---|---|
| `role-admin-bg` | `#f8f9fb` | Page background |
| `role-admin-sidebar` | `#ffffff` | Sidebar |
| `role-admin-border` | `#eaecf0` | All borders |
| `role-admin-mark` | `#374151` | Logo mark background |
| `role-admin-ink` | `#111827` | Primary text |
| `role-admin-muted` | `#9ca3af` | Section labels |
| `role-admin-subtle` | `#6b7280` | Inactive nav items |

**Sidebar:** `bg-white border-r border-role-admin-border`
Active: `bg-gray-100 text-role-admin-ink` + green dot `w-1.5 h-1.5 rounded-full bg-brand-primary`

**Typography:**
| Element | Class |
|---|---|
| Page titles | `font-['Inter'] text-sm font-bold text-role-admin-ink` |
| Section labels | `font-['Inter'] text-xs font-bold uppercase tracking-widest text-role-admin-muted` |
| Body / nav | `font-['Inter'] text-sm text-role-admin-subtle` |
| KPI values | `font-['Inter'] text-2xl font-bold` |

**Buttons:** Primary `bg-brand-primary text-white rounded-full` · Danger `bg-red-600 text-white rounded-full` · Secondary `bg-gray-100 text-role-admin-ink rounded-full`

---

### 5.2 School Admin — Sage Authority

**Layout:** `DashboardLayout variant="school-admin"` · **Fonts:** Fraunces headings, Nunito body.

| Token | Hex | Usage |
|---|---|---|
| `role-school-bg` | `#f5f7f1` | Page background |
| `role-school-border` | `#d4e4d8` | All borders — green tinted |
| `role-school-muted` | `#6b9e79` | Section labels |

**Sidebar:** `bg-white border-r border-role-school-border`
Active: `border-l-[3px] border-brand-primary bg-brand-light text-brand-primary rounded-r-lg rounded-l-none font-semibold` — **left stripe is the defining visual**

**Buttons:** Primary `bg-brand-primary text-white rounded-full` · Secondary `border border-role-school-border text-brand-primary rounded-full`

---

### 5.3 Teacher — Warm Professional

**Layout:** `DashboardLayout variant="teacher"` · **Fonts:** Fraunces headings, Nunito body.
**⚠️ Gold is the action color. Green = mastery data ONLY. Never green buttons.**

| Token | Hex | Usage |
|---|---|---|
| `role-teacher-bg` | `#f5f7f1` | Page background |
| `role-teacher-border` | `#e5e7eb` | All borders |
| `role-teacher-muted` | `#a0a8a0` | Section labels |
| `brand-gold` | `#c9932a` | ALL teacher action buttons, active nav |
| `brand-gold-light` | `#fffbeb` | Active nav tint |

**Sidebar:** `bg-white border-r border-role-teacher-border`
Active: `bg-[#fffbeb] text-brand-gold-dark font-bold` — **gold tint fill is the defining visual**
Pending action indicator: amber dot `w-2 h-2 rounded-full bg-brand-gold ml-auto`

**Buttons:**
```
Primary action: bg-brand-gold text-white hover:bg-brand-gold-dark rounded-full
Publish:        bg-brand-primary text-white rounded-full  (publish = success — green is correct here)
Secondary:      border border-role-teacher-border text-brand-ink rounded-full
Danger:         border border-red-300 text-red-600 hover:bg-red-50 rounded-full
```

---

### 5.4 Student — Airy & Encouraging

**Layout:** `StudentLayout` · **Fonts:** Fraunces headings, Nunito body. Green action color.
**v2.1: Student uses a sidebar. Previous top-nav-tabs + bottom-nav spec is superseded.**

| Token | Hex | Usage |
|---|---|---|
| `role-student-bg` | `#f9fafb` | Page background — cool near-white |
| `role-student-border` | `#e5e7eb` | Card borders |
| `brand-primary` | `#1a5c38` | Action buttons, active nav |
| `brand-green-light` | `#f0fdf4` | Active nav tint |

**Sidebar:** `bg-white border-r border-role-student-border w-[200px]`
Active: `bg-[#f0fdf4] text-brand-primary font-semibold` + green dot `w-[6px] h-[6px] rounded-full bg-brand-primary`

**Navigation:**
```
Section LEARN:    Home → /student/dashboard
                  My progress → /student/my-progress
                  Study plans → /student/study-plans
                  Assessments → /student/assessments

Section CLASSES:  [Subject dot] Class name → /student/classes/:classId/topics  (unlocked)
                  [Arrow →]     Class name → /student/classes/:classId/diagnostic (locked — no lock icon)
```

Locked class items: no lock icon, no opacity reduction, no amber color. Arrow icon only. The CTA text is the affordance.

**Top nav:** `h-[50px] bg-white border-b` · Left: greeting + grade/curriculum · Right: avatar → settings

**Typography:**
| Element | Class |
|---|---|
| Page title | `font-display font-bold text-2xl text-brand-ink` |
| Subject labels | `font-sans font-bold text-xs uppercase tracking-wide` |
| Score values | `font-sans font-extrabold text-2xl` + mastery color |
| Body | `font-sans text-sm text-brand-body` |

**Buttons:** Primary `bg-brand-primary text-white rounded-full` · Celebrate (achievement only) `bg-brand-gold text-white rounded-full`

---

### 5.5 Parent — Warm & Readable

**Layout:** `ParentLayout` · **Fonts:** Lora narrative/headings, Nunito labels/buttons.
**v2.1: Parent uses a sidebar. Previous minimal-top-nav-only spec is superseded.**

| Token | Hex | Usage |
|---|---|---|
| `role-parent-bg` | `#fdf8f0` | Page background — warm cream |
| `role-parent-border` | `#e8dcc8` | Borders — warm sand |
| `role-parent-ink` | `#2c1a0e` | Primary text — espresso |
| `role-parent-muted` | `#a08060` | Secondary text |
| `brand-gold` | `#c9932a` | Active nav dot, CTAs |

**Sidebar:** `bg-white border-r border-role-parent-border w-[200px]`
Active: `bg-[#fdf8f0] text-role-parent-ink font-semibold` + gold dot `w-[6px] h-[6px] rounded-full bg-brand-gold`
Sidebar logo uses `font-['Lora']` — the only role with Lora in the sidebar.

**Typography:**
| Element | Class |
|---|---|
| Greeting / headings | `font-['Lora'] font-semibold text-xl text-role-parent-ink` |
| Narrative body | `font-['Lora'] text-sm leading-relaxed text-role-parent-ink` |
| Labels, meta | `font-sans text-xs font-bold text-role-parent-muted` |
| CTAs | `font-sans text-xs font-bold text-brand-gold hover:text-brand-gold-dark` |

**Narrative Card:**
```tsx
<div className="bg-white rounded-2xl border-[1.5px] border-role-parent-border p-5">
  <p className="font-['Lora'] text-sm leading-relaxed text-role-parent-ink">{narrative}</p>
  {highlights.map(h => <span className="bg-brand-green-light border border-brand-mid rounded-full text-xs px-3 py-1 font-sans font-semibold text-brand-green">{h}</span>)}
  <button className="font-sans text-xs font-bold text-brand-gold hover:text-brand-gold-dark">Read full report →</button>
</div>
```

---

## 6. Layout Architecture

All five roles use a left sidebar (v2.1).

| Role | Layout | Sidebar border | Page bg | Primary font |
|---|---|---|---|---|
| Kaihle Admin | `AdminLayout` | `#eaecf0` | `#f8f9fb` | Inter |
| School Admin | `DashboardLayout variant="school-admin"` | `#d4e4d8` | `#f5f7f1` | Fraunces + Nunito |
| Teacher | `DashboardLayout variant="teacher"` | `#e5e7eb` | `#f5f7f1` | Fraunces + Nunito |
| Student | `StudentLayout` | `#e5e7eb` | `#f9fafb` | Fraunces + Nunito |
| Parent | `ParentLayout` | `#e8dcc8` | `#fdf8f0` | Lora + Nunito |

### Sidebar Dimensions (all roles)
```
Width:         w-[200px]
Logo row:      h-[50px] border-b
Nav item:      px-3 py-[7px] mx-[6px] rounded-[6px] text-[12px] gap-2
Section label: px-3.5 pt-4 pb-1 text-[9px] font-bold uppercase tracking-[0.8px]
Profile card:  mt-auto border-t px-3.5 py-3
```

### Sidebar Active State by Role
| Role | Active pattern | Classes |
|---|---|---|
| Kaihle Admin | Gray fill + green dot | `bg-gray-100 text-role-admin-ink` + dot `bg-brand-primary` |
| School Admin | Left green stripe + tint | `border-l-[3px] border-brand-primary bg-brand-light text-brand-primary` |
| Teacher | Gold tint fill | `bg-[#fffbeb] text-brand-gold-dark font-bold` |
| Student | Green tint + green dot | `bg-[#f0fdf4] text-brand-primary font-semibold` + dot `bg-brand-primary` |
| Parent | Cream tint + gold dot | `bg-[#fdf8f0] text-role-parent-ink font-semibold` + dot `bg-brand-gold` |

---

## 7. Spacing & Responsive

| Context | Value |
|---|---|
| Page padding desktop | `p-6` |
| Page padding mobile | `p-4` |
| Card padding | `p-5` standard, `p-4` compact |
| Card gap | `gap-4` |
| Stacked sections | `space-y-6` |
| Form fields | `space-y-4` |

Sidebar collapses at `md:` (768px). Kaihle Admin: desktop only. Touch targets: `min-h-[44px] min-w-[44px]`.

---

## 8. Subject Colors

| Subject | Tailwind | Hex |
|---|---|---|
| Mathematics | `bg-brand-primary` | `#1a5c38` |
| Integrated Science | `bg-violet-600` | `#7c3aed` |
| Biology | `bg-green-600` | `#16a34a` |
| Chemistry | `bg-amber-600` | `#d97706` |
| Physics | `bg-blue-600` | `#2563eb` |
| English Language | `bg-red-600` | `#dc2626` |
| English Literature | `bg-purple-600` | `#9333ea` |

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

Install: `pnpm --filter @kaihle/ui add @radix-ui/react-dialog`

**KaihleAdmin note:** `Modal` title uses `font-display` by default. Pass `titleClassName="font-['Inter'] font-bold"` in kaihle-admin usage.

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

**PR checklist for loading states:**
```
□ Skeleton (not spinner) while useQuery is loading?
□ isError state handled gracefully?
□ Empty data state explicit (not blank)?
□ Buttons with async actions use loading={true}?
□ Background generation uses pulsing badge?
```

---

## 11. Hard Rules

- ❌ No washed-out or gray progress bars, chart fills, or data visuals — use tinted brand colors (`bg-brand-gold/30`, `bg-brand-primary/20`, etc.). `bg-gray-100` / `bg-gray-200` are permitted only for track backgrounds on skeletons and neutral UI chrome, never as data fill colors.
- ❌ No colored sidebar backgrounds — all sidebars are `bg-white`
- ❌ No `indigo-*`, `emerald-*` for brand or mastery colors
- ❌ No `emerald-500` for Strong mastery — use `brand-green`
- ❌ No green buttons in Teacher role — gold only for Teacher actions
- ❌ No Fraunces or Lora in Kaihle Admin — Inter only
- ❌ No Lora in any role except Parent
- ❌ No font-size in px — always rem via Tailwind
- ❌ No `!important`
- ❌ No per-page layout shells — use shared wrappers
- ❌ No `@apply` in component files
- ❌ No additional UI kits (MUI, Chakra, shadcn) — see CONSTITUTION Rule 14
- ❌ No lock icon on locked class items in Student sidebar — arrow icon only
- ❌ No opacity reduction on locked class cards in Student app

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
