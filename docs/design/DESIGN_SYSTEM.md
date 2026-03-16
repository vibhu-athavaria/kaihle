# Kaihle Design System
**Version:** 2.0 · March 2026
**Authority:** Single source of truth for all frontend visual decisions.
**Load this file alongside CONSTITUTION.md for every frontend task.**

> Every coding agent implementing a frontend task MUST read this entire file before writing
> any component or Tailwind class. Do not invent colors, fonts, or layout patterns.

---

## 1. Core Design Philosophy

**"White sidebars. Colored data. Not colored chrome."**

The Kaihle brand appears in data (mastery scores, status badges, charts) and action elements
(primary buttons, active nav states). It does NOT live in background fills or sidebar colors.
This keeps the UI clean while making student performance data the visual hero.

**Five distinct roles. One coherent brand.**
All five apps share: Forest Green `#1a5c38` for mastery/success, Gold `#c9932a` for developing/actions,
Red `#ef4444` for needs-work, and Nunito as the base body font. What varies per role is page temperature,
typographic warmth, sidebar chrome style, and layout density.

---

## 2. Shared Brand Palette

These tokens are common to ALL five roles and live in `packages/ui/tailwind.config.js`.

```
Token                   Hex         Usage
──────────────────────  ──────────  ────────────────────────────────────────────
brand-primary           #1a5c38     Forest Green — mastery Strong, success states
brand-dark              #0f3d25     Hover on brand-primary
brand-light             #e8f2ea     Green tint backgrounds
brand-mid               #b5d4bc     Green borders, subtle outlines
brand-green             #16a34a     Mastery Strong dot/bar color
brand-green-light       #dcfce7     Mastery Strong tint background
brand-gold              #c9932a     Gold — developing states, Teacher primary action
brand-gold-light        #f5ead0     Gold tint backgrounds  (also: #fffbeb for Teacher nav tint)
brand-gold-mid          #e8c97a     Gold borders
brand-gold-dark         #92400e     Text on gold tint backgrounds
brand-red               #ef4444     Mastery Needs Work
brand-red-light         #fee2e2     Needs Work tint background
brand-amber             #f59e0b     Mastery Developing
brand-amber-light       #fef3c7     Developing tint background
brand-ink               #1a2016     Primary text (Teacher, Student, School Admin)
brand-body              #4a5240     Secondary body text
brand-muted             #9ca3af     Placeholder, disabled text
brand-border            #e5e7eb     Default border (Teacher, Student)
brand-border-soft       #f3f4f6     Subtle separator
brand-bg                #f5f7f1     Page background (Teacher, School Admin)
```

### Mastery Score Colour Bands ⚠️ NEVER use generic emerald-*/amber-*/red-*

| Score | Label | Dot class | Text class | Tint bg |
|---|---|---|---|---|
| > 0.7 | Strong | `bg-brand-green` | `text-brand-green` | `bg-brand-green-light` |
| 0.4–0.7 | Developing | `bg-brand-amber` | `text-brand-amber` | `bg-brand-amber-light` |
| < 0.4 | Needs Work | `bg-brand-red` | `text-brand-red` | `bg-brand-red-light` |
| null | Not assessed | `bg-brand-muted` | `text-brand-muted` | `bg-gray-50` |

**TypeScript helper — add to `packages/types/src/mastery.ts`:**

```typescript
export type MasteryLabel = 'Strong' | 'Developing' | 'Needs Work' | 'Not assessed'
export interface MasteryStyle {
  label: MasteryLabel; dotClass: string; textClass: string; bgClass: string
}
export function getMasteryStyle(score: number | null): MasteryStyle {
  if (score === null) return { label: 'Not assessed', dotClass: 'bg-brand-muted', textClass: 'text-brand-muted', bgClass: 'bg-gray-50' }
  if (score > 0.7)   return { label: 'Strong',     dotClass: 'bg-brand-green', textClass: 'text-brand-green', bgClass: 'bg-brand-green-light' }
  if (score >= 0.4)  return { label: 'Developing', dotClass: 'bg-brand-amber', textClass: 'text-brand-amber', bgClass: 'bg-brand-amber-light' }
  return                    { label: 'Needs Work', dotClass: 'bg-brand-red',   textClass: 'text-brand-red',   bgClass: 'bg-brand-red-light'   }
}
```

