# M2-2-T2 — Student Profile Page UI
**Milestone:** M2 · **Epic:** M2-2
**Authors:** Kramer (engineering) · Pixel (design) · Vidhya (education)
**Depends on:** M2-2-T1 (roster), M2-1-T2 (gap map routes), M3-2-T2 (study plan routes)
**Effort:** 4–5 hours

---

## Vidhya — Educational Context

**The student profile is the richest teaching tool in the entire platform.**

A well-designed student profile replaces the informal mental model every experienced teacher carries about each student — "Emma is strong in algebra but struggles with data interpretation, she's a visual learner and interested in football, she's been active lately." Making that model visible and structured means teachers can act on it systematically rather than relying on memory.

**The four-tab structure maps to how teachers think about a student:**

1. **Gap Map tab** — *"Where are they now?"* — The current mastery picture. This is a read-only view. The teacher can see the gaps but cannot assign a study plan from this page (that action belongs on the main class gap map where they have full context). Do not add an assign button here — it would fragment the workflow.

2. **Learning Profile tab** — *"How do they learn?"* — The modality breakdown and interests. A teacher preparing a lesson for Emma will glance at this and remember to include a visual component and use football analogies in the maths problems. Display dominant modality prominently. Show all four bars for completeness, but make the dominant one clearly stand out.

3. **Study Plans tab** — *"What have we tried?"* — History of assigned study plans and their outcomes. A teacher who is about to assign another study plan should first check if Emma already has an active one or recently completed one covering the same subtopic. Show this history clearly. If a plan was completed and Emma's quiz score was still low, that's important context for the teacher's next decision.

4. **Assessments tab** — *"How has performance trended?"* — Score history over time. A single low score is data; a pattern of improving scores despite starting low is a success story. Show assessment type, date, and score together so the teacher can read a trend.

**What this page is NOT:** It is not the student's own view of themselves. The teacher sees things the student doesn't — correct answers in the question breakdown, the full gap map with all scores, historical study plan details. This is the teacher's professional view.

**Dominant modality in gold.** On the teacher-facing learning profile view, the dominant modality bar renders in `bg-brand-gold` (`#c9932a`) — the teacher's action colour. This reinforces: "this is information you should act on." All other bars render in `bg-gray-200`. This is the opposite of the student settings page where all bars use the student's green scheme.

---

## Pixel — Design Spec

### Page layout

```
Header section (bg-white border-b border-gray-100):
  ← Back to students  |  Emma Rodriguez  |  [Grade 9] [Maths 9B] [Science 9A]
  Avatar (large, w-16 h-16) | Learning style tag | Interest pills

Subject mastery cards (grid-cols-3 md:grid-cols-3 gap-4 p-6):
  Read-only mini-cards, no links, no CTAs

Tab nav (sticky, bg-white border-b):
  [Gap Map] [Learning Profile] [Study Plans] [Assessments]

Tab content:
  Scrollable below sticky tab nav
```

### Component: StudentProfileHeader

```
Component: StudentProfileHeader
──────────────────────────────────────────────────────────
Avatar:     w-16 h-16 rounded-full bg-brand-light text-brand-primary
            font-fraunces text-2xl — initials

Name:       font-fraunces text-2xl text-ink
Grade:      bg-gray-100 text-gray-600 rounded-full px-2.5 py-1 text-xs font-medium
Class tags: bg-gray-100 text-gray-600 rounded-full px-2.5 py-1 text-xs
            One per enrolled class — truncate class name to 20 chars with tooltip

Learning style row (below name):
  Dominant modality pill: bg-amber-50 text-amber-700 (gold context — teacher view)
  icon + "Visual learner" or "Hands-on learner" etc.
  Interest pills: up to 4 shown, "+ N more" if there are more
    bg-gray-100 text-gray-600 text-xs rounded-full px-2 py-0.5

If profile null: "Learning profile not completed" — text-gray-400 text-sm italic
──────────────────────────────────────────────────────────
Back link:  ← Back to My Students  — text-brand-gold text-sm, top-left
```

