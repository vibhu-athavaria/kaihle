# M0-7-T3-patch — Student Dashboard: Complete Gap Fix
**Milestone:** M0 — Foundations
**Epic:** M0-7 — Frontend Foundations
**Task ID:** M0-7-T3-patch
**Executor:** Coding agent
**Parent task:** `docs/tasks/M0-7-T3_student_dashboard.md`
**Depends on:** M0-7-T3 (already merged — this patches it)
**Blocks:** Nothing
**Estimated effort:** 3–4 hours
**Reference mockup:** `docs/design/mockups/student_dashboard.html`
**Design authority:** `docs/design/DESIGN_SYSTEM.md` §5.4 · `docs/design/screens/STUDENT_SCREENS.md`

> **Read `docs/design/DESIGN_SYSTEM.md` §5.4 in full before writing a single line of code.**
> All colors, font sizes, spacing, and layout decisions are specified there.
> Do not invent values. Do not reuse sidebar pixel sizes in page content.

---

## Context — What Is Wrong

Screenshot review on 2026-03-30 identified five failures:

| # | Gap | Root cause |
|---|---|---|
| 1 | StudentLayout not updated to v2.1 sidebar spec | `StudentLayout` still uses `TopNav + BottomNav` — sidebar not implemented |
| 2 | Greeting missing from top nav | Top nav left side is empty — greeting text must live there per design spec |
| 3 | "Your subjects" section absent | `SubjectScoreCard.tsx` not rendered; gap-map API not called |
| 4 | Class cards show "Hi there" / "Your Teacher" | Agent hardcoded strings instead of reading API response fields |
| 5 | "What's waiting for you" hidden when no steps | Section hidden entirely; weakest-subject step never computed |

Backend gap: `subject_id` UUID missing from `GET /students/me/classes` response, blocking gap-map calls.

**Do not merge partial fixes. All five must be resolved in this task.**

---

## Do NOT Touch

- `frontend/apps/student/src/pages/onboarding/` — any file in this directory
- `frontend/apps/student/src/hooks/useOnboardingStatus.ts`
- `frontend/apps/student/src/pages/dashboard/NextStepCard.tsx`
- `frontend/apps/student/src/pages/dashboard/StreakBadge.tsx`
- Any file in `apps/teacher/`, `apps/parent/`, `apps/school-admin/`, `apps/kaihle-admin/`
- `packages/ui/src/layouts/DashboardLayout.tsx`
- `packages/ui/src/components/nav/Sidebar.tsx`

---

## Typography Reference — Student App

**Read this table before writing any className. Every text element in this task maps to one row.**

### Rule: Sidebar chrome vs page content

Sidebar chrome (section labels, nav items, profile card) uses the explicit pixel values
specified in `DESIGN_SYSTEM.md §5.4 Sidebar spec`. These are the only elements where
pixel font sizes are permitted in this task.

Page content (greeting, score cards, class cards, next step cards, section headings)
must use the Tailwind rem-based type scale — never raw pixel values.
`DESIGN_SYSTEM.md` Hard Rule: *"No font-size in px — always rem via Tailwind text scale."*

### Sidebar chrome — pixel sizes (permitted only here)

| Element | Tailwind class | px equivalent |
|---|---|---|
| Sidebar logo "Kaihle" | `font-display italic font-semibold text-[15px] text-brand-ink` | 15px |
| Section labels (LEARN, CLASSES) | `font-sans font-bold text-[9px] uppercase tracking-[0.8px] text-brand-muted` | 9px |
| Nav item label | `font-sans text-[12px]` | 12px |
| Avatar initials | `font-sans font-bold text-[10px] text-brand-primary` | 10px |
| Profile name | `font-sans font-semibold text-[11px] text-brand-ink` | 11px |
| Profile grade + curriculum | `font-sans text-[9px] text-brand-muted` | 9px |
| Logout label | `font-sans text-[11px] text-brand-muted` | 11px |

### Top nav — pixel sizes (explicitly specified in §5.4 Top nav spec)

| Element | Tailwind class | px equivalent |
|---|---|---|
| Greeting "Good morning, Aditya 👋" | `font-sans font-medium text-[13px] text-brand-ink` | 13px |
| Grade + curriculum subtitle | `font-sans text-[10px] text-brand-muted` | 10px |

### Page content — rem scale (Tailwind tokens only)

| Element | Tailwind class | rem / px equivalent |
|---|---|---|
| Page greeting heading (h1) | `font-display font-bold text-2xl text-brand-ink` | 1.5rem / 24px |
| Grade + curriculum subtitle | `font-sans text-sm text-brand-muted` | 0.875rem / 14px |
| Section heading (MY CLASSES etc.) | `font-sans text-xs font-bold uppercase tracking-widest text-brand-muted` | 0.75rem / 12px |
| Subject score value | `font-sans font-extrabold text-2xl` + mastery textClass | 1.5rem / 24px |
| Subject name label in score card | `font-sans font-bold text-xs uppercase tracking-wide text-brand-muted` | 0.75rem / 12px |
| Mastery band label in score card | `font-sans text-xs text-brand-muted` | 0.75rem / 12px |
| Class card name | `font-sans font-semibold text-sm text-brand-ink` | 0.875rem / 14px |
| Grade pill in class card | `font-sans font-semibold text-xs text-brand-muted` | 0.75rem / 12px |
| Teacher + grade meta in class card | `font-sans text-xs text-brand-muted` | 0.75rem / 12px |
| Class card footer link (locked) | `font-sans font-semibold text-xs text-brand-gold flex items-center gap-1` | 0.75rem / 12px |
| Class card footer link (unlocked) | `font-sans font-semibold text-xs text-brand-primary` | 0.75rem / 12px |
| Next step card title | `font-sans font-semibold text-sm text-brand-ink` | 0.875rem / 14px |
| Next step card subtitle | `font-sans text-xs text-brand-muted` | 0.75rem / 12px |
| Next step action link | `font-sans font-bold text-xs text-brand-primary` | 0.75rem / 12px |