---

## 3. Typography — Shared Rules

### Font Families

| Token | Family | Roles |
|---|---|---|
| `font-sans` | Nunito | ALL roles — body, labels, buttons, nav |
| `font-display` | Fraunces | School Admin, Teacher, Student (headings only) |
| `font-['Lora']` | Lora | Parent ONLY — narrative text and headings |
| `font-['Inter']` | Inter | Kaihle Admin ONLY — all text, no serifs |

**Google Fonts import — add to EVERY app's `src/index.css` above Tailwind directives:**

```css
@import url('https://fonts.googleapis.com/css2?family=Nunito:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,400&family=Fraunces:ital,opsz,wght@0,9..144,600;0,9..144,700;1,9..144,400;1,9..144,600&family=Inter:wght@400;500;600;700&family=Lora:ital,wght@0,600;1,400&display=swap');

@tailwind base;
@tailwind components;
@tailwind utilities;
```

### Type Scale (rem — never px for font sizes)

| Token | rem | Use |
|---|---|---|
| `text-xs` | 0.75rem | Section labels, captions |
| `text-sm` | 0.875rem | Secondary labels, metadata, nav items |
| `text-base` | 1rem | Body text, form labels |
| `text-lg` | 1.125rem | Card titles |
| `text-xl` | 1.25rem | Sub-headings |
| `text-2xl` | 1.5rem | Page titles (with font-display) |
| `text-3xl` | 1.875rem | Large headings |

---

## 4. Shared Component Patterns

These live in `packages/ui/src/components/` and are used across ALL roles.

### Mastery Dot (always pair color with aria-label)

```tsx
const { dotClass, label } = getMasteryStyle(score)
<span className={`w-5 h-5 rounded-full flex-shrink-0 ${dotClass}`}
  aria-label={label} role="img" />
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

Lucide React only. Sizes: `w-5 h-5` default, `w-4 h-4` in buttons, `w-6 h-6` in KPI cards.
Always `aria-hidden="true"` on decorative icons. Never icon-only interactive elements.

---

## 5. Role-Specific Design Specs

---

### 5.1 Kaihle Admin — Surgical Slate

**Feeling:** Internal ops tool. Surgical, data-dense, no decoration.
**Layout:** Left sidebar + top nav + content (`AdminLayout`).
**Primary font:** Inter throughout — NO Fraunces or Lora.

#### Palette

| Token | Hex | Usage |
|---|---|---|
| `role-admin-bg` | `#f8f9fb` | Page background — cool blue-gray |
| `role-admin-sidebar` | `#ffffff` | Sidebar |
| `role-admin-border` | `#eaecf0` | All borders |
| `role-admin-mark` | `#374151` | Logo mark background |
| `role-admin-ink` | `#111827` | Primary text |
| `role-admin-muted` | `#9ca3af` | Section labels, secondary |
| `role-admin-subtle` | `#6b7280` | Inactive nav items |
| `brand-primary` | `#1a5c38` | Action buttons, positive metrics |
| `brand-amber` | `#f59e0b` | Warning (trial schools) |

#### Typography (Inter — ALL text)

| Element | Class |
|---|---|
| Page titles | `font-['Inter'] text-sm font-bold text-role-admin-ink` |
| Section labels | `font-['Inter'] text-xs font-bold uppercase tracking-widest text-role-admin-muted` |
| Body / nav | `font-['Inter'] text-sm text-role-admin-subtle` |
| KPI values | `font-['Inter'] text-2xl font-bold` |

#### Sidebar spec

```
bg-white border-r border-role-admin-border
Logo mark: bg-role-admin-mark (gray-700) rounded-lg
Nav active: bg-gray-100 text-role-admin-ink + w-1.5 h-1.5 rounded-full bg-brand-primary dot
Nav hover:  bg-gray-50 text-role-admin-ink
Nav base:   text-role-admin-subtle
```

