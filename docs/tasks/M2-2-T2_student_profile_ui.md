# M2-2-T2 — Student Profile Page UI (Teacher App)
**Milestone:** M2 · **Epic:** M2-2 · **Task:** T2
**Depends on:** M2-2-T1 (my students list — entry point), M2-1-T2 (student gap map routes), M2-1-T3 (gap map side panel — "View full profile →" links here)
**Blocks:** Nothing — final task of M2-2 epic
**Estimated effort:** 4–5 hours

---

## Context

All code in this task lives in `frontend/apps/teacher`. No code goes in any other app.

Read `docs/design/DESIGN_SYSTEM.md` §5.3 (Teacher) before writing any component.
Gold is the action color. Green is mastery data only — never green buttons.

This page is the full teacher view of a single student. It is reached from two
entry points:
1. "View profile →" link in `MyStudentsPage` (`M2-2-T1`)
2. "View full profile →" button in `StudentSidePanel` on the gap map (`M2-1-T3`)

It is a read-only page for teachers. Teachers cannot edit any student data here.

---

## User Story

As a teacher, I want to see a single student's full gap profile, learning style, and
study plan history so I can understand where they are struggling and what support has
already been assigned.

---

## Files to Create

```
frontend/apps/teacher/src/pages/students/
  StudentProfilePage.tsx         ← page shell

frontend/apps/teacher/src/components/students/
  StudentGapProfileTab.tsx       ← subject-tabbed subtopic mastery list
  StudentLearningProfileCard.tsx ← modality bars + work style + interests
  StudentStudyPlanHistory.tsx    ← list of assigned plans with status

frontend/apps/teacher/src/hooks/
  useStudentProfile.ts           ← React Query hooks for student profile data

frontend/apps/teacher/src/tests/
  student-profile.spec.ts        ← Playwright E2E tests
```

---

## Route

`/teacher/students/:studentId` — `StudentProfilePage`.
Protected by `PrivateRoute` + `RoleRoute(['TEACHER', 'SCHOOL_ADMIN', 'KAIHLE_ADMIN'])`.

Back navigation: breadcrumb shows origin context:
- Came from gap map side panel → "← Gap map"
- Came from students list → "← My students"
Use `history.back()` for simplicity — do not attempt to reconstruct origin route.

---

## Complete List of API Calls This UI Makes

`GET /api/v1/students/{studentId}/gap-map?subject_id={subjectId}` — called via
`useStudentGapMap(studentId, subjectId)`. Called on mount and on subject tab change.

`GET /api/v1/onboarding/learning-profile?student_id={studentId}` — called once on
mount. Returns full `StudentLearningProfileResponse` including `modality_scores`,
`work_style`, `interests`, `completed_at`.

`GET /api/v1/students/{studentId}/study-plans` — called once on mount. Returns
`Page[StudyPlanResponse]` for all plans assigned to this student, any status.

Those are the only three API calls. Do not call assessment or class endpoints here.

---

## Page Layout

Three regions: header card (full width) → two-column content (gap profile left,
learning profile + study plan history right).

```
┌───────────────────────────────────────────────────────────────┐
│  ← Back  |  Aisha Rahman — Student profile         [read only]│
├───────────────────────────────────────────────────────────────┤
│  Student header card (full width)                             │
│  name · grade · class · curriculum · enrolled date           │
├─────────────────────────────────┬─────────────────────────────┤
│  Gap profile (left)             │  Right column               │
│  Subject tabs                   │  Learning profile card      │
│  Expandable topic groups        │  Study plan history         │
│  Subtopic mastery circles       │                             │
└─────────────────────────────────┴─────────────────────────────┘
```

Grid: `grid-cols-[1.2fr_1fr]` gap-14. On mobile (md:): stack vertically.

---

## Student Header Card

```tsx
<div className="bg-white border border-role-teacher-border rounded-2xl p-5 flex items-center gap-5">
  {/* Avatar initials circle */}
  {/* Name (font-display font-bold text-xl) */}
  {/* Grade · Class · Curriculum (muted meta) */}
  {/* Enrolled date */}
  {/* Overall mastery ring (small, 48px) */}
</div>
```

Avatar: initials from `first_name[0] + last_name[0]`, `bg-brand-primary text-white`.
Overall mastery: aggregate average across all subjects from gap map response.
If no assessments yet: ring is gray, "No assessments yet" label.

---

## Gap Profile Tab (`StudentGapProfileTab.tsx`)

Subject tabs across the top of the left column.
Below tabs: expandable topic groups, each with subtopic rows.

This reuses the same visual pattern as the student's own My Progress page
(`M2-1-T4`) but reads from `GET /students/{id}/gap-map` (teacher endpoint)
rather than the `/me` shortcut.

```typescript
interface StudentGapProfileTabProps {
  studentId: string
  subjectId: string
  onSubjectChange: (subjectId: string) => void
}
```

