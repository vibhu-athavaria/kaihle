# M4-1-T5 — Student Lesson Plan Preview UI (Teacher App)
**Milestone:** M4 · **Epic:** M4-1 · **Task:** T5
**Depends on:** M4-1-T4 (lesson plan detail page — Students tab links here), M2-1-T3 (learning profile available)
**Blocks:** Nothing — final task of M4-1 epic
**Estimated effort:** 3–4 hours

---

## Context

All code in this task lives in `frontend/apps/teacher`. No code goes in any other app.

Read `docs/design/DESIGN_SYSTEM.md` §5.3 (Teacher) before writing any component.
Gold is the action color. Green is mastery data only.

This page is reached from the "Students" tab on the Lesson Plan Detail page
(`M4-1-T4`). Each student row has a "Preview plan →" button that opens this page.
It is a teacher-facing read-only preview — the teacher sees exactly what lesson
experience this one student receives, with explicit AI personalisation rationale.

This is not a student-facing page. Students do not see this URL or this layout.

---

## User Story

As a teacher, I want to preview the personalised lesson plan experience for any
individual student in my class so I can verify the AI's personalisation decisions
and understand why each student is placed in their group.

---

## Files to Create

```
frontend/apps/teacher/src/pages/lesson-plans/
  StudentLessonPlanPreviewPage.tsx    ← page shell

frontend/apps/teacher/src/components/lesson-plans/
  PersonalisationCallout.tsx          ← amber banner explaining AI decisions
  PersonalisationRationale.tsx        ← sidebar: group, modality bars, interests
  StudentPlanSections.tsx             ← filtered lesson sections (student's group only)

frontend/apps/teacher/src/tests/
  student-lesson-plan-preview.spec.ts ← Playwright E2E tests
```

---

## Route

`/teacher/lesson-plans/:planId/student/:studentId` — `StudentLessonPlanPreviewPage`.
Protected by `PrivateRoute` + `RoleRoute(['TEACHER'])`.

Breadcrumb: `Lesson plans › Week of {date} › Students › {student_name}`

---

## Complete List of API Calls This UI Makes

`GET /api/v1/lesson-plans/{planId}` — called on mount via `useLessonPlan(planId)`
(hook already exists from M4-1-T4). Returns full plan including `generated_plan`
JSON with `student_groups` object containing group assignments.

`GET /api/v1/onboarding/learning-profile?student_id={studentId}` — called on mount
via the same hook used in M2-1-T3's `StudentSidePanel`. Returns `modality_scores`,
`work_style`, and `interests`.

Those are the only two API calls. The student's group assignment and personalisation
rationale are derived entirely from the plan's `generated_plan` JSON and the
learning profile — no additional endpoints needed.

---

## Page Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  Lesson plans › Week of 17 Mar › Students › Aisha Rahman        │
│                                            [Teacher preview — read only] │
├──────────────────────────────────────────────────────────────────┤
│  Student profile card (full width)                               │
│  name · class · group badge · modality tag · interest tags      │
│  weakest subtopics (from plan focus)                             │
├──────────────────────────────────────────────────────────────────┤
│  Personalisation callout (full width, amber)                     │
├──────────────────────────────────────┬───────────────────────────┤
│  Lesson sections (left)              │  Rationale sidebar (right)│
│  Starter (whole class)               │  Group placement          │
│  Main activity (this student only)   │  Modality bars            │
│  Plenary (whole class)               │  Focus subtopics          │
│  Homework (whole class)              │  Interests used           │
│                                      │  Prev/Next student nav    │
└──────────────────────────────────────┴───────────────────────────┘
```

Two-column grid: `grid-cols-[1fr_240px]`, `gap-14`. Stack on mobile.

---

## Student Profile Card (full width)

Initials avatar + name (Fraunces font-bold) + class + grade + curriculum meta.

Tag row (flex wrap):
- Group badge: A = `bg-amber-100 text-amber-700` · B = `bg-blue-50 text-blue-700` · C = `bg-green-50 text-green-700`
- Dominant modality tag: `bg-gray-100 text-gray-700` with emoji icon
- Interest tags: `bg-blue-50 text-blue-700` (top 3 from `interests[]`)
- Focus subtopic mastery tags: `bg-red-50 text-red-700` for Needs Work, `bg-amber-50 text-amber-700` for Developing

"Read only" badge in topbar right: `bg-gray-100 text-gray-500` pill with eye icon.

---

## Personalisation Callout (`PersonalisationCallout.tsx`)

Full-width amber card: `bg-amber-50 border border-amber-200 rounded-xl`.

Left: ✨ icon in `bg-amber-100` rounded square.

Right: "How this plan was personalised for {firstName}" (bold, amber-800) then
plain-language explanation constructed from the plan data:

```
"{firstName} is in Group {A/B/C} because their mastery on this week's focus
subtopics is {below 40% / between 40–70% / above 70%}. The plan gives them
{hands-on, physical activities / structured examples with visual scaffolds /
extension challenges} matched to their {dominant modality} learning style."
```

If interest injection was used in starter: "The starter uses a {interest} scenario
referencing their interests."

Build this string programmatically from plan data + profile — do not hardcode it.

---

## Lesson Sections (`StudentPlanSections.tsx`)

Show only the sections relevant to this student. DO NOT show other groups' activities.

Sections to show (in order):
1. **Starter** — whole class, from `lesson_structure.starter_10min`
2. **Main activity** — this student's group ONLY, from `lesson_structure.main_activity_30min.group_{A/B/C}`
3. **Plenary** — whole class, from `lesson_structure.plenary_10min`
4. **Homework** — whole class, from `lesson_structure.homework`

Each section is a card with:
- Phase dot (amber Starter, gold Main activity, green Plenary, indigo Homework)
- Section title + duration
- Badge: "Whole class" `bg-gray-100 text-gray-500` OR "Group {X} — {firstName}'s activity" `bg-amber-100 text-amber-700`
- Body text (from plan JSON)
- Personalisation highlight box (where applicable):
  - `border-l-[3px] border-brand-gold bg-amber-50 rounded-r-lg p-2 mt-2 text-xs text-amber-800`
  - Content: explain the specific personalisation (interest reference, modality framing, simplified exit ticket)

The student's group activity card has: `border-[1.5px] border-brand-gold` (gold border
distinguishing it from whole-class sections).

---

## Personalisation Rationale Sidebar (`PersonalisationRationale.tsx`)

Four stacked cards inside the 240px right column:

**1. Group placement**
- Group letter badge
- One sentence: "Mastery below 40% on focus subtopics → Group A (foundational)"

**2. Learning modality**
- Section label "Learning style"
- 4 mini horizontal bars (Visual / Auditory / Reading / Kinesthetic)
- Dominant bar uses gold `#c9932a`. Others use `#9ca3af`.
- Percentages (from `modality_scores`, ×100)