Active indicator: small **green dot** before the label. No background stripe.

#### Buttons

```
Primary:   bg-brand-primary text-white hover:bg-brand-dark rounded-full
Danger:    bg-red-600 text-white hover:bg-red-700 rounded-full
Secondary: bg-gray-100 text-role-admin-ink hover:bg-gray-200 rounded-full
```

---

### 5.2 School Admin — Sage Authority

**Feeling:** Strategic oversight. Trustworthy, brand-connected, professional.
**Layout:** Left sidebar + top nav + content (`DashboardLayout variant="school-admin"`).

#### Palette

| Token | Hex | Usage |
|---|---|---|
| `role-school-bg` | `#f5f7f1` | Page background — brand cream |
| `role-school-sidebar` | `#ffffff` | Sidebar |
| `role-school-border` | `#d4e4d8` | Borders — green-tinted |
| `role-school-muted` | `#6b9e79` | Section labels — muted green |
| `role-school-subtle` | `#4a5240` | Inactive nav items |
| `brand-primary` | `#1a5c38` | Active nav stripe, primary actions |
| `brand-light` | `#e8f2ea` | Active nav tint |
| `brand-gold` | `#c9932a` | Secondary actions, warnings |

#### Typography

| Element | Class |
|---|---|
| Page titles | `font-display font-bold text-2xl text-brand-ink` |
| Nav brand | `font-display font-bold text-sm text-brand-ink` |
| Section labels | `font-sans text-xs font-bold uppercase tracking-widest text-role-school-muted` |
| Body | `font-sans text-sm text-role-school-subtle` |

#### Sidebar spec

```
bg-white border-r border-role-school-border
Logo mark: bg-brand-primary italic Fraunces "K"
Nav active: border-l-[3px] border-brand-primary bg-brand-light text-brand-primary
            (left stripe + green tint — the "authority stripe" pattern)
            rounded-r-lg rounded-l-none
Nav hover:  bg-brand-light/50 text-brand-ink
Nav base:   text-role-school-subtle
```

Active indicator: **left border stripe** — `border-l-[3px] border-brand-primary`.

#### Buttons

```
Primary:   bg-brand-primary text-white hover:bg-brand-dark rounded-full
Secondary: bg-white text-brand-primary border border-brand-mid hover:bg-brand-light rounded-full
```

---

### 5.3 Teacher — Focused Workspace

**Feeling:** Clean workspace. Data speaks; chrome disappears.
**Layout:** Left sidebar + top nav + content (`DashboardLayout variant="teacher"`).

> **Key design rule:** Gold is the action color. Green is the data/success color.
> NEVER use green buttons in the Teacher role — green means mastery, gold means action.

#### Palette

| Token | Hex | Usage |
|---|---|---|
| `role-teacher-bg` | `#f5f7f1` | Page background |
| `role-teacher-sidebar` | `#ffffff` | Sidebar |
| `role-teacher-border` | `#e5e7eb` | Borders — neutral gray |
| `role-teacher-muted` | `#9ca3af` | Section labels, metadata |
| `role-teacher-body` | `#4a5240` | Inactive nav, secondary text |
| `brand-gold` | `#c9932a` | PRIMARY ACTION — buttons, active nav |
| `brand-gold-light` | `#fffbeb` | Active nav tint |
| `brand-gold-dark` | `#92400e` | Text on gold tint |
| `brand-primary` | `#1a5c38` | SUCCESS DATA ONLY — never for buttons |
| `brand-ink` | `#1a2016` | Primary text |

#### Typography

| Element | Class |
|---|---|
| Page titles | `font-display font-bold text-2xl text-brand-ink` |
| Nav brand | `font-display font-bold text-sm text-brand-ink` |
| Section labels | `font-sans text-xs font-bold uppercase tracking-widest text-role-teacher-muted` |
| Body | `font-sans text-sm text-role-teacher-body` |

#### Sidebar spec