Subtopic row: mastery circle (SVG, `getMasteryStyle`) + subtopic name +
last assessed date + band badge. Identical to `SubtopicProgressRow` in the
student app but lives in `apps/teacher` — do not import across apps.

Empty state (no assessments): "No assessment data yet for this subject.
Students will appear here after completing their first diagnostic."

---

## Learning Profile Card (`StudentLearningProfileCard.tsx`)

```tsx
<div className="bg-white border border-role-teacher-border rounded-2xl p-5">
  <SectionLabel>Learning profile</SectionLabel>

  {/* Modality bars — 4 bars */}
  {/* Work style preferences — 2-col grid of boolean badges */}
  {/* Interests — pill tags */}
  {/* Completed date or "Not yet completed" */}
</div>
```

**Modality bars:**
```
Kinesthetic  [████████░░]  80%   ← dominant (show gold #c9932a, matching lesson plan)
Visual       [█████░░░░░]  55%
Reading      [███░░░░░░░]  30%
Auditory     [██░░░░░░░░]  20%
```
Dominant modality bar uses gold `#c9932a`. Others use `#9ca3af`.
Dominant = `argmax(modality_scores)`.

**Work style** (from `work_style` JSONB):

```
Prefers:  Solo study      Short sessions   Task-based
```
Show as small badge pills. True values shown in `bg-brand-light text-brand-primary`,
false values omitted (show only what is true — "Prefers solo" not "Does not prefer group").

**Interests:** pill tags `bg-gray-100 text-gray-700 rounded-full`.

If `completed_at = null`: show single muted message "Learning profile not yet completed."
Do not show empty bars — hide the entire modality section.

This is read-only. Teachers cannot edit the student's learning profile.

---

## Study Plan History (`StudentStudyPlanHistory.tsx`)

```tsx
<div className="bg-white border border-role-teacher-border rounded-2xl p-5">
  <SectionLabel>Study plans</SectionLabel>
  {/* List of assigned plans */}
</div>
```

One row per plan, showing:
- Subtopic name + subject (from `study_plan.subtopic_name`)
- Status badge: GENERATING (amber pulse) / ACTIVE (green) / COMPLETED (gray tick)
- Quiz score if COMPLETED: "Quiz: 80%"
- Assigned date: "Assigned 12 Mar 2026"

Sort: ACTIVE first, GENERATING second, COMPLETED last. Within COMPLETED, most recent first.

Empty state: "No study plans assigned yet. Assign plans from the Gap Map →"
The "Gap Map →" text is a link to `/teacher/classes/{classId}/gap-map`.
`classId` comes from the student's enrollment in this teacher's class — use the
first match if enrolled in multiple of the teacher's classes.

---

## Acceptance Criteria

**Playwright E2E tests in `student-profile.spec.ts`**

`test_profile_page_when_loaded_then_header_shows_student_name` — Navigate to
`/teacher/students/{studentId}`. Assert the student's name is visible in the header.

`test_profile_page_when_learning_profile_complete_then_modality_bars_visible` — Mock
a completed learning profile. Assert four labelled bars are visible in the learning
profile card.

`test_profile_page_when_learning_profile_incomplete_then_not_yet_completed_message` —
Mock `completed_at=null`. Assert "Learning profile not yet completed." message is
visible and no bars are shown.

`test_profile_page_when_subject_tab_changed_then_gap_data_updates` — Click the
Science tab. Assert a new API call is made for the Science subject ID.

`test_profile_page_when_study_plan_completed_then_quiz_score_shown` — Mock a
COMPLETED plan with `quiz_score=0.8`. Assert "Quiz: 80%" text is visible.

`test_profile_page_when_no_study_plans_then_empty_state_shown` — Mock empty study
plans response. Assert the empty state message with "Assign plans from the Gap Map →"
link is visible.

`test_profile_page_when_gap_map_null_score_then_dash_shown` — Mock a subtopic with
`mastery_score=null`. Assert "–" appears inside that subtopic's circle.

**Jest unit tests**

`test_learning_profile_card_when_kinesthetic_dominant_then_bar_uses_gold` — Render
card with `kinesthetic: 0.8, visual: 0.5`. Assert the kinesthetic bar has the gold
color class.

`test_learning_profile_card_when_prefers_solo_true_then_badge_shown` — Render with
`work_style.prefers_solo=true`. Assert "Solo study" badge is visible.

`test_learning_profile_card_when_prefers_solo_false_then_no_badge` — `prefers_solo=false`.
Assert "Solo study" badge is NOT visible.

---

## Do NOT Touch

`frontend/apps/student/` — no code goes here.
`frontend/apps/school-admin/` — no code goes here.
`frontend/packages/ui/` — do not add teacher-specific profile components here.
Any backend file.