---

## Fix 1 — Rewrite `StudentLayout.tsx` (sidebar + top nav with greeting)

### Props interface

```typescript
// packages/ui/src/layouts/StudentLayout.tsx

export type StudentNavItem = 'home' | 'progress' | 'study-plans' | 'assessments'

export interface StudentClass {
  id: string
  name: string                                              // "Mathematics 9B"
  subjectName: string                                       // "Mathematics"
  subjectId: string                                         // UUID
  diagnosticStatus: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED'
  diagnosticAttemptId: string | null
}

export interface StudentLayoutProps {
  children: React.ReactNode
  activeNav: StudentNavItem      // required — every page must pass this explicitly
  classes?: StudentClass[]       // enrolled classes — populates sidebar CLASSES section
  studentName: string            // "Jane Doe" — sidebar profile card + avatar + top nav greeting
  gradeName: string              // "Grade 9" — sidebar profile card + top nav subtitle
  curriculumName: string         // "Cambridge IGCSE" — sidebar profile card + top nav subtitle
  onLogout: () => void           // sidebar logout button
}
```

### Subject dot color map — copy exactly, do not invent colors

Values from `DESIGN_SYSTEM.md §8 Subject Colors`:

```typescript
const SUBJECT_DOT_COLORS: Record<string, string> = {
  'Mathematics':          'bg-brand-primary',  // #1a5c38
  'Integrated Science':   'bg-violet-600',      // #7c3aed
  'Biology':              'bg-green-600',        // #16a34a
  'Chemistry':            'bg-amber-600',        // #d97706
  'Physics':              'bg-blue-600',         // #2563eb
  'English Language':     'bg-red-600',          // #dc2626
  'English Literature':   'bg-purple-600',       // #9333ea
}
function getSubjectDotColor(subjectName: string): string {
  return SUBJECT_DOT_COLORS[subjectName] ?? 'bg-brand-muted'
}
```

### Nav item → route map

```typescript
const NAV_ROUTES: Record<StudentNavItem, string> = {
  'home':         '/student/dashboard',
  'progress':     '/student/my-progress',
  'study-plans':  '/student/study-plans',
  'assessments':  '/student/assessments',
}
```

### Full `StudentLayout` implementation

```tsx
// packages/ui/src/layouts/StudentLayout.tsx
import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Home, BarChart2, BookOpen, ClipboardList, Lock, LogOut } from 'lucide-react'

export function StudentLayout({
  children,
  activeNav,
  classes = [],
  studentName,
  gradeName,
  curriculumName,
  onLogout,
}: StudentLayoutProps) {
  const navigate = useNavigate()

  // Avatar initials — "Jane Doe" → "JD", "Jane" → "J"
  const initials = studentName
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  const firstName = studentName.split(' ')[0] ?? studentName

  return (
    <div className="flex h-screen overflow-hidden bg-role-student-bg">

      {/* ── SIDEBAR ──────────────────────────────────────────── */}
      <aside
        className="w-[200px] flex-shrink-0 bg-white border-r border-role-student-border flex flex-col"
        aria-label="Sidebar"
      >

        {/* Logo row — h-[50px] must match topnav height */}
        <div className="h-[50px] flex items-center px-4 border-b border-role-student-border flex-shrink-0">
          <span className="font-display italic font-semibold text-[15px] text-brand-ink">
            Kaihle
          </span>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-2" aria-label="Main navigation">

          {/* LEARN section */}
          <div className="px-3.5 pt-4 pb-1 font-sans font-bold text-[9px] uppercase tracking-[0.8px] text-brand-muted">
            Learn
          </div>

          {([
            { key: 'home'        as StudentNavItem, label: 'Home',        Icon: Home },
            { key: 'progress'    as StudentNavItem, label: 'My progress', Icon: BarChart2 },
            { key: 'study-plans' as StudentNavItem, label: 'Study plans', Icon: BookOpen },
            { key: 'assessments' as StudentNavItem, label: 'Assessments', Icon: ClipboardList },
          ]).map(({ key, label, Icon }) => {
            const isActive = activeNav === key
            return (
              <Link
                key={key}
                to={NAV_ROUTES[key]}
                aria-current={isActive ? 'page' : undefined}
                className={[
                  'flex items-center gap-2 mx-[6px] px-3 py-[7px] rounded-[6px]',
                  'font-sans text-[12px] transition-colors',
                  isActive
                    ? 'bg-[#f0fdf4] text-brand-primary font-semibold'
                    : 'text-brand-muted hover:bg-gray-50 hover:text-brand-ink',
                ].join(' ')}
              >
                {isActive
                  ? <span className="w-[6px] h-[6px] rounded-full bg-brand-primary flex-shrink-0" aria-hidden="true" />
                  : <Icon className="w-[13px] h-[13px] flex-shrink-0" aria-hidden="true" />
                }
                {label}
              </Link>
            )
          })}

          {/* CLASSES section — dynamic */}
          {classes.length > 0 && (
            <>
              <div className="px-3.5 pt-4 pb-1 font-sans font-bold text-[9px] uppercase tracking-[0.8px] text-brand-muted">
                Classes
              </div>
              {classes.map(cls => {
                const isLocked = cls.diagnosticStatus !== 'COMPLETED'
                const route = isLocked
                  ? (cls.diagnosticAttemptId
                      ? `/student/assessments/${cls.diagnosticAttemptId}/take`
                      : `/student/classes/${cls.id}/diagnostic`)
                  : `/student/classes/${cls.id}/topics`
                return (
                  <Link
                    key={cls.id}
                    to={route}
                    className={[
                      'flex items-center gap-2 mx-[6px] px-3 py-[7px] rounded-[6px]',
                      'font-sans text-[12px] transition-colors',
                      isLocked
                        ? 'text-brand-gold hover:bg-[#fffbeb]'
                        : 'text-brand-muted hover:bg-gray-50 hover:text-brand-ink',
                    ].join(' ')}
                  >
                    {isLocked
                      ? <Lock className="w-[11px] h-[11px] flex-shrink-0" aria-hidden="true" />
                      : <span className={`w-[7px] h-[7px] rounded-full flex-shrink-0 ${getSubjectDotColor(cls.subjectName)}`} aria-hidden="true" />
                    }
                    {cls.name}
                  </Link>
                )
              })}
            </>
          )}
        </nav>

        {/* ── PROFILE CARD — pinned at sidebar bottom ──────────── */}
        <div className="border-t border-role-student-border flex-shrink-0">

          {/* Profile row → /student/settings on click */}
          <button
            type="button"
            onClick={() => navigate('/student/settings')}
            className="w-full flex items-center gap-2 px-3.5 py-3 hover:bg-gray-50 transition-colors text-left"
            aria-label={`${studentName} — open settings`}
          >
            <div
              className="w-[28px] h-[28px] rounded-full bg-brand-green-light flex items-center
                         justify-center font-sans font-bold text-[10px] text-brand-primary flex-shrink-0"
              aria-hidden="true"
            >
              {initials}
            </div>
            <div className="overflow-hidden min-w-0">
              <div className="font-sans font-semibold text-[11px] text-brand-ink truncate leading-tight">
                {studentName}
              </div>
              <div className="font-sans text-[9px] text-brand-muted truncate leading-tight">
                {gradeName} · {curriculumName}
              </div>
            </div>
          </button>

          {/* Logout — separate button below profile row */}
          <button
            type="button"
            onClick={onLogout}
            className="w-full flex items-center gap-2 px-3.5 py-2.5
                       font-sans text-[11px] text-brand-muted hover:text-brand-ink hover:bg-gray-50 transition-colors"
            aria-label="Log out"
          >
            <LogOut className="w-[13px] h-[13px] flex-shrink-0" aria-hidden="true" />
            Logout
          </button>
        </div>
      </aside>

      {/* ── MAIN AREA ─────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">

        {/* Top nav — greeting lives HERE per DESIGN_SYSTEM.md §5.4 Top nav spec */}
        <header
          className="h-[50px] bg-white border-b border-role-student-border
                     flex items-center justify-between px-[18px] flex-shrink-0"
        >
          {/* Left: greeting + grade/curriculum */}
          <div>
            <div className="font-sans font-medium text-[13px] text-brand-ink leading-tight">
              {getGreeting()}, {firstName} 👋
            </div>
            {gradeName && curriculumName && (
              <div className="font-sans text-[10px] text-brand-muted leading-tight">
                {gradeName} · {curriculumName}
              </div>
            )}
          </div>

          {/* Right: avatar → settings */}
          <button
            type="button"
            onClick={() => navigate('/student/settings')}
            className="w-[28px] h-[28px] rounded-full bg-brand-green-light flex items-center
                       justify-center font-sans font-bold text-[10px] text-brand-primary
                       hover:opacity-80 transition-opacity flex-shrink-0"
            aria-label={`${studentName} — open settings`}
          >
            {initials}
          </button>
        </header>

        {/* Page content — children render here */}
        <main className="flex-1 overflow-y-auto p-[18px]">
          {children}
        </main>
      </div>
    </div>
  )
}

// Greeting helper — shared by layout top nav
function getGreeting(): string {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}
```