```
bg-white border-r border-role-teacher-border
Logo mark: bg-brand-primary italic Fraunces "K"
Nav active: bg-brand-gold-light text-brand-gold-dark font-bold
            (gold tint fill — NO border stripe, distinct from School Admin)
Nav hover:  bg-gray-50 text-brand-ink
Nav base:   text-role-teacher-body
```

Active indicator: **gold tint background only** — no stripe. This is the visual distinction
from School Admin (stripe = authority, tint = workspace).

#### Buttons

```
Primary:   bg-brand-gold text-white hover:bg-amber-600 rounded-full
           (teacher taking action — gold = "you do something")
Secondary: bg-white text-brand-ink border border-role-teacher-border hover:bg-gray-50 rounded-full
Positive:  bg-brand-primary text-white hover:bg-brand-dark rounded-full
           (only when confirming success — "Publish", "Mark as used")
```

---

### 5.4 Student — Airy & Encouraging

**Feeling:** Lightweight learning companion. Mobile-first, encouraging, app-like.
**Layout:** TOP NAV ONLY — no sidebar. Bottom nav on mobile (`StudentLayout`).

#### Palette

| Token | Hex | Usage |
|---|---|---|
| `role-student-bg` | `#f9fafb` | Page background — cool near-white |
| `role-student-border` | `#e5e7eb` | Card borders, dividers |
| `brand-primary` | `#1a5c38` | Strong mastery, positive actions |
| `brand-light` | `#e8f2ea` | Strong mastery card borders/tints |
| `brand-mid` | `#b5d4bc` | Strong mastery card border (colored-border cards) |
| `brand-gold` | `#c9932a` | Developing mastery, achievement moments |
| `brand-gold-light` | `#f5ead0` | Developing card border tint |
| `brand-gold-mid` | `#e8c97a` | Developing card border |
| `brand-red` | `#ef4444` | Needs Work |
| `brand-red-light` | `#fee2e2` | Needs Work tint |
| `brand-ink` | `#1a2016` | Primary text |
| `brand-muted` | `#9ca3af` | Secondary labels |

> Why `#f9fafb` (slightly cool) rather than `#f5f7f1` (warm cream)?
> Students respond to cleaner, app-like surfaces. The cream belongs to the teacher
> professional workspace. Students are in Duolingo territory — crisp white-adjacent.

#### Typography

| Element | Class |
|---|---|
| Greeting / page title | `font-display font-bold text-2xl text-brand-ink` |
| Subject labels | `font-sans font-bold text-xs uppercase tracking-wide` |
| Score values | `font-sans font-extrabold text-2xl` + mastery color class |
| Body | `font-sans text-sm text-brand-body` |
| Card titles | `font-sans font-semibold text-base text-brand-ink` |

#### Subject Score Cards (colored-border pattern)

```tsx
// Derive border color from mastery:
// Strong:      border-brand-mid  (#b5d4bc)
// Developing:  border-brand-gold-mid (#e8c97a)
// Needs Work:  border-brand-red/30

<div className={`bg-white rounded-2xl border-[1.5px] ${borderClass} p-4 text-center`}>
  <div className={`text-2xl font-extrabold ${textClass}`}>{Math.round(score * 100)}%</div>
  <div className="text-xs font-bold uppercase tracking-wide text-brand-muted mt-1">{subject}</div>
  <div className="text-xs text-brand-muted mt-0.5">{label}</div>
</div>
```

#### Layout spec

```
Top nav:     h-14 bg-white border-b border-role-student-border
             Left: font-display "Kaihle" + subject tabs (active = brand-primary underline)
             Right: avatar
Content:     bg-role-student-bg p-4 md:p-6 pb-20 (bottom nav clearance on mobile)
Bottom nav:  md:hidden fixed bottom-0 w-full h-16 bg-white border-t border-role-student-border
             4 items: Home, Progress, Study Plans, Assessments
             Active: text-brand-primary (no background fill)
```

#### Buttons

