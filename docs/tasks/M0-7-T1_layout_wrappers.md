# M0-7-T1 — Shared Layout Wrappers
**Milestone:** M0 — Foundations
**Epic:** M0-7 — Frontend Foundations (new epic)
**Task ID:** M0-7-T1
**Depends on:** M0-3-T5 (login UI, auth hooks), M0-1-T1 (monorepo structure)
**Blocks:** Every UI task from M0-6-T4 onwards — nothing can be built without these
**Estimated effort:** 4–6 hours

---

## Context

Every UI task in the codebase references layout wrappers (`DashboardLayout`, `StudentLayout`,
`ParentLayout`, `AuthLayout`, `OnboardingLayout`) but none of them exist. This task builds all
five wrappers in `packages/ui` so that every subsequent UI task can compose from them rather
than inventing ad-hoc layout structure.

Read `docs/design/DESIGN_SYSTEM.md` §5 and §6 before writing any code.
These wrappers implement the per-role design specs exactly as defined there.

---

## User Story

As a coding agent implementing any frontend feature, I want shared layout wrappers already
built so I can focus on the page content, not re-inventing the sidebar and navbar on every task.

---

## Files to Create

```
packages/ui/src/layouts/
  DashboardLayout.tsx       ← Teacher + School Admin (variant prop)
  StudentLayout.tsx         ← Student (top nav + mobile bottom nav)
  ParentLayout.tsx          ← Parent (minimal top nav, narrow reading column)
  AdminLayout.tsx           ← Kaihle Admin (Inter font, cool bg)
  AuthLayout.tsx            ← Login screen for all roles
  OnboardingLayout.tsx      ← Student onboarding steps

packages/ui/src/components/nav/
  Sidebar.tsx               ← Used by DashboardLayout + AdminLayout
  TopNav.tsx                ← Used by all layouts
  BottomNav.tsx             ← Used by StudentLayout (mobile only)
  NavItem.tsx               ← Single nav item (dot / stripe / tint variant)

packages/ui/src/layouts/index.ts    ← re-export all
```

---

## Navigation Specs by Role

### DashboardLayout — Teacher variant (`variant="teacher"`)

Sidebar links (in order):
```
Section: MY CLASSES
  - Dashboard         → /teacher/dashboard
  - Gap Map           → /teacher/classes/:classId/gap-map   (links to last active class)
  - Assessments       → /teacher/classes/:classId/assessments
  - Lesson Plans      → /teacher/classes/:classId/lesson-plans

Section: STUDENTS
  - My Students       → /teacher/classes/:classId/students

Section: TOOLS
  - Study Plans       → (no dedicated page — see gap map assign)
```

Top nav right: `[+ Assessment]` gold button + user avatar + name

Active state: **gold tint** — `bg-[#fffbeb] text-brand-gold-dark font-bold`

### DashboardLayout — School Admin variant (`variant="school-admin"`)

Sidebar links (in order):
```
Section: SCHOOL
  - Overview          → /school/overview
  - Teachers          → /school/users?role=teacher
  - Students          → /school/users?role=student
  - Classes           → /school/classes

Section: ADMIN
  - Analytics         → /admin/analytics
  - Billing           → /school/billing
```

Top nav right: `[Invite teacher]` green button + user avatar + name

Active state: **left green stripe** — `border-l-[3px] border-brand-primary bg-brand-light text-brand-primary rounded-r-lg rounded-l-none`

### AdminLayout — Kaihle Admin

Sidebar links (in order):
```
Section: PLATFORM
  - Overview          → /kaihle-admin/overview
  - Schools           → /kaihle-admin/schools
  - Users             → /kaihle-admin/users
  - Billing           → /kaihle-admin/billing

Section: SYSTEM
  - Logs              → /kaihle-admin/logs
  - Config            → /kaihle-admin/config
```

Top nav right: `[+ Add school]` green button + user avatar

Active state: **gray fill + green dot** — `bg-gray-100 text-role-admin-ink` with `w-1.5 h-1.5 rounded-full bg-brand-primary` dot