### Exports — update `packages/ui/src/layouts/index.ts`

```typescript
export { StudentLayout } from './StudentLayout'
export type { StudentLayoutProps, StudentNavItem, StudentClass } from './StudentLayout'
```

### Remove BottomNav from StudentLayout

Delete the `<BottomNav>` import and usage. It is superseded by the sidebar in v2.1.

---

## Fix 2 — Remove greeting from page content, pass data into StudentLayout

The greeting now lives in the top nav (rendered by `StudentLayout`). Remove the `<h1>`
greeting block from the page content area in `StudentDashboard.tsx`. The layout
receives `studentName`, `gradeName`, `curriculumName` as props and renders the greeting.

### `useStudentInfo` hook — student identity

Student name, grade, and curriculum come from `GET /api/v1/students/me/info`.
Do NOT read from `user?.first_name` in the auth context — use this endpoint.

Create `frontend/apps/student/src/hooks/useStudentInfo.ts`:

```typescript
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@kaihle/api-client'

export interface StudentInfo {
  id: string
  first_name: string
  last_name: string
  grade_name: string        // "Grade 9"
  curriculum_name: string   // "Cambridge IGCSE" or "Cambridge Lower Secondary"
  school_id: string         // UUID — needed by other API calls
}

export const useStudentInfo = () =>
  useQuery<StudentInfo>({
    queryKey: ['student', 'info'],
    queryFn: async () => {
      const res = await apiClient.get('/students/me/info')
      return res.data
    },
    staleTime: 10 * 60 * 1000,   // student info rarely changes
  })
```

**API call:**

```
GET /api/v1/students/me/info
Authorization: Bearer {access_token}

Response 200:
{
  "id": "uuid",
  "first_name": "Jane",
  "last_name": "Doe",
  "grade_name": "Grade 9",
  "curriculum_name": "Cambridge IGCSE",
  "school_id": "uuid"
}
```

### `useMyClasses` hook — class list

⚠️ `GET /api/v1/students/me/classes` **does not yet exist** in the live API.
Fix 6 (backend) must CREATE this endpoint before this hook can work.
The hook is written here so frontend and backend can be implemented together.

Create `frontend/apps/student/src/hooks/useMyClasses.ts`:

```typescript
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@kaihle/api-client'

export interface StudentClassItem {
  id: string
  name: string                                              // "Mathematics 9B"
  subject_id: string                                        // UUID — required for gap-map calls
  subject_name: string                                      // "Mathematics"
  grade_name: string                                        // "Grade 9"
  teacher_name: string                                      // "Ms. Ravi"
  curriculum_id: string
  academic_year: string
  is_active: boolean
  onboarding_diagnostic_status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED'
  diagnostic_attempt_id: string | null
}

export const useMyClasses = () =>
  useQuery<StudentClassItem[]>({
    queryKey: ['student', 'my-classes'],
    queryFn: async () => {
      const res = await apiClient.get('/students/me/classes')
      return res.data
    },
    staleTime: 2 * 60 * 1000,
  })
```

