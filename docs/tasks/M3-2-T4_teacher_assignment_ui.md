# M3-2-T4 — Teacher Study Plan Assignment UI (Teacher App)
**Milestone:** M3 · **Epic:** M3-2 · **Task:** T4
**Depends on:** M3-2-T2 (study plan routes live), M2-1-T3 (gap map heatmap — assignment is triggered from here)
**Blocks:** Nothing — final task of M3
**Estimated effort:** 3–4 hours

---

## Context

All code in this task lives in `frontend/apps/teacher`. No code goes in any other app.

This task wires up the "Assign Study Plan" button that was stubbed as a disabled
placeholder in M2-1-T3. That button already exists in `StudentSidePanel.tsx` with an
`onClick` that shows a "coming in next update" toast. This task replaces that stub
handler with a real modal.

Read `docs/design/DESIGN_SYSTEM.md` §5.3 (Teacher) before writing. Action buttons
use gold (`brand-gold`).

---

## User Story

As a teacher, I want to assign a personalised study plan to one or more students
directly from the gap map, so I can act on identified gaps without navigating away.

---

## Files to Create / Modify

```
frontend/apps/teacher/src/components/study-plans/
  AssignStudyPlanModal.tsx      ← CREATE: assignment modal
  StudentSelectionList.tsx      ← CREATE: student picker for custom selection

frontend/apps/teacher/src/hooks/
  useAssignStudyPlan.ts         ← CREATE: mutation hook

frontend/apps/teacher/src/pages/gap-map/
  StudentSidePanel.tsx          ← MODIFY: wire up real modal instead of toast stub
```

---

## Complete List of API Calls This UI Makes

`POST /api/v1/classes/{classId}/study-plans` — called by `useAssignStudyPlan` when
the teacher confirms the assignment. Body: `StudyPlanAssignRequest` with `subtopic_id`
and either `student_ids: null` (all students below threshold) or a specific list.

`GET /api/v1/classes/{classId}/enrollments` — called inside the modal to populate the
custom student selection list when the teacher chooses "Custom selection". This list
shows all enrolled students with their current mastery score for the selected subtopic.

Those are the only two API calls. The subtopic and class context come from the gap map
data already loaded in the parent component — no additional fetch needed.

---

## `useAssignStudyPlan.ts`

```typescript
export const useAssignStudyPlan = (classId: string) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: StudyPlanAssignRequest) =>
      apiClient.post<StudyPlanAssignResponse>(
        `/classes/${classId}/study-plans`,
        body,
      ),
    onSuccess: () => {
      // Invalidate the teacher's class data so the gap map refreshes
      queryClient.invalidateQueries({ queryKey: ['teacher', 'gap-map', classId] })
    },
  })
}
```

---

## `AssignStudyPlanModal.tsx`

The modal opens when the teacher clicks "Assign Study Plan" in `StudentSidePanel`.
It receives the `classId`, `subtopicId`, `subtopicName`, and the current `studentScores`
array from the gap map node as props.

```typescript
interface AssignStudyPlanModalProps {
  isOpen: boolean
  onClose: () => void
  classId: string
  subtopicId: string
  subtopicName: string
  studentScores: StudentGapScore[]   // from gap map node — used to count at-risk students
}
```

The modal body shows three radio options:

"All students with mastery below 70%" — counts students from `studentScores` where
`mastery_score < 0.7` (or mastery is null). Shows the count: "12 students". This is
the default selection.

"Only this student ({studentName})" — assigns only the student whose cell was clicked.
The `studentName` comes from the selected student in `StudentSidePanel`.

"Custom selection" — reveals `StudentSelectionList`, a checkbox list of all enrolled
students with their current mastery score for this subtopic shown next to their name.

Below the selection, show a muted line: "Estimated generation time: ~30 seconds."

Two footer buttons: "Cancel" (closes modal, no API call) and "Generate Plans →"
(gold, calls the mutation). While the mutation is in-flight, the button shows a
spinner and the text "Generating..." and is disabled to prevent double-submission.

On success: close modal, show a success toast: "Study plans generating for {n}
students. They'll be notified when ready."

On error: show an inline error inside the modal — do not close it. The teacher should
be able to retry without re-entering their selection.

---

## Modifying `StudentSidePanel.tsx`

Find the existing "Assign Study Plan" button stub. It currently looks like:

```typescript
// M2-1-T3 stub — wire up in M3-2-T4
<Button
  className="opacity-60 cursor-not-allowed"
  onClick={() => toast("Study plan assignment coming in the next update.")}
>
  Assign Study Plan
</Button>
```

Replace it with:

```typescript
const [isAssignModalOpen, setIsAssignModalOpen] = useState(false)

// Replace stub button:
<Button
  variant="primary"
  disabled={!selectedCell || selectedCell.mastery_score >= 0.7}
  onClick={() => setIsAssignModalOpen(true)}
>
  Assign Study Plan
</Button>

// Add modal at end of component:
{isAssignModalOpen && selectedSubtopic && (
  <AssignStudyPlanModal
    isOpen={isAssignModalOpen}
    onClose={() => setIsAssignModalOpen(false)}
    classId={classId}
    subtopicId={selectedSubtopic.subtopic_id}
    subtopicName={selectedSubtopic.subtopic_name}
    studentScores={selectedSubtopic.student_scores}
  />
)}
```

The button is disabled (greyed, not hidden) when the selected cell has
`mastery_score >= 0.7` (Strong — no study plan needed). This gives the teacher
feedback about why the action is unavailable rather than hiding it.

---

## Acceptance Criteria

**Playwright E2E tests in `gap-map.spec.ts`** (add to existing file from M2-1-T3)

`test_assign_button_when_red_cell_then_enabled` — Click a cell with mastery 0.3.
Assert the "Assign Study Plan" button in the side panel does not have the `disabled`
attribute.

`test_assign_button_when_green_cell_then_disabled` — Click a cell with mastery 0.85.
Assert the "Assign Study Plan" button is disabled.

`test_assign_modal_opens_when_button_clicked` — Click an enabled "Assign Study Plan"
button. Assert the modal is visible with the subtopic name shown.

`test_assign_modal_default_option_is_all_below_threshold` — Open the modal. Assert
the "All students with mastery below 70%" radio is selected by default and shows the
correct student count.

`test_assign_modal_when_custom_selected_then_student_list_shown` — Select "Custom
selection." Assert the `StudentSelectionList` component becomes visible.

`test_assign_modal_when_generate_clicked_then_api_called_and_modal_closes` — Mock the
`POST /classes/{id}/study-plans` endpoint to return 202. Click "Generate Plans." Assert
the modal closes and a success toast appears mentioning the student count.

`test_assign_modal_when_api_fails_then_stays_open_with_error` — Mock the endpoint to
return 500. Click "Generate Plans." Assert the modal remains open and an error message
is visible inside it.

`test_assign_modal_when_cancel_clicked_then_closes_without_api_call` — Click Cancel.
Assert the modal closes and no API call was made to `/study-plans`.

---

## Do NOT Touch

`frontend/apps/student/` — no code goes here. Any backend file. The `useClassGapMap`
hook or `GapMapGrid` component — do not refactor those in this task.