### StudentLayout — Bottom nav items (mobile)

```
1. Home       → /student/dashboard     (icon: Home)
2. Progress   → /student/my-progress   (icon: BarChart2)
3. Study      → /student/study-plans   (icon: BookOpen)
4. Assessments→ /student/assessments   (icon: ClipboardList)
```

Active state: `text-brand-primary` — no background fill on mobile nav items.
Desktop: top nav shows the same 4 as horizontal tabs with active underline.

### ParentLayout — Top nav only

```
Left:  Lora italic "Kaihle" logo
Right: User avatar + name only (no nav links — parents have one destination)
```

No sidebar. No bottom nav. Top nav links to nothing — parents navigate via in-page CTAs.

---

## Component Specs

### `DashboardLayout.tsx`

```tsx
interface DashboardLayoutProps {
  variant: 'teacher' | 'school-admin'
  children: React.ReactNode
  pageTitle: string
  pageSubtitle?: string
  topNavAction?: React.ReactNode   // the role-specific CTA button
  classId?: string                 // used to build class-specific nav links
}
```

Structure:
```
<div class="flex h-screen overflow-hidden bg-[role-specific-bg]">
  <Sidebar variant={variant} classId={classId} />
  <div class="flex flex-col flex-1 min-w-0 overflow-hidden">
    <TopNav pageTitle={pageTitle} pageSubtitle={pageSubtitle} topNavAction={topNavAction} />
    <main class="flex-1 overflow-y-auto p-6">
      {children}
    </main>
  </div>
</div>
```

Sidebar dimensions: `w-56 flex-shrink-0`
Topnav height: `h-14`
Both: `bg-white border-[role-specific-border]`

### `StudentLayout.tsx`

```tsx
interface StudentLayoutProps {
  children: React.ReactNode
  pageTitle?: string
  activeNav?: 'home' | 'progress' | 'study' | 'assessments'
}
```

Structure:
```
<div class="min-h-screen bg-role-student-bg">
  <TopNav (Student variant — subject tabs on desktop) />
  <main class="pb-20 md:pb-6 p-4 md:p-6">
    {children}
  </main>
  <BottomNav activeItem={activeNav} class="md:hidden fixed bottom-0 inset-x-0" />
</div>
```

### `ParentLayout.tsx`

```tsx
interface ParentLayoutProps {
  children: React.ReactNode
}
```

Structure:
```
<div class="min-h-screen bg-role-parent-bg">
  <TopNav (Parent variant — logo + avatar only) />
  <main class="p-4 max-w-lg mx-auto">
    {children}
  </main>
</div>
```

### `AdminLayout.tsx`

```tsx
interface AdminLayoutProps {
  children: React.ReactNode
  pageTitle: string
  pageSubtitle?: string
  topNavAction?: React.ReactNode
}
```

Same structure as DashboardLayout. Uses `role-admin-*` tokens throughout.
Font: `font-['Inter']` on all text — no Fraunces.

### `AuthLayout.tsx`

Used by: Login page (all roles), password reset.

```tsx
interface AuthLayoutProps {
  children: React.ReactNode  // the form card
}
```

Structure:
```
<div class="min-h-screen bg-brand-bg flex items-center justify-center p-4">
  <div class="w-full max-w-md">
    <div class="text-center mb-8">
      <span class="font-display font-bold text-2xl text-brand-ink">Kaihle</span>
    </div>
    {children}
  </div>
</div>
```

### `OnboardingLayout.tsx`

Used by: Student onboarding questionnaire + diagnostic hub.

```tsx
interface OnboardingLayoutProps {
  children: React.ReactNode
  step: number           // 1 | 2
  totalSteps: number     // 2
  stepLabel: string      // "Learning profile" | "Subject diagnostics"
}
```