```
Primary:   bg-brand-primary text-white hover:bg-brand-dark rounded-full
Celebrate: bg-brand-gold text-white rounded-full
           (achievement moments only — plan complete, high quiz score)
Secondary: bg-white text-brand-ink border border-role-student-border rounded-full
```

---

### 5.5 Parent — Warm & Readable

**Feeling:** Warm editorial. A letter from school, not a dashboard.
**Layout:** MINIMAL TOP NAV — no sidebar, no bottom nav (`ParentLayout`).
**Primary display font:** Lora (narrative text + headings). Nunito for labels/buttons.

#### Palette

| Token | Hex | Usage |
|---|---|---|
| `role-parent-bg` | `#fdf8f0` | Page background — warm cream |
| `role-parent-card` | `#ffffff` | Card surfaces |
| `role-parent-border` | `#e8dcc8` | Borders — warm sand |
| `role-parent-ink` | `#2c1a0e` | Primary text — espresso |
| `role-parent-muted` | `#a08060` | Secondary text — warm taupe |
| `brand-primary` | `#1a5c38` | Strong mastery dots |
| `brand-gold` | `#c9932a` | "Read more" CTAs, developing mastery |
| `brand-gold-dark` | `#92400e` | Hover on gold text links |
| `brand-red` | `#ef4444` | Needs Work mastery |

> Why espresso ink `#2c1a0e` rather than `brand-ink #1a2016`?
> On a warm cream background, espresso reads warmer and avoids the color temperature
> clash that standard cool-dark ink would create.

#### Typography

| Element | Class |
|---|---|
| Greeting / headings | `font-['Lora'] font-semibold text-xl text-role-parent-ink` |
| Narrative body | `font-['Lora'] text-sm leading-relaxed text-role-parent-ink` |
| Score values | `font-sans font-extrabold text-xl` + mastery color |
| Labels, badges, meta | `font-sans text-xs font-bold text-role-parent-muted` |
| Buttons | `font-sans font-bold` |
| "Read more" links | `font-sans text-xs font-bold text-brand-gold hover:text-brand-gold-dark` |

> Why Lora for Parents?
> Lora is a book-style serif with warmth at body sizes. The AI narrative is a short
> letter — Lora makes it feel like a thoughtful note from the teacher, not a data readout.
> NO other role uses Lora.

#### Layout spec

```
Top nav:    h-14 bg-white border-b border-role-parent-border
            Left: font-['Lora'] italic "Kaihle" — the only role with italic logo text
            Right: avatar only (no nav links)
Content:    bg-role-parent-bg p-4
            max-w-lg mx-auto  ← narrow reading column on tablet+
            This is a reading experience, not a grid
```

#### Narrative Card (hero component of Parent app)

```tsx
<div className="bg-white rounded-2xl border-[1.5px] border-role-parent-border p-5">
  <div className="flex items-center gap-2 mb-3">
    <span className="w-2 h-2 rounded-full bg-brand-primary flex-shrink-0" />
    <span className="font-sans text-xs font-bold uppercase tracking-wide text-role-parent-muted">
      Latest update · {formattedDate}
    </span>
  </div>
  <p className="font-['Lora'] text-sm leading-relaxed text-role-parent-ink">{narrative}</p>
  <button className="mt-3 font-sans text-xs font-bold text-brand-gold hover:text-brand-gold-dark transition-colors">
    Read full report →
  </button>
</div>
```

#### Buttons

```
Primary:   bg-brand-primary text-white rounded-full (rare — "View report" only)
Text link: text-brand-gold font-bold hover:text-brand-gold-dark (most CTAs)
```

---

## 6. Layout Architecture Summary

| Role | Layout Wrapper | Sidebar | Page Bg | Primary Font |
|---|---|---|---|---|
| Kaihle Admin | `AdminLayout` | White + gray borders | `#f8f9fb` | Inter |
| School Admin | `DashboardLayout variant="school-admin"` | White + green borders | `#f5f7f1` | Fraunces + Nunito |
| Teacher | `DashboardLayout variant="teacher"` | White + gray borders | `#f5f7f1` | Fraunces + Nunito |
| Student | `StudentLayout` | None (top nav + bottom nav) | `#f9fafb` | Fraunces + Nunito |
| Parent | `ParentLayout` | None (top nav only) | `#fdf8f0` | Lora + Nunito |