**API call (must be created — see Fix 6):**

```
GET /api/v1/students/me/classes
Authorization: Bearer {access_token}

Response 200:
[
  {
    "id": "uuid",
    "name": "Mathematics 9B",
    "subject_id": "uuid",
    "subject_name": "Mathematics",
    "grade_name": "Grade 9",
    "teacher_name": "Ms. Ravi",
    "curriculum_id": "uuid",
    "academic_year": "2025-2026",
    "is_active": true,
    "onboarding_diagnostic_status": "PENDING",
    "diagnostic_attempt_id": null
  }
]

Response 403: non-STUDENT JWT
```

### Updated `StudentDashboard.tsx`

```tsx
// frontend/apps/student/src/pages/dashboard/StudentDashboard.tsx
import React, { useState, useMemo, useCallback } from 'react'
import { StudentLayout, StudentClass } from '@kaihle/ui'
import { useAuth } from '@kaihle/auth'
import { useStudentInfo } from '../../hooks/useStudentInfo'
import { useMyClasses } from '../../hooks/useMyClasses'
import { useStudentDashboard } from '../../hooks/useStudentDashboard'
import { SubjectScoresSection } from './SubjectScoresSection'
import { ClassCard, ClassCardSkeleton } from '../../components/ClassCard'
import { NextStepCard, EmptyNextSteps } from './NextStepCard'

function SkeletonNextStep() {
  return (
    <div className="bg-white border border-role-student-border rounded-2xl p-4 animate-pulse h-[64px]" />
  )
}

export function StudentDashboard() {
  const { logout, user } = useAuth()

  const { data: classesData, isLoading: isClassesLoading } = useMyClasses()
  const { data: dashboardData, isLoading: isDashboardLoading } = useStudentDashboard()

  // Subject scores lifted from SubjectScoresSection for buildNextSteps priority 4
  const [resolvedSubjectScores, setResolvedSubjectScores] = useState<
    { subjectName: string; avgMastery: number | null }[]
  >([])
  const handleScoresResolved = useCallback(
    (scores: { subjectName: string; avgMastery: number | null }[]) => {
      setResolvedSubjectScores(scores)
    },
    []
  )

  // Identity — from GET /api/v1/students/me/info (NOT auth context)
  const { data: studentInfo } = useStudentInfo()
  const firstName      = studentInfo?.first_name   ?? ''
  const lastName       = studentInfo?.last_name    ?? ''
  const studentName    = [firstName, lastName].filter(Boolean).join(' ') || 'Student'
  const gradeName      = studentInfo?.grade_name      ?? ''
  const curriculumName = studentInfo?.curriculum_name ?? ''

  // Sidebar classes
  const sidebarClasses: StudentClass[] = useMemo(
    () => (classesData ?? []).map(cls => ({
      id:                  cls.id,
      name:                cls.name,
      subjectName:         cls.subject_name,
      subjectId:           cls.subject_id,
      diagnosticStatus:    cls.onboarding_diagnostic_status,
      diagnosticAttemptId: cls.diagnostic_attempt_id,
    })),
    [classesData]
  )

  // Unique subjects for score cards — one card per unique subject_id
  const uniqueSubjects = useMemo(() => {
    const seen = new Set<string>()
    return (classesData ?? []).reduce<{ subjectId: string; subjectName: string }[]>(
      (acc, cls) => {
        if (!seen.has(cls.subject_id)) {
          seen.add(cls.subject_id)
          acc.push({ subjectId: cls.subject_id, subjectName: cls.subject_name })
        }
        return acc
      },
      []
    )
  }, [classesData])

  // Next steps
  const studyPlans       = dashboardData?.studyPlans ?? []
  const assessments      = dashboardData?.assessments ?? []
  const activeStudyPlans = studyPlans.filter(sp => sp.status === 'ACTIVE')
  const inProgressPlans  = studyPlans.filter(sp => sp.status === 'IN_PROGRESS')
  const nextSteps        = buildNextSteps(assessments, activeStudyPlans, inProgressPlans, resolvedSubjectScores)

  return (
    <StudentLayout
      activeNav="home"
      classes={sidebarClasses}
      studentName={studentName}
      gradeName={gradeName}
      curriculumName={curriculumName}
      onLogout={logout}
    >
      {/*
        NOTE: NO <h1> greeting here — greeting lives in StudentLayout top nav.
        Page content starts directly with the first data section.
      */}
      <div className="space-y-6">

        {/* YOUR SUBJECTS */}
        {(uniqueSubjects.length > 0 || isClassesLoading) && (
          <SubjectScoresSection
            subjects={uniqueSubjects}
            isLoading={isClassesLoading}
            onScoresResolved={handleScoresResolved}
          />
        )}

        {/* MY CLASSES */}
        <div>
          <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-brand-muted mb-3">
            My classes
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {isClassesLoading
              ? Array.from({ length: 2 }).map((_, i) => <ClassCardSkeleton key={i} />)
              : (classesData ?? []).map(cls => (
                  <ClassCard
                    key={cls.id}
                    classId={cls.id}
                    className={cls.name}                          // "Mathematics 9B"
                    subjectName={cls.subject_name}                // "Mathematics"
                    gradeName={cls.grade_name}                    // "Grade 9"
                    teacherName={cls.teacher_name}                // "Ms. Ravi" — NEVER hardcode
                    diagnosticStatus={cls.onboarding_diagnostic_status}
                    diagnosticAttemptId={cls.diagnostic_attempt_id ?? undefined}
                    hasNewMessages={false}
                    hasNewProgressCheck={false}
                    topicCount={0}
                  />
                ))}
          </div>
        </div>

        {/* WHAT'S WAITING FOR YOU — always rendered */}
        <div>
          <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-brand-muted mb-3">
            What's waiting for you
          </h2>
          <div className="space-y-3">
            {isDashboardLoading ? (
              <><SkeletonNextStep /><SkeletonNextStep /></>
            ) : nextSteps.length > 0 ? (
              nextSteps.slice(0, 3).map(step => <NextStepCard key={step.id} {...step} />)
            ) : (
              <EmptyNextSteps />
            )}
          </div>
        </div>

      </div>
    </StudentLayout>
  )
}
```

