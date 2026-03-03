# M3-2-T4 — Teacher Study Plan Assignment UI

**Milestone:** M3 — Smart Study Plans
**Epic:** M3-2 — Study Plan Lifecycle
**Task ID:** M3-2-T4
**Depends on:** M3-2-T2 (study plan routes), M2-1-T3 (gap map heatmap UI — assignment is triggered from here)
**Blocks:** Nothing — last task of M3

---

## User Story

As a teacher, I want to assign a personalised study plan to students directly from the gap map, so I can act on gaps immediately without switching screens.

---

## What To Build

Add an "Assign Study Plan" action to the gap map heatmap UI (M2-1-T3). When a teacher clicks a red or amber cell and selects "Assign Study Plan," a modal opens confirming the subtopic and letting the teacher choose which students to assign it to. On confirm, the system queues study plan generation for each selected student.

---

## Files To Create / Modify

```
/frontend/apps/teacher/src/
  components/
    study-plans/
      AssignStudyPlanModal.tsx      ← NEW
      StudentSelectionList.tsx      ← NEW
      AssignmentSuccessToast.tsx    ← NEW
  hooks/
    useAssignStudyPlan.ts           ← NEW
  pages/
    gap-map/
      GapMapPage.tsx                ← MODIFY — add "Assign Study Plan" button to cell side panel
```

---

## UI Flow

```
Teacher clicks a cell in the heatmap (M2-1-T3)
  → Side panel opens showing student gap detail
  → "Assign Study Plan" button visible at bottom of panel
    (Only shown if cell mastery < 0.7 — no point assigning for green cells)

Teacher clicks "Assign Study Plan"
  → AssignStudyPlanModal opens

Modal contents:
  ┌─────────────────────────────────────────────────┐
  │ Assign Study Plan                           [×] │
  │                                                 │
  │ Subtopic: Algebraic Fractions                   │
  │ Subject:  Mathematics · Grade 9                 │
  │                                                 │
  │ Select students:                                │
  │ ● All students with mastery < 60% (12 students) │ ← default
  │ ○ Only this student (Emma Wilson)               │
  │ ○ Custom selection                              │
  │   [StudentSelectionList when custom selected]  │
  │                                                 │
  │ Estimated time to generate: ~30 seconds         │
  │                                                 │
  │        [Cancel]  [Generate Plans →]             │
  └─────────────────────────────────────────────────┘

On "Generate Plans" click:
  → Button shows spinner + "Generating..."
  → POST /api/v1/classes/{class_id}/study-plans
  → On success: modal closes, success toast appears
  → Toast: "Study plans generating for 12 students. They'll be notified when ready."
  → On error: inline error message inside modal (do not close)
```

---

## Component Implementation

### `AssignStudyPlanModal.tsx`
```tsx
interface AssignStudyPlanModalProps {
  isOpen: boolean
  onClose: () => void
  classId: string
  subtopicId: string
  subtopicName: string
  subjectName: string
  gradeName: string
  focusStudentId?: string        // pre-selected when triggered from single student cell
  studentsWithGap: Array<{       // students with mastery < 0.7 for this subtopic
    id: string
    name: string
    masteryScore: number
  }>
}
```

**Selection modes:**
- "All students with mastery < 60%" — default, auto-computed from `studentsWithGap` filtered to `masteryScore < 0.6`
- "Only this student" — only shown if `focusStudentId` is provided
- "Custom selection" — renders `StudentSelectionList` with checkboxes

**Submit payload:**
```ts
// All or custom:
{ subtopic_id: string, student_ids: string[] }
// Never send "all" as a keyword — always resolve to explicit IDs on the frontend
```

### `useAssignStudyPlan.ts`
```ts
const useAssignStudyPlan = (classId: string) => {
  const mutation = useMutation({
    mutationFn: (payload: { subtopic_id: string; student_ids: string[] }) =>
      apiClient.post(`/classes/${classId}/study-plans`, payload),
    onSuccess: () => {
      toast.success('Study plans are generating...')
      queryClient.invalidateQueries({ queryKey: ['study-plans', classId] })
    },
  })
  return mutation
}
```

### `StudentSelectionList.tsx`
- Renders a scrollable list of students (max height 240px, overflow scroll)
- Each row: checkbox, student name, mastery score badge (colour-coded)
- "Select all" / "Deselect all" toggle at top

---

## GapMapPage.tsx Modifications

In the existing side panel (from M2-1-T3), add below the student learning profile section:

```tsx
{cellMastery < 0.7 && (
  <button
    onClick={() => setAssignModalOpen(true)}
    className="mt-4 w-full bg-indigo-600 text-white rounded-lg py-2 px-4
               hover:bg-indigo-700 transition-colors text-sm font-medium"
  >
    Assign Study Plan
  </button>
)}

<AssignStudyPlanModal
  isOpen={assignModalOpen}
  onClose={() => setAssignModalOpen(false)}
  classId={classId}
  subtopicId={selectedCell.subtopicId}
  subtopicName={selectedCell.subtopicName}
  subjectName={selectedCell.subjectName}
  gradeName={selectedCell.gradeName}
  focusStudentId={selectedCell.studentId}
  studentsWithGap={studentsWithGapForSubtopic}
/>
```

---

## Acceptance Criteria

- [ ] E2E test: teacher clicks red cell → side panel shows "Assign Study Plan" button
- [ ] E2E test: teacher clicks green cell → "Assign Study Plan" button NOT shown
- [ ] E2E test: teacher opens modal → default selection is "All students with mastery < 60%"
- [ ] E2E test: teacher clicks "Generate Plans" → loading state shown → success toast appears
- [ ] E2E test: teacher selects "Custom selection" → `StudentSelectionList` renders with checkboxes
- [ ] E2E test: API error → modal stays open, error message shown inline
- [ ] Unit test: `useAssignStudyPlan` calls correct endpoint with resolved `student_ids` array
- [ ] Unit test: "All students with mastery < 60%" correctly filters to mastery < 0.6 only
- [ ] Responsive: modal correct at 768px and 1280px viewports

---

## Output (what the next milestone needs)

- Teacher can assign study plans from the gap map with one click
- Study plan generation is queued via `POST /api/v1/classes/{class_id}/study-plans`
- Students are notified when plans are ready (via existing notification system)
- M4 Teacher Copilot can reference that study plans have been assigned when generating lesson plans