Structure:
```
<div class="min-h-screen bg-brand-bg">
  <header class="bg-white border-b border-brand-border h-14 flex items-center px-6">
    <span class="font-display font-bold text-lg text-brand-ink">Kaihle</span>
    <div class="ml-auto text-sm text-brand-muted font-semibold">
      Step {step} of {totalSteps} — {stepLabel}
    </div>
  </header>
  <main class="p-4 md:p-8 max-w-2xl mx-auto">
    {children}
  </main>
</div>
```

---

## Sidebar Implementation Details

### `NavItem.tsx`

```tsx
interface NavItemProps {
  label: string
  href: string
  icon?: LucideIcon
  isActive: boolean
  variant: 'teacher' | 'school-admin' | 'admin'
}
```

Active class map:
```
teacher:      bg-[#fffbeb] text-brand-gold-dark font-bold rounded-lg
school-admin: border-l-[3px] border-brand-primary bg-brand-light text-brand-primary
              rounded-r-lg rounded-l-none (override mx-2 with ml-0 mr-2)
admin:        bg-gray-100 text-role-admin-ink rounded-lg (+ green dot)
```

Inactive: `text-[role-body] hover:bg-[role-hover] rounded-lg`

### `BottomNav.tsx`

```tsx
// Fixed bottom bar, mobile only (md:hidden)
// 4 items: equal-width flex children
// Each item: flex col, icon + label text-[10px]
// Active: text-brand-primary
// Touch target: min-h-[56px] full height of nav
```

---

## Acceptance Criteria

- [ ] `DashboardLayout variant="teacher"` renders sidebar with correct 7 nav items in correct sections
- [ ] `DashboardLayout variant="school-admin"` renders sidebar with correct 6 nav items + left stripe active
- [ ] Active nav item highlights correctly for each variant (gold tint / green stripe / gray fill)
- [ ] `StudentLayout` renders top nav + main content + bottom nav (visible on <768px, hidden on md+)
- [ ] `StudentLayout` bottom nav has 4 items with correct routes and Lucide icons
- [ ] `ParentLayout` renders top nav with Lora italic logo + avatar, narrow `max-w-lg` content column
- [ ] `AdminLayout` uses Inter font throughout — no Fraunces visible anywhere
- [ ] `AuthLayout` centers card on brand-bg background
- [ ] `OnboardingLayout` shows step indicator ("Step 1 of 2 — Learning profile")
- [ ] All layouts use correct page background colors per DESIGN_SYSTEM.md §5
- [ ] All layouts export from `packages/ui/src/layouts/index.ts`
- [ ] Responsive: DashboardLayout sidebar collapses to icons-only at md: breakpoint
- [ ] Responsive: StudentLayout bottom nav hidden at md:, top nav tabs visible
- [ ] Unit test: `NavItem isActive={true} variant="teacher"` → gold tint class applied
- [ ] Unit test: `NavItem isActive={true} variant="school-admin"` → green stripe class applied
- [ ] Unit test: `BottomNav activeItem="progress"` → Progress item has `text-brand-primary`
- [ ] Accessibility: sidebar nav uses `<nav aria-label="Main navigation">`
- [ ] Accessibility: active nav item has `aria-current="page"`
- [ ] Accessibility: bottom nav items have `aria-label` on icon-only items

---

## Output — What Every Subsequent UI Task Can Use

```tsx
// Teacher page
import { DashboardLayout } from '@kaihle/ui'

export function GapMapPage() {
  return (
    <DashboardLayout
      variant="teacher"
      pageTitle="Gap Map"
      pageSubtitle="Mathematics · Grade 9 · Class 9B"
      topNavAction={<button className="btn-primary">+ Assessment</button>}
      classId={classId}
    >
      {/* page content here */}
    </DashboardLayout>
  )
}

// Student page
import { StudentLayout } from '@kaihle/ui'

export function MyProgressPage() {
  return (
    <StudentLayout pageTitle="My Progress" activeNav="progress">
      {/* page content here */}
    </StudentLayout>
  )
}
```

**Unlocks:** Every UI task in M0-M6 that builds a page.