---

## Fix 3 — Create `SubjectScoresSection.tsx`

### API call

```
GET /api/v1/students/me/gap-map?subject_id={uuid}
Authorization: Bearer {access_token}

Called once per unique subject_id. React Query parallelises automatically.
If student has 3 subjects: 3 calls fired simultaneously.

Response 200 — StudentGapMap:
{
  "student_id": "uuid",
  "subject_id": "uuid",
  "generated_at": "2026-03-30T10:00:00Z",
  "scores": [
    {
      "subtopic_id": "uuid",
      "subtopic_name": "Linear Equations",
      "topic_id": "uuid",
      "topic_name": "Algebra",
      "mastery_score": 0.72,     ← null if student not yet assessed on this subtopic
      "last_assessed_at": "..."  ← null if not assessed
    }
  ]
}
```

### Aggregate helper

```typescript
// Average all non-null mastery_score values. Returns null when nothing assessed.
function aggregateSubjectMastery(gapMapData: any): number | null {
  const assessed = (gapMapData?.scores ?? [])
    .map((s: any) => s.mastery_score)
    .filter((v: any): v is number => typeof v === 'number')
  if (assessed.length === 0) return null
  return assessed.reduce((sum: number, v: number) => sum + v, 0) / assessed.length
}
```

### Border class map

Derived from `getMasteryStyle().bgClass` — from `DESIGN_SYSTEM.md §5.4 Subject Score Cards`:

```typescript
const BORDER_CLASS_MAP: Record<string, string> = {
  'bg-brand-green-light': 'border-brand-mid',       // Strong  — green border #b5d4bc
  'bg-brand-amber-light': 'border-brand-gold-mid',  // Developing — gold border #e8c97a
  'bg-brand-red-light':   'border-brand-red/30',    // Needs Work — soft red
  'bg-gray-50':           'border-role-student-border', // Not assessed — neutral
}
```

### Score card typography — from Typography Reference table above

| Element | Class |
|---|---|
| Score value | `font-sans font-extrabold text-2xl` + `textClass` from `getMasteryStyle` |
| Subject name | `font-sans font-bold text-xs uppercase tracking-wide text-brand-muted mt-1` |
| Band label | `font-sans text-xs text-brand-muted mt-0.5` |

### Full component

```tsx
// frontend/apps/student/src/pages/dashboard/SubjectScoresSection.tsx
import React, { useEffect, useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@kaihle/api-client'
import { getMasteryStyle, scoreToPercent } from '@kaihle/types'

interface SubjectEntry { subjectId: string; subjectName: string }

interface SubjectScoresSectionProps {
  subjects: SubjectEntry[]
  isLoading: boolean
  onScoresResolved: (scores: { subjectName: string; avgMastery: number | null }[]) => void
}

// ── Single card — self-fetching (avoids hook-in-loop rule) ────────────────────
function SingleSubjectCard({
  subject,
  onResolved,
}: {
  subject: SubjectEntry
  onResolved: (name: string, avg: number | null) => void
}) {
  const { data, isLoading } = useQuery({
    queryKey: ['student', 'gap-map', subject.subjectId],
    queryFn: async () => {
      const res = await apiClient.get(
        `/students/me/gap-map?subject_id=${subject.subjectId}`
      )
      return res.data
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!subject.subjectId,
  })

  const avgMastery = aggregateSubjectMastery(data)

  useEffect(() => {
    if (!isLoading) onResolved(subject.subjectName, avgMastery)
  }, [isLoading, avgMastery, subject.subjectName, onResolved])

  if (isLoading) {
    return (
      <div
        className="bg-white rounded-2xl border-[1.5px] border-role-student-border
                   p-4 animate-pulse h-[96px]"
        aria-label={`Loading ${subject.subjectName}`}
      />
    )
  }

  const { bgClass, textClass, label } = getMasteryStyle(avgMastery)
  const borderClass = BORDER_CLASS_MAP[bgClass] ?? 'border-role-student-border'
  const displayPct  = scoreToPercent(avgMastery)   // "72%" or "–"

  return (
    <div
      className={`bg-white rounded-2xl border-[1.5px] ${borderClass} p-4 text-center`}
      aria-label={`${subject.subjectName}: ${label}, ${displayPct}`}
    >
      {/* Score — text-2xl per DESIGN_SYSTEM.md §5.4 Score values */}
      <div className={`font-sans font-extrabold text-2xl leading-tight ${textClass}`}>
        {displayPct}
      </div>
      {/* Subject name — text-xs per Typography Reference */}
      <div className="font-sans font-bold text-xs uppercase tracking-wide text-brand-muted mt-1">
        {subject.subjectName}
      </div>
      {/* Mastery band — text-xs */}
      <div className="font-sans text-xs text-brand-muted mt-0.5">
        {avgMastery !== null ? label : 'Not assessed'}
      </div>
    </div>
  )
}

// ── Section wrapper ────────────────────────────────────────────────────────────
export function SubjectScoresSection({
  subjects, isLoading, onScoresResolved,
}: SubjectScoresSectionProps) {
  const [resolved, setResolved] = useState<Record<string, number | null>>({})

  const handleResolved = useCallback(
    (subjectName: string, avgMastery: number | null) => {
      setResolved(prev => {
        const updated = { ...prev, [subjectName]: avgMastery }
        if (Object.keys(updated).length === subjects.length) {
          onScoresResolved(
            Object.entries(updated).map(([subjectName, avgMastery]) => ({ subjectName, avgMastery }))
          )
        }
        return updated
      })
    },
    [subjects.length, onScoresResolved]
  )

  return (
    <div>
      {/* Section heading — text-xs per Typography Reference */}
      <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-brand-muted mb-3">
        Your subjects
      </h2>
      <div className="grid grid-cols-3 gap-3">
        {isLoading
          ? Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="bg-white rounded-2xl border border-role-student-border p-4 animate-pulse h-[96px]" />
            ))
          : subjects.map(subject => (
              <SingleSubjectCard key={subject.subjectId} subject={subject} onResolved={handleResolved} />
            ))
        }
      </div>
    </div>
  )
}
```