All layout wrappers: `frontend/packages/ui/src/layouts/`.

### Sidebar Active State by Role

| Role | Pattern | Tailwind |
|---|---|---|
| Kaihle Admin | Green dot before label | `text-role-admin-ink bg-gray-100` + dot `bg-brand-primary` |
| School Admin | Left green stripe + green tint | `border-l-[3px] border-brand-primary bg-brand-light text-brand-primary rounded-r-lg rounded-l-none` |
| Teacher | Gold tint fill | `bg-[#fffbeb] text-brand-gold-dark font-bold` |

### Sidebar Dimensions (DashboardLayout + AdminLayout)

```
Width:         w-56 (224px)
Logo row:      h-14 border-b
Nav item:      px-3 py-2.5 mx-2 rounded-lg text-sm font-semibold gap-2
Section label: px-3 pt-4 pb-1 text-[10px] font-bold uppercase tracking-widest
```

---

## 7. Spacing & Responsive

### Spacing Conventions

| Context | Value |
|---|---|
| Page content padding desktop | `p-6` |
| Page content padding mobile | `p-4` |
| Card padding | `p-5` standard, `p-4` compact |
| Card gap in grid | `gap-4` |
| Stacked sections | `space-y-6` |
| Form fields | `space-y-4` |

### Breakpoints (mobile-first)

| Prefix | Min-width |
|---|---|
| base | 0px |
| `sm:` | 640px |
| `md:` | 768px — sidebar appears for dashboard roles |
| `lg:` | 1024px |
| `xl:` | 1280px |

Student + Parent: designed at 375px, comfortable at `md:`.
Teacher + School Admin: designed at `lg:`, sidebar collapses at `md:`.
Kaihle Admin: desktop acceptable, no mobile requirement.
Touch targets: `min-h-[44px] min-w-[44px]` on all interactive elements.

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

## 9. Accessibility (All Roles — Non-Negotiable)

1. Mastery color indicators MUST have `aria-label` — colour is never the only signal.
2. All interactive elements MUST have focus ring: `focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2`
3. All form inputs MUST have a visible `<label>` or `aria-label`.
4. Touch targets: `min-h-[44px] min-w-[44px]`
5. Contrast checks:
   - `brand-ink` on white: 14.3:1 ✓
   - `white` on `brand-primary`: 7.2:1 ✓
   - `white` on `brand-gold`: 3.1:1 ✗ — use `brand-gold-dark` for text on gold backgrounds

---

## 10. Hard Rules

- ❌ No colored sidebar backgrounds — all sidebars are white
- ❌ No `indigo-*`, `emerald-*` for brand or mastery colors
- ❌ No `emerald-500` for Strong mastery — use `brand-green` (#16a34a)
- ❌ No green buttons in Teacher role — use gold buttons for Teacher actions
- ❌ No Fraunces or Lora in Kaihle Admin — Inter only
- ❌ No Lora in any role except Parent
- ❌ No font-size in px — always rem via Tailwind text scale
- ❌ No `!important`
- ❌ No per-page layout shells — use shared wrappers from `packages/ui`
- ❌ No `@apply` in component files — utility classes in JSX only
- ❌ No additional UI kits (MUI, Chakra, shadcn) — see CONSTITUTION §4 Rule 11

---

## 11. File Map

| Need | Location |
|---|---|
| Tailwind tokens (brand + role) | `frontend/packages/ui/tailwind.config.js` |
| Google Fonts import | Each app's `src/index.css` |
| Layout wrappers | `frontend/packages/ui/src/layouts/` |
| Shared components | `frontend/packages/ui/src/components/` |
| Mastery helper | `frontend/packages/types/src/mastery.ts` |

---

*Kaihle Design System v2.0 · Pixel (UX/UI Lead) · March 2026*
*Supersedes v1.0. Load alongside CONSTITUTION.md for every frontend task.*