### Component: SubjectMasteryCards (read-only)

```
Component: SubjectMasteryCards
──────────────────────────────────────────────────────────
Cards:      grid-cols-3 gap-4 (no horizontal scroll — max 3 subjects in v1)
Card:       bg-white rounded-xl border-l-4 border border-gray-100 p-4
            Left border color from getMasteryStyle(score).borderClass
Subject:    font-fraunces text-sm font-semibold text-ink
Score:      text-2xl font-fraunces color from getMasteryStyle(score).textClass
Band:       font-nunito text-xs text-gray-400 mt-0.5
──────────────────────────────────────────────────────────
CRITICAL: No links. No "View gap map →". No CTAs whatsoever.
This is read-only display. (Vidhya: teacher is here to understand, not act)
score=null: "—" in text-gray-400, "Not assessed" sub text
```

### Tabs (sticky)

```
Tab nav:    position sticky top-0 z-10 bg-white border-b border-gray-100
Tab item:   px-4 py-3 text-sm font-nunito font-medium
Active:     border-b-2 border-brand-gold text-brand-gold (gold underline)
Inactive:   text-gray-500 hover:text-gray-700 transition-colors
```

### Tab 1 — Gap Map

Simple list view (NOT the heatmap grid — too dense for a profile page):

```
Subject tabs → pill toggle: [Mathematics] [Science] [English]
  Active: bg-brand-light text-brand-primary border border-brand-primary

Topic group header:
  Topic name — font-fraunces text-base text-ink + chevron + avg badge

Subtopic row:
  Mastery circle (24px SVG, stroke colour from band) | Subtopic name | "Last assessed {date}"
  score=null: gray circle + "—" + "Not yet assessed"
──────────────────────────────────────────────────────────
Banner at top of tab (Vidhya):
  "This view shows this student's gaps. To assign a study plan, use the
   class Gap Map and select this student's cell."
  bg-blue-50 border border-blue-100 text-blue-700 text-xs p-3 rounded-xl
  [Go to Gap Map →] link
```

### Tab 2 — Learning Profile

```
Modality bars (4 rows):
  Bar container: flex items-center gap-3 py-2
  Label: font-nunito text-sm w-32 flex-shrink-0 text-gray-700
  Bar:   h-2.5 rounded-full flex-1
         Dominant: bg-brand-gold (teacher gold — Vidhya's requirement)
         Others:   bg-gray-200
  Pct:   font-nunito text-sm text-gray-500 w-10 text-right

Work style chips (2 × 2 grid):
  Each: rounded-xl border p-3 text-center
  Preferred option: bg-amber-50 border-amber-200 text-amber-700
  Other option:     bg-gray-50 border-gray-100 text-gray-400
  Label: text-xs font-nunito font-medium
  Examples:
    [Solo learner ✓]  [Group learner  ]
    [Short sessions ] [Long sessions ✓]

Interest pills: all interests shown (not just top 2)
  bg-gray-100 text-gray-700 rounded-full px-3 py-1 text-xs

Completed date: "Profile completed {date}" text-xs text-gray-400 mt-4
If null: "This student hasn't completed their learning profile yet."
```

### Tab 3 — Study Plans

```
Plan card:  bg-white rounded-xl border border-gray-100 p-4 mb-3
Header:     Subject dot (mastery colour) | Subtopic name (Fraunces)
            Status badge | Assigned {date}

Status badges:
  ACTIVE:      bg-green-50 text-green-700
  GENERATING:  bg-amber-50 text-amber-700 (+ pulsing dot)
  COMPLETED:   bg-gray-100 text-gray-500

Completed plan:  Quiz score pill (getMasteryStyle) + Completed {date}
                 "View plan →" ghost link — text-brand-gold text-sm

Empty state: "No study plans assigned yet. Assign from the class Gap Map
              when this student needs support on a specific subtopic."
  font-nunito text-sm text-gray-400 text-center py-12
```

### Tab 4 — Assessments