---

## Fix 4 — Fix `ClassCard.tsx` — props, font sizes, routing

### Props interface

```typescript
interface ClassCardProps {
  classId: string
  className: string                                         // "Mathematics 9B" — card heading
  subjectName: string                                       // "Mathematics" — subject dot
  gradeName: string                                         // "Grade 9" — grade pill + meta
  teacherName: string                                       // "Ms. Ravi" — NEVER hardcode "Your Teacher"
  diagnosticStatus: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED'
  diagnosticAttemptId?: string
  hasNewMessages: boolean
  hasNewProgressCheck: boolean
  topicCount: number
}
```

### Full font spec — from Typography Reference table

Every element maps to the table. Do not deviate.

```tsx
// ClassCard.tsx — correct rendering

const isLocked = diagnosticStatus !== 'COMPLETED'
const dotColor = getSubjectDotColor(subjectName)   // from SUBJECT_DOT_COLORS map
const diagnosticRoute = diagnosticAttemptId
  ? `/student/assessments/${diagnosticAttemptId}/take`
  : `/student/classes/${classId}/diagnostic`

return (
  <div className={`bg-white border border-role-student-border rounded-2xl p-4 ${isLocked ? 'opacity-60' : ''}`}>

    {/* Top row */}
    <div className="flex items-center gap-[7px] mb-2">
      <span className={`w-[7px] h-[7px] rounded-full flex-shrink-0 ${dotColor}`} aria-hidden="true" />

      {/* Class name — text-sm font-semibold per Typography Reference */}
      <span className="font-sans font-semibold text-sm text-brand-ink">
        {className}   {/* NEVER hardcode. This is "Mathematics 9B" from the API */}
      </span>

      {/* Grade pill — text-xs */}
      <span className="font-sans font-semibold text-xs text-brand-muted bg-brand-border-soft
                       px-2 py-0.5 rounded-full ml-auto">
        {gradeName}
      </span>
    </div>

    {/* Teacher + grade meta — text-xs */}
    <div className="font-sans text-xs text-brand-muted mb-3">
      {teacherName}   {/* NEVER hardcode "Your Teacher". This is "Ms. Ravi" from the API */}
    </div>

    {/* Divider */}
    <hr className="border-t border-brand-border-soft mb-3" />

    {/* Footer link — text-xs font-semibold */}
    {isLocked ? (
      <Link
        to={diagnosticRoute}
        className="font-sans font-semibold text-xs text-brand-gold flex items-center gap-1"
      >
        <Lock className="w-3 h-3" aria-hidden="true" />
        Start diagnostic →
      </Link>
    ) : (
      <Link
        to={`/student/classes/${classId}/topics`}
        className="font-sans font-semibold text-xs text-brand-primary"
      >
        View class →
      </Link>
    )}
  </div>
)
```

---

## Fix 5 — Fix `buildNextSteps` and "What's waiting for you"

### API calls for `useStudentDashboard`

```
GET /api/v1/students/me/study-plans?status=ACTIVE,IN_PROGRESS&limit=10
Authorization: Bearer {access_token}

Response 200:
[
  {
    "id": "uuid",
    "title": "Algebra — Linear Equations",
    "subject_name": "Mathematics",
    "status": "ACTIVE"     // "ACTIVE" | "IN_PROGRESS" | "COMPLETED"
  }
]

────────────────────────────────────────────────────────────

GET /api/v1/classes/{classId}/assessments?status=ACTIVE&limit=5
Authorization: Bearer {access_token}
(call for first enrolled classId — one call sufficient for dashboard)

Response 200:
[
  {
    "id": "uuid",
    "title": "Algebra Diagnostic",
    "subject_name": "Mathematics",
    "status": "ACTIVE",
    "due_date": "2026-04-05T23:59:59Z"   ← null for open-ended diagnostics
  }
]
```

### Next step card typography — from Typography Reference table

```tsx
// NextStepCard.tsx — verify these classes are correct, update if not
<div className="bg-white border border-role-student-border rounded-2xl p-4
                flex items-center justify-between">
  <div className="flex items-center gap-3">
    <span className="text-sm" aria-hidden="true">{emoji}</span>   {/* emoji icon */}
    <div>
      <div className="font-sans font-semibold text-sm text-brand-ink">{title}</div>
      <div className="font-sans text-xs text-brand-muted mt-0.5">{subtitle}</div>
    </div>
  </div>
  <Link to={actionRoute} className="font-sans font-bold text-xs text-brand-primary whitespace-nowrap ml-4">
    {actionLabel}
  </Link>
</div>
```

### Updated `buildNextSteps`

