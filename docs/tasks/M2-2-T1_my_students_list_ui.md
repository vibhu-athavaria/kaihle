# M2-2-T1 — My Students Class Roster UI
**Milestone:** M2 — Gap Map & Teacher Dashboard · **Epic:** M2-2
**Authors:** Kramer (engineering) · Pixel (design) · Vidhya (education)
**Depends on:** M2-1-T2 (gap map routes), M1-4-T1 (attempt routes)
**Blocks:** M2-2-T2 (student profile)
**Effort:** 3–4 hours

---

## Vidhya — Educational Context

**What teachers actually use a roster for:**

A class roster is not a gradebook. Teachers look at a roster to answer fast questions:
- Who hasn't been assessed yet? (Learning gap — can't assign a study plan without data)
- Who has a very different learning style from the rest of the class? (Instructional planning)
- Who was active this week and who has gone quiet? (Engagement signal)

The roster should surface those three signals without requiring the teacher to click into each student. Dense data tables fail teachers — the cognitive load of scanning 28 rows of numbers is too high during a lesson or planning period.

**Learning style tags matter educationally.** A teacher seeing "👁 Visual" next to a student's name will adapt their in-class support instinctively. This is called *differentiated instruction* — the best teachers do it naturally; a good tool makes it visible for the rest. The tag must show the dominant modality from the student's learning profile, not a generic label.

**Mastery "not yet assessed" is different from mastery 0%.** A student who hasn't taken any assessments yet has a null gap map. Displaying this as 0% is educationally misleading — it implies they attempted and failed, not that there's simply no data. Always use "—" for null. Teachers understand this distinction immediately.

**Sort order:** Default should be alphabetical by last name — that's how teachers think of their class. Unlike the assessment results page (lowest-first for instructional urgency), the roster is a reference view, not a triage view.

---

## Pixel — Design Spec

### Overall approach

This is a **reference table**, not a dashboard. The visual tone should be calm and scannable — white background, generous row height, restrained typography. Teachers will open this page mid-lesson to look up a student quickly. It must load fast and scan faster.

Avoid adding too many columns. Six columns is the maximum before the table becomes a horizontal scroll nightmare on laptops. Keep it to: Student · Mastery · Style · Last active · →

### Component: LearningStyleTag

```
Component: LearningStyleTag
──────────────────────────────────────────────────────────
Base:       inline-flex items-center gap-1.5 rounded-full
            px-2.5 py-1 text-xs font-medium
            bg-gray-100 text-gray-700

Variants (modality → icon + label):
  visual:          👁  "Visual"
  auditory:        👂  "Auditory"
  reading_writing: 📖  "Reader"
  kinesthetic:     🤲  "Hands-on"
  null:            "—" text-gray-400 (no pill, just a dash)
──────────────────────────────────────────────────────────
Note: Do not use brand colours for these tags. They are not
status indicators — they are descriptors. Gray keeps them
visually quiet next to the mastery badge which IS coloured.
──────────────────────────────────────────────────────────
Accessibility: aria-label="Learning style: {label}"
               Icon is presentational (aria-hidden="true")
```

### Component: StudentRosterTable

```
Component: StudentRosterTable
──────────────────────────────────────────────────────────
Table:      bg-white rounded-2xl border border-gray-100 overflow-hidden
Header:     bg-gray-50 border-b border-gray-100
            th: font-nunito text-[11px] uppercase tracking-wide
            text-gray-400 px-4 py-3
Row height: 60px — generous, prevents visual cramping
Row hover:  bg-gray-50 transition-colors duration-75 cursor-pointer
Last row:   no bottom border (no double border with card edge)
──────────────────────────────────────────────────────────
Avatar:     w-9 h-9 rounded-full bg-brand-light text-brand-primary
            font-fraunces text-sm flex-shrink-0
            Initials from first_name[0] + last_name[0]
Name:       font-fraunces text-sm font-semibold text-ink
Grade:      font-nunito text-xs text-gray-400 mt-0.5
──────────────────────────────────────────────────────────
Mastery:    getMasteryStyle(score).pill — coloured pill
            score=null: "—" text-gray-400 text-sm (Vidhya: not "0%")
──────────────────────────────────────────────────────────
Last active: "Today" / "2 days ago" / "1 week ago"
             Use date-fns formatDistanceToNow
             "—" if no activity yet
             > 2 weeks: text-amber-600 (soft urgency signal)
──────────────────────────────────────────────────────────
Arrow:      text-gray-300 →, group-hover:text-brand-gold transition-colors
──────────────────────────────────────────────────────────
Empty state:
  Illustration: simple empty classroom SVG or plain icon
  Heading: "No students enrolled yet" — font-fraunces text-lg
  Sub: "Ask your school admin to enrol students in this class."
  font-nunito text-sm text-gray-400 text-center py-16
──────────────────────────────────────────────────────────
Loading: Skeleton rows (5 rows) with animate-pulse
         Avatar circle + two text bars per row
```