**3. Focus subtopics**
- List of 2 focus subtopics with mastery % and band badge
- These are from `plan.focus_subtopic_ids` resolved against plan JSON names

**4. Interests used**
- Which interests were injected and where (starter / quiz scenarios)
- If no interests: "No interests on file"

**Student navigation** (bottom of sidebar):
```
← Prev student    1 of 28    Next student →
```
Navigation is client-side — receives ordered student list as a prop from the parent
plan detail page. No API call on prev/next. Show student number in the centre.

---

## Deriving group assignment

The student's group (A/B/C) is NOT stored as a field on the student record. It must
be derived from the lesson plan's `student_groups` object. The plan JSON contains
per-group student counts and focus descriptions, but NOT individual student-to-group
mappings directly.

Approach: use the student's mastery score for the focus subtopic to determine group:
- Score < 0.4 → Group A
- 0.4 ≤ score ≤ 0.7 → Group B
- Score > 0.7 → Group C
- Score null → Group A (same as `lesson_plan_service.py` clustering logic)

This mirrors the server-side clustering in `lesson_plan_tasks.py`. The teacher app
derives it client-side from the student's `gap_map` data.

---

## Acceptance Criteria

**Playwright E2E tests in `student-lesson-plan-preview.spec.ts`**

`test_preview_page_when_loaded_then_student_name_in_breadcrumb` — Navigate to the
preview URL. Assert the student's name appears in the breadcrumb trail.

`test_preview_page_when_loaded_then_only_one_group_activity_shown` — Assert exactly
one card with "Group X — {name}'s activity" badge is visible. Assert the other two
group activities are NOT in the DOM.

`test_preview_page_when_loaded_then_whole_class_sections_visible` — Assert Starter,
Plenary, and Homework sections are visible (all marked "Whole class").

`test_preview_page_when_group_a_student_then_group_a_badge_shown` — Mock a student
with mastery < 0.4. Assert the "Group A" badge is visible on the student profile card.

`test_preview_page_when_next_student_clicked_then_url_updates` — Click "Next student →".
Assert the URL changes to the next studentId in the sequence.

`test_preview_page_when_no_profile_then_modality_bars_hidden` — Mock a student with
`completed_at=null` learning profile. Assert modality bars are NOT rendered. Assert
"Learning profile not yet completed." appears in rationale sidebar.

`test_preview_page_read_only_badge_visible` — Assert the "Teacher preview — read only"
badge is visible in the topbar area.

**Jest unit tests**

`test_group_derivation_when_score_below_0_4_then_group_a` — Call group derivation
with `score=0.35`. Assert result is "A".

`test_group_derivation_when_score_0_4_exactly_then_group_b` — Boundary: assert "B".

`test_group_derivation_when_score_null_then_group_a` — Assert `null` → "A" (same
as server-side default).

`test_group_derivation_when_score_above_0_7_then_group_c` — Assert "C".

---

## Do NOT Touch

`frontend/apps/student/` — no code goes here.
`frontend/apps/school-admin/` — no code goes here.
`frontend/packages/ui/` — do not add lesson-plan-specific components here.
Any backend file — no new endpoints needed for this page.