```typescript
interface NextStep {
  id: string
  emoji: string
  title: string
  subtitle: string
  actionLabel: string
  actionRoute: string
}

function buildNextSteps(
  assessments:       Array<{ id: string; subjectName: string; dueDate?: string | null }>,
  activeStudyPlans:  Array<{ id: string }>,
  inProgressPlans:   Array<{ id: string }>,
  subjectScores:     Array<{ subjectName: string; avgMastery: number | null }>
): NextStep[] {
  const steps: NextStep[] = []

  // Priority 1 — assessments due within 7 days
  const dueSoon = assessments.filter(a => {
    if (!a.dueDate) return false
    const days = (new Date(a.dueDate).getTime() - Date.now()) / 86_400_000
    return days >= 0 && days <= 7
  })
  if (dueSoon.length > 0) {
    steps.push({
      id:          `assessment-${dueSoon[0].id}`,
      emoji:       '📝',
      title:       `${dueSoon.length} assessment${dueSoon.length > 1 ? 's' : ''} due · ${dueSoon[0].subjectName}`,
      subtitle:    'Due within 7 days',
      actionLabel: 'Start now →',
      actionRoute: `/student/assessments/${dueSoon[0].id}/take`,
    })
  }

  // Priority 2 — ACTIVE study plans
  if (activeStudyPlans.length > 0 && steps.length < 3) {
    steps.push({
      id:          'study-plans-active',
      emoji:       '📚',
      title:       `${activeStudyPlans.length} study plan${activeStudyPlans.length > 1 ? 's' : ''} ready`,
      subtitle:    'Assigned by your teacher',
      actionLabel: 'View plans →',
      actionRoute: '/student/study-plans',
    })
  }

  // Priority 3 — IN_PROGRESS study plans
  if (inProgressPlans.length > 0 && steps.length < 3) {
    steps.push({
      id:          'study-plans-progress',
      emoji:       '📚',
      title:       'Continue your study plan',
      subtitle:    `${inProgressPlans.length} plan${inProgressPlans.length > 1 ? 's' : ''} in progress`,
      actionLabel: 'Continue →',
      actionRoute: '/student/study-plans',
    })
  }

  // Priority 4 — weakest subject (only when no active study plans)
  if (steps.length < 3 && activeStudyPlans.length === 0) {
    const assessed = subjectScores.filter(s => s.avgMastery !== null)
    if (assessed.length > 0) {
      const weakest = assessed.reduce((a, b) =>
        (a.avgMastery ?? 1) < (b.avgMastery ?? 1) ? a : b
      )
      if ((weakest.avgMastery ?? 1) < 0.7) {
        steps.push({
          id:          `weakest-${weakest.subjectName}`,
          emoji:       '📈',
          title:       `Your weakest area: ${weakest.subjectName}`,
          subtitle:    `${Math.round((weakest.avgMastery ?? 0) * 100)}% — keep going`,
          actionLabel: 'View progress →',
          actionRoute: '/student/my-progress',
        })
      }
    }
  }

  return steps.slice(0, 3)
}
```

---

## Fix 6 — CREATE `GET /students/me/classes` endpoint (backend)

⚠️ `GET /api/v1/students/me/classes` **does not exist** in the live API.
This endpoint must be created from scratch. It is the data source for the
sidebar CLASSES section, the class card grid, and the subject score cards.

### `backend/app/schemas/school.py` — add `StudentClassResponse`

```python
class StudentClassResponse(BaseModel):
    """Response schema for GET /students/me/classes.

    Enriched class response for the student dashboard. Includes
    enrollment-specific fields (diagnostic status, attempt ID, subject_id)
    that the standard ClassResponse does not carry.
    """
    id: uuid.UUID
    name: str                         # "Mathematics 9B"
    subject_id: uuid.UUID             # needed by frontend to call /students/me/gap-map?subject_id=
    subject_name: str                 # "Mathematics"
    grade_name: str                   # "Grade 9"
    teacher_name: str                 # "Ms. Ravi" (first_name + last_name)
    curriculum_id: uuid.UUID
    academic_year: str
    is_active: bool
    onboarding_diagnostic_status: str         # "PENDING" | "IN_PROGRESS" | "COMPLETED"
    diagnostic_attempt_id: uuid.UUID | None   # null if Celery task hasn't run yet
```

### `backend/app/api/v1/routes/students.py` — create new route

Add the following route. Read `docs/tasks/M0-10-T7_addendum2_student_classes.md`
for the intended query structure — the SQL pattern is already specified there:

```python
from app.schemas.school import StudentClassResponse

@router.get("/me/classes", response_model=list[StudentClassResponse])
async def get_my_classes(
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> list[StudentClassResponse]:
    """Return all classes the authenticated student is enrolled in.

    Returns classes ordered alphabetically by name. Active enrollments only.
    Includes onboarding_diagnostic_status per enrollment and the Tier 1
    diagnostic_attempt_id (null if Celery task has not yet run).
    """
    results = await db.execute(
        select(
            Class.id,
            Class.name,
            Class.curriculum_id,
            Class.academic_year,
            Class.is_active,
            Subject.id.label("subject_id"),
            Subject.name.label("subject_name"),
            Grade.name.label("grade_name"),
            (User.first_name + " " + User.last_name).label("teacher_name"),
            ClassEnrollment.onboarding_diagnostic_status,
            StudentAttempt.id.label("diagnostic_attempt_id"),
        )
        .join(ClassEnrollment, ClassEnrollment.class_id == Class.id)
        .join(Subject, Subject.id == Class.subject_id)
        .join(Grade, Grade.id == Class.grade_id)
        .join(User, User.id == Class.teacher_id)
        .outerjoin(
            Assessment,
            (Assessment.class_id == Class.id)
            & (Assessment.is_system_generated.is_(True))
            & (Assessment.status == "ACTIVE"),
        )
        .outerjoin(
            StudentAttempt,
            (StudentAttempt.assessment_id == Assessment.id)
            & (StudentAttempt.student_id == current_user.id),
        )
        .where(
            ClassEnrollment.student_id == current_user.id,
            ClassEnrollment.is_active.is_(True),
            Class.is_active.is_(True),
        )
        .order_by(Class.name)
    )

    return [
        StudentClassResponse(
            id=row.id,
            name=row.name,
            subject_id=row.subject_id,
            subject_name=row.subject_name,
            grade_name=row.grade_name,
            teacher_name=row.teacher_name,
            curriculum_id=row.curriculum_id,
            academic_year=row.academic_year,
            is_active=row.is_active,
            onboarding_diagnostic_status=row.onboarding_diagnostic_status,
            diagnostic_attempt_id=row.diagnostic_attempt_id,
        )
        for row in results.all()
    ]
```

---

## Files to Modify / Create