### Search + Sort Bar

```
Layout: flex justify-between items-center mb-4
Search: flex-1 max-w-xs
        Input — rounded-xl border border-gray-200 px-4 py-2 text-sm
        Placeholder: "Search students..."
        Icon: 🔍 left-side, text-gray-400
Sort:   <select> rounded-xl border border-gray-200 px-3 py-2 text-sm text-gray-600
        Options:  Name A–Z (default) | Mastery ↑ | Mastery ↓ | Last active
```

---

## Kramer — Engineering Spec

### Files

```
frontend/apps/teacher/src/pages/students/
  MyStudentsPage.tsx

frontend/apps/teacher/src/components/students/
  StudentRosterTable.tsx
  StudentRosterRow.tsx
  LearningStyleTag.tsx

frontend/apps/teacher/src/hooks/
  useMyStudents.ts

frontend/apps/teacher/src/tests/
  my-students.spec.ts
  learning-style-tag.test.tsx
```

### Route

`/teacher/classes/:classId/students` → `MyStudentsPage.tsx`

### Data Strategy

Enrollment list from `GET /classes/{classId}/enrollments`. Then `useQueries` for mastery + learning profile per student (capped at 40 students per CONSTITUTION Rule — class size limit).

```typescript
export function useMyStudents(classId: string) {
  const enrollments = useQuery({
    queryKey: ['enrollments', classId],
    queryFn: () => apiClient.get(`/api/v1/classes/${classId}/enrollments`),
  })

  const studentIds = enrollments.data?.map(e => e.student_id) ?? []

  const profiles = useQueries({
    queries: studentIds.map(id => ({
      queryKey: ['student-learning-profile', id],
      queryFn: () => apiClient.get(`/api/v1/students/${id}/learning-profile`),
      staleTime: 5 * 60_000,
    })),
  })

  const masteryScores = useQueries({
    queries: studentIds.map(id => ({
      queryKey: ['student-gap-map-summary', id],
      queryFn: () => apiClient.get(`/api/v1/students/${id}/gap-map`),
      staleTime: 2 * 60_000,
      select: (data) => computeOverallMastery(data), // average across subjects
    })),
  })

  return { enrollments, profiles, masteryScores }
}
```

---

## Playwright E2E

```typescript
test('roster_loads_and_shows_student_rows', ...)
test('roster_avatar_shows_initials', ...)                  // Pixel
test('roster_null_mastery_shows_dash_not_zero', ...)       // Vidhya
test('roster_search_filters_by_name', ...)
test('roster_sort_alphabetical_by_default', ...)           // Vidhya
test('roster_sort_by_mastery_works', ...)
test('roster_stale_student_last_active_amber', ...)        // Pixel: > 2 weeks amber
test('roster_row_click_navigates_to_profile', ...)
test('roster_empty_state_when_no_enrollments', ...)        // Pixel
test('roster_loading_shows_skeleton_rows', ...)            // Pixel
test('roster_learning_style_tag_has_aria_label', ...)      // Pixel
test('roster_no_green_buttons', ...)                       // Teacher design spec
```

---

## Jest Unit Tests

```typescript
describe('LearningStyleTag', () => {
  it('visual: shows 👁 icon and "Visual" label', ...)
  it('auditory: shows 👂 icon and "Auditory" label', ...)
  it('reading_writing: shows 📖 icon and "Reader" label', ...)
  it('kinesthetic: shows 🤲 icon and "Hands-on" label', ...)
  it('null modality: renders "—" not a pill', ...)          // Vidhya: null ≠ 0
  it('icon is aria-hidden', ...)                            // Pixel
  it('has aria-label with modality name', ...)              // Pixel
})
```

---

## Acceptance Criteria

- [ ] Default sort alphabetical by last name (Vidhya — roster is a reference view)
- [ ] `score=null` renders "—" not "0%" anywhere on the page (Vidhya)
- [ ] Learning style tag shows correct icon + label per modality (Vidhya)
- [ ] `LearningStyleTag` null state renders "—" not empty pill (Vidhya)
- [ ] Avatar shows initials, not a broken image (Pixel)
- [ ] Last active > 2 weeks renders in amber (Pixel — soft urgency)
- [ ] Loading state shows skeleton rows, not blank table (Pixel)
- [ ] Empty state has heading + explanation, not a blank page (Pixel)
- [ ] Search filters client-side, no spinner on keypress (Pixel)
- [ ] All icons are `aria-hidden`, tags have `aria-label` (Pixel)
- [ ] Row click navigates to student profile page (Kramer)
- [ ] No green action buttons (Teacher design spec)