```
Attempt row:  flex items-center gap-4 py-4 border-b border-gray-50
Type badge:   (same as assessment results page — purple/blue/orange/gray)
Name:         font-fraunces text-sm text-ink
Date:         font-nunito text-xs text-gray-400
Score:        getMasteryStyle pill
"View answers →": text-brand-gold text-sm (→ assessment results student detail)

Empty state:  "No assessments taken yet."
```

---

## Kramer — Engineering Spec

### Files

```
frontend/apps/teacher/src/pages/students/
  StudentProfilePage.tsx

frontend/apps/teacher/src/components/students/
  StudentProfileHeader.tsx
  SubjectMasteryCards.tsx
  StudentGapMapTab.tsx
  LearningProfileTab.tsx
  StudyPlanHistoryTab.tsx
  AssessmentHistoryTab.tsx

frontend/apps/teacher/src/hooks/
  useStudentProfile.ts

frontend/apps/teacher/src/tests/
  student-profile.spec.ts
  subject-mastery-cards.test.tsx
  learning-profile-tab.test.tsx
```

### Route

`/teacher/students/:studentId` → `StudentProfilePage.tsx`

### React Query

```typescript
export function useStudentProfile(studentId: string) {
  return {
    student:        useQuery({ queryKey: ['student', studentId], ... }),
    gapMap:         useQuery({ queryKey: ['student-gap-map', studentId], ... }),
    learningProfile:useQuery({ queryKey: ['learning-profile', studentId], ... }),
    studyPlans:     useQuery({ queryKey: ['student-study-plans', studentId], ... }),
    attempts:       useQuery({ queryKey: ['student-attempts', studentId], ... }),
  }
}
```

### API Calls

| Data | Endpoint |
|---|---|
| Student | `GET /api/v1/schools/{id}/users/{studentId}` |
| Gap map | `GET /api/v1/students/{studentId}/gap-map` |
| Learning profile | `GET /api/v1/students/{studentId}/learning-profile` |
| Study plans | `GET /api/v1/students/{studentId}/study-plans` |
| Assessment history | Derived from attempts listing |

---

## Playwright E2E + Jest Unit Tests

```typescript
// E2E
test('profile_header_shows_name_grade_classes', ...)
test('profile_header_shows_modality_in_gold_pill', ...)          // Vidhya + Pixel
test('profile_gap_map_tab_has_reroute_banner_not_assign_button',...)// Vidhya
test('profile_learning_profile_dominant_bar_uses_gold', ...)     // Vidhya + Pixel
test('profile_study_plans_empty_state_has_guidance', ...)        // Vidhya
test('profile_assessments_view_answers_link_present', ...)
test('profile_null_mastery_shows_dash_not_zero', ...)            // Vidhya
test('profile_back_link_returns_to_roster', ...)

// Unit
describe('SubjectMasteryCards', () => {
  it('no links or CTAs rendered (read-only)', ...)               // Vidhya + Pixel
  it('null score shows dash not zero', ...)                      // Vidhya
  it('left border colour from mastery band', ...)                // Pixel
})

describe('LearningProfileTab', () => {
  it('dominant modality bar uses bg-brand-gold', ...)            // Vidhya + Pixel
  it('non-dominant bars use bg-gray-200', ...)                   // Pixel
  it('preferred work style chip highlighted amber', ...)         // Pixel
})
```

---

## Acceptance Criteria

- [ ] Header shows name, grade, class tags, modality pill in gold (Pixel + Vidhya)
- [ ] Gap Map tab has reroute banner — no assign button on this page (Vidhya)
- [ ] Learning Profile dominant bar renders in `bg-brand-gold` not green (Vidhya + Pixel)
- [ ] Work style chips: preferred highlighted, others muted (Pixel)
- [ ] Subject mastery cards: read-only, no links, no CTAs (Vidhya + Pixel)
- [ ] `score=null` → "—" everywhere, never "0%" (Vidhya)
- [ ] Study plan history shows quiz scores and completion status (Vidhya)
- [ ] Assessment history "View answers →" links work (Kramer)
- [ ] No green action buttons (Teacher design spec)
- [ ] All tabs keyboard navigable (Pixel)