```
packages/ui/src/layouts/StudentLayout.tsx               MODIFY — full rewrite (Fix 1)
packages/ui/src/layouts/index.ts                        MODIFY — export StudentClass, StudentNavItem

frontend/apps/student/src/pages/dashboard/StudentDashboard.tsx      MODIFY (Fix 2)
frontend/apps/student/src/pages/dashboard/SubjectScoresSection.tsx   CREATE (Fix 3)
frontend/apps/student/src/components/ClassCard.tsx                   MODIFY (Fix 4)
frontend/apps/student/src/hooks/useStudentInfo.ts                    CREATE — GET /students/me/info
frontend/apps/student/src/hooks/useMyClasses.ts                      CREATE — GET /students/me/classes
frontend/apps/student/src/hooks/useStudentDashboard.ts               MODIFY (Fix 5)

backend/app/schemas/school.py                           MODIFY — add StudentClassResponse (Fix 6)
backend/app/api/v1/routes/students.py                   MODIFY — add GET /students/me/classes (Fix 6)
```

---

## Acceptance Criteria

### Named tests — `student-dashboard-patch.spec.ts`

`test_sidebar_renders_learn_nav_four_items_no_bottom_nav`
Assert: "Home", "My progress", "Study plans", "Assessments" in sidebar. No `<nav>` bottom element.

`test_sidebar_home_active_state`
`activeNav="home"` → Home item has `bg-[#f0fdf4]` and `text-brand-primary`. Green dot present.
Other three items do NOT have `bg-[#f0fdf4]`.

`test_topnav_shows_greeting_and_grade`
`studentName="Jane Doe"`, `gradeName="Grade 9"`, `curriculumName="Cambridge IGCSE"`.
Assert: Top nav left contains greeting text with "Jane". "Grade 9 · Cambridge IGCSE" visible in top nav.
Assert: These strings are inside the `<header>` element, not inside `<main>`.

`test_sidebar_locked_class_amber_text_routes_to_attempt`
`diagnosticStatus: "IN_PROGRESS"`, `diagnosticAttemptId: "abc-123"`.
Assert: Class name text has `text-brand-gold`. Lock icon present.
Link href is `/student/assessments/abc-123/take`.

`test_sidebar_locked_class_no_attempt_routes_to_diagnostic`
`diagnosticAttemptId: null`, `id: "c1"`.
Assert: Link href is `/student/classes/c1/diagnostic`.

`test_profile_card_click_navigates_to_settings`
Act: Click profile card button. Assert: `navigate` called with `/student/settings`.

`test_logout_button_calls_onlogout_not_navigate`
Act: Click Logout button. Assert: `onLogout` called. `navigate` NOT called.

`test_subject_score_card_uses_text_2xl_for_score`
Mock gap-map avg = 0.72.
Assert: Score element has Tailwind class `text-2xl` (not `text-[20px]` or `text-[11px]`).
Assert: Score text is "72%".

`test_subject_score_card_uses_text_xs_for_labels`
Assert: Subject name element has `text-xs`. Band label element has `text-xs`.
Neither has `text-[9px]`.

`test_class_card_uses_text_sm_for_name`
Mock `name: "Mathematics 9B"`. Assert: Name element has class `text-sm`.
Text "Mathematics 9B" visible. "Hi there" NOT in DOM.

`test_class_card_uses_text_xs_for_meta`
Mock `teacher_name: "Ms. Ravi"`. Assert: Meta element has `text-xs`.
"Ms. Ravi" visible. "Your Teacher" NOT in DOM.

`test_what_is_waiting_always_visible_when_empty`
Mock all data to empty. Assert: Section heading visible. `EmptyNextSteps` content visible.

`test_next_step_card_uses_text_sm_for_title_text_xs_for_subtitle`
Build a step. Assert: Title element has `text-sm`. Subtitle element has `text-xs`.

`test_weakest_subject_step_appears_when_no_study_plans`
Mock Physics gap-map avg = 0.32. Zero active study plans.
Assert: Next step card with "Physics" in title visible.

`test_backend_get_my_classes_creates_new_endpoint` — `test_student_classes.py`
Enroll student in one class. Subject UUID known from seed.
`GET /api/v1/students/me/classes` with student JWT.
Assert: HTTP 200. Response is a list. Item `subject_id` equals seeded subject UUID —
not null, not the string "Mathematics", valid UUID format.
Assert: Item `teacher_name` is a non-empty string (not a UUID).
Assert: Same call with teacher JWT → HTTP 403.
Assert: Same call with school_admin JWT → HTTP 403.

`test_backend_get_my_info_returns_name_and_grade` — `test_students.py`
Authenticate as a student with known first_name "Jane", grade "Grade 9".
`GET /api/v1/students/me/info`.
Assert: HTTP 200. `first_name` = "Jane". `grade_name` = "Grade 9".
`curriculum_name` is a non-empty string.

---

## Branch and commit

```
Branch: M0-7-T3-patch/fix-student-dashboard-complete

Commit:
fix(student): complete dashboard gap fix — sidebar, typography, subjects, class data

- Rewrite StudentLayout: left sidebar per DESIGN_SYSTEM.md v2.1 §5.4
- Top nav shows greeting (font-sans text-[13px]) and subtitle (text-[10px])
- Remove greeting from page content — it lives in top nav only
- Fix all page content fonts to rem-based Tailwind type scale:
    score values → text-2xl, labels → text-xs, card names → text-sm
- Sidebar chrome retains explicit pixel sizes per design spec
- Create GET /students/me/classes backend endpoint (was missing from live API)
- Add StudentClassResponse schema with subject_id, teacher_name, diagnostic fields
- Add useStudentInfo hook — GET /students/me/info for name/grade/curriculum
- Add useMyClasses hook — GET /students/me/classes for sidebar + class grid
- Create SubjectScoresSection with per-subject gap-map queries
- Fix ClassCard: use className/teacherName from API response, never hardcoded
- Fix locked card routing: diagnostic_attempt_id → /assessments/:id/take
- Always render "What's waiting for you" — EmptyNextSteps when empty
- buildNextSteps: add weakest-subject priority step from resolved subject scores

Closes: student dashboard gap audit 2026-03-30
```
