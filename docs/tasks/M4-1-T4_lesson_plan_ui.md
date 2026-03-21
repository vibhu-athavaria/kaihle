# M4-1-T4 — Lesson Plan Teacher UI (Teacher App)
**Milestone:** M4 · **Epic:** M4-1 · **Task:** T4
**Depends on:** M4-1-T3 (lesson plan routes return real data)
**Blocks:** Nothing — final task of M4
**Estimated effort:** 4–5 hours

---

## Context

All code in this task lives in `frontend/apps/teacher`. No code goes in any other app.

Read `docs/design/DESIGN_SYSTEM.md` §5.3 (Teacher) before writing anything. Action
buttons use gold (`brand-gold`). Green is reserved for mastery indicators.

The `useClassLessonPlans` hook already exists from M0-10-T9. It now returns real
data after M4-1-T3 completes. This task builds the presentation layer on top of it.

The "This Week" card placeholder on the teacher dashboard has been showing empty since
M0. After this task ships, it renders real plan data.

---

## User Story

As a teacher, I want to view my AI-generated weekly lesson plan, edit any section,
regenerate it if needed, and mark it as used so I can track which weeks I have planned.

---

## Files to Create / Modify

```
frontend/apps/teacher/src/pages/lesson-plans/
  LessonPlanListPage.tsx        ← list of all plans for a class
  LessonPlanDetailPage.tsx      ← single plan with editor
  components/
    LessonPlanCard.tsx          ← card shown in list and on dashboard
    LessonEditor.tsx            ← inline section editor
    StudentGroupPanel.tsx       ← shows A/B/C group activities

frontend/apps/teacher/src/hooks/
  useLessonPlanActions.ts       ← edit, regenerate, mark-used mutations

frontend/apps/teacher/src/tests/
  lesson-plans.spec.ts          ← Playwright E2E tests
  LessonEditor.test.tsx         ← Jest unit tests
```

Also update the teacher dashboard "This Week" card component (already exists as a
placeholder from M0-9-T2) to render a `LessonPlanCard` when a plan exists.

---

## Routes

`/teacher/classes/:classId/lesson-plans` — `LessonPlanListPage`. Protected by
`PrivateRoute` + `RoleRoute(['TEACHER'])`.

`/teacher/lesson-plans/:planId` — `LessonPlanDetailPage`. Same guards.

---

## Complete List of API Calls This UI Makes

`GET /api/v1/classes/{classId}/lesson-plans` — called by `useClassLessonPlans(classId)`
on the list page and for the dashboard "This Week" card (only fetches the latest plan).

`GET /api/v1/lesson-plans/{planId}` — called by a `useLessonPlan(planId)` query on
the detail page. Returns the merged view (teacher edits applied over generated plan).

`PATCH /api/v1/lesson-plans/{planId}` — called by `useLessonPlanActions.saveEdits`
when the teacher saves an edited section.

`POST /api/v1/lesson-plans/{planId}/regenerate` — called by
`useLessonPlanActions.regenerate`.

`PATCH /api/v1/lesson-plans/{planId}/status` — called by
`useLessonPlanActions.markUsed` and `markArchived`.

Those are the only API calls. Do not fetch student data separately — student group
counts come from the plan's `student_groups` object in the `generated_plan` JSON.

---

## `useLessonPlanActions.ts`

```typescript
export const useLessonPlanActions = (planId: string) => {
  const queryClient = useQueryClient()
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['teacher', 'lesson-plan', planId] })
  }

  const saveEdits = useMutation({
    mutationFn: (edits: Partial<LessonPlanEditFields>) =>
      apiClient.patch(`/lesson-plans/${planId}`, edits),
    onSuccess: invalidate,
  })

  const regenerate = useMutation({
    mutationFn: () => apiClient.post(`/lesson-plans/${planId}/regenerate`, {}),
    onSuccess: invalidate,
  })

  const markUsed = useMutation({
    mutationFn: () =>
      apiClient.patch(`/lesson-plans/${planId}/status`, { status: 'USED' }),
    onSuccess: invalidate,
  })

  const markArchived = useMutation({
    mutationFn: () =>
      apiClient.patch(`/lesson-plans/${planId}/status`, { status: 'ARCHIVED' }),
    onSuccess: invalidate,
  })

  return { saveEdits, regenerate, markUsed, markArchived }
}
```

---

## Lesson Plan List Page (`LessonPlanListPage.tsx`)

Shows all plans for a class, newest first. Each row shows the week start date, status
badge, and the two focus subtopic names from `generated_plan.focus_subtopic_ids` (resolved
to names from the plan JSON's `class_summary` or a separate lookup). The actions
column shows "View" always, "Mark as Used" for GENERATED/EDITED plans, and "Archive"
for any non-ARCHIVED plan.

The most recent GENERATED or EDITED plan is highlighted with a subtle gold border.
If it was generated in the last 24 hours, show a "New ✨" badge.

Empty state: "No lesson plans generated yet. Plans are generated automatically every
Monday morning. Check back on Monday!"

---

## Lesson Plan Detail Page (`LessonPlanDetailPage.tsx`)

The page has three visual regions: a header bar, a lesson structure area, and a
sidebar showing student groups.

**Header bar:** Plan week, subject, class name, status badge, and action buttons.
The action buttons are: "Edit" (toggles edit mode), "Regenerate" (with confirmation
modal), and "Mark as Used" (only for GENERATED/EDITED plans).

**Lesson structure area (`LessonEditor`):** Shows the five lesson sections as
expandable cards — Starter (10 min), Group A Activity, Group B Activity, Group C
Activity, Plenary (10 min), and Homework. In view mode, each card shows the activity
text. In edit mode, clicking a card reveals an inline textarea. The "Edit" button in
the header switches all cards into edit mode simultaneously; a "Save Changes" button
at the bottom of the page calls `saveEdits` with all modified fields.

**Student groups sidebar (`StudentGroupPanel`):** A narrow column on the right
(hidden on mobile, accessible via a "Groups" tab). Shows three collapsed sections
labelled Group A, Group B, and Group C with their student counts and the focus
description from `generated_plan.student_groups`.

**Regenerate modal:** A confirmation dialog: "Regenerate this lesson plan? Your edits
will be lost. A new plan will be generated based on your current class data. This takes
about 30 seconds." Two buttons: "Cancel" and "Regenerate" (gold). On confirm, call
`regenerate` mutation, close the modal, and show a loading state on the plan content
area: the lesson sections are replaced by a skeleton with the text "Generating your
new plan...". The page polls `GET /lesson-plans/{planId}` every 5 seconds until the
status is no longer `GENERATING`.

---

## Dashboard "This Week" Card Update

The teacher dashboard already has a "This Week" placeholder card from M0-9-T2.
Locate this component and update it to:

Fetch `GET /api/v1/classes/{classId}/lesson-plans?page=1&page_size=1` for the most
recent plan using the `useClassLessonPlans` hook. If a GENERATED or EDITED plan
exists, show `LessonPlanCard` with the week label and the two focus subtopic names.
A "View Full Plan" link goes to `/teacher/lesson-plans/{planId}`.

If no plan exists, show the existing placeholder: "Your weekly lesson plan will
appear here every Monday morning."

---

## Acceptance Criteria

**Playwright E2E tests in `lesson-plans.spec.ts`**

`test_list_page_when_plans_exist_then_newest_first` — Seed three plans on different
Mondays. Navigate to the list page. Assert the most recent plan appears first.

`test_list_page_when_recent_plan_then_new_badge_shown` — Seed a plan created
`datetime.now() - 1 hour`. Assert the "New ✨" badge is visible on that row.

`test_list_page_when_no_plans_then_empty_state_shown` — Mock the API to return empty
data. Assert the "No lesson plans generated yet" message is visible.

`test_detail_page_when_loaded_then_five_sections_visible` — Navigate to a plan detail
page. Assert five distinct section cards are present.

`test_detail_page_when_edit_mode_then_textareas_visible` — Click the "Edit" button.
Assert that at least one textarea is visible in the lesson structure area.

`test_detail_page_when_save_changes_then_patch_api_called` — Enter edit mode, change
the starter text, click "Save Changes." Assert a `PATCH /lesson-plans/{id}` request
was made with the updated field.

`test_detail_page_when_regenerate_confirmed_then_generating_skeleton_shown` — Click
"Regenerate," confirm in the modal. Assert the lesson sections are replaced by a
skeleton loading state.

`test_detail_page_when_mark_as_used_then_status_badge_updates` — Click "Mark as Used."
Assert the status badge changes to "USED" and the "Mark as Used" button disappears.

`test_dashboard_card_when_plan_exists_then_shows_plan_data` — Navigate to the teacher
dashboard. Mock the lesson plan API to return one GENERATED plan. Assert the "This
Week" card shows the week label and "View Full Plan" link.

`test_dashboard_card_when_no_plan_then_shows_placeholder` — Mock the API to return
empty data. Assert the "Your weekly lesson plan will appear here every Monday morning"
text is visible.

**Jest unit tests in `LessonEditor.test.tsx`**

`test_lesson_editor_view_mode_shows_activity_text` — Render `LessonEditor` in view
mode with a starter text "Begin with a warm-up." Assert that text is visible and no
textarea is rendered.

`test_lesson_editor_edit_mode_shows_textarea_with_current_text` — Switch to edit mode.
Assert a textarea is visible containing "Begin with a warm-up." as its value.

`test_lesson_editor_save_calls_on_save_with_updated_value` — Change the textarea
content and trigger save. Assert the `onSave` callback is called with the new text.

`test_lesson_editor_cancel_restores_original_text` — Change the textarea content, then
click Cancel. Assert the displayed text reverts to the original and no `onSave` is
called.

---

## Do NOT Touch

`frontend/apps/student/` — no code goes here. `frontend/apps/school-admin/` — no
code goes here. Any backend file. The `useClassLessonPlans` hook from M0-10-T9 — use
as-is, do not rewrite it.
