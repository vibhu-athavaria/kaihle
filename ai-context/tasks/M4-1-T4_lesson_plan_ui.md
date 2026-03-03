# M4-1-T4 — Lesson Plan UI (Teacher App)

**Milestone:** M4 — Teacher Copilot
**Epic:** M4-1 — Lesson Plan Generation
**Task ID:** M4-1-T4
**Depends on:** M4-1-T3 (all lesson plan API endpoints)
**Blocks:** Nothing — last task of M4

---

## User Story

As a teacher, I want to view my weekly AI-generated lesson plan in a clear, structured layout, edit any section inline, regenerate if it missed the mark, and mark it as used when I've delivered it.

---

## What To Build

A lesson plan dashboard in the teacher app. Teachers land here from the nav bar or from a notification badge. The current week's plan is shown prominently. Past plans are accessible in a history list.

---

## Files To Create

```
/frontend/apps/teacher/src/
  pages/
    lesson-plans/
      LessonPlansPage.tsx           ← main page (route: /teacher/classes/:classId/lesson-plans)
      LessonPlanDetail.tsx          ← full plan view (current week)
      LessonPlanHistory.tsx         ← accordion list of past plans
  components/
    lesson-plans/
      PlanStatusBadge.tsx           ← GENERATED | EDITED | USED | ARCHIVED badge
      StudentGroupTabs.tsx          ← Group A / B / C tabs with activities
      EditableSection.tsx           ← click-to-edit inline field
      RegenerateModal.tsx           ← confirm before regenerating
  hooks/
    useLessonPlans.ts               ← React Query hooks for all lesson plan endpoints
```

---

## Page Layout: `LessonPlansPage.tsx`

```
/teacher/classes/:classId/lesson-plans

┌─────────────────────────────────────────────────────────────┐
│  Mathematics · Grade 9 · 3B                    [← Back]     │
│                                                             │
│  This Week's Plan  (week of 2 Mar 2026)                     │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ LessonPlanDetail (current week's plan)                │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  Previous Plans                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ LessonPlanHistory (accordion)                         │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Loading state:** Skeleton cards while fetching.
**Empty state:** "No lesson plan yet for this week. Plans are generated every Monday at 6am." (with a "Generate Now" button that calls `/regenerate` on the most recent plan or creates a blank trigger)

---

## `LessonPlanDetail.tsx`

Shows the current week's plan in full. Sections:

```
┌─ Plan Header ───────────────────────────────────────────────┐
│  Week of 2 Mar 2026                     [GENERATED badge]   │
│  Focus: Algebraic Fractions, Ratio & Proportion             │
│                                                             │
│  Class Summary                                              │
│  "60% of students are struggling with simplifying           │
│   fractions. Group C is ready for mixed number work."       │
└─────────────────────────────────────────────────────────────┘

┌─ Student Groups ────────────────────────────────────────────┐
│  [Group A — 8 students] [Group B — 12 students] [Group C — 5] │
│                                                             │
│  (selected tab content)                                     │
│  Group A Focus: Foundational — identifying numerator/       │
│  denominator from visual representations                    │
└─────────────────────────────────────────────────────────────┘

┌─ Lesson Structure ──────────────────────────────────────────┐
│  Starter (10 min)                                  [Edit ✎] │
│  "Begin with a fraction wall visual on the board..."        │
│                                                             │
│  Main Activity (30 min)                            [Edit ✎] │
│  [StudentGroupTabs showing group-specific activities]       │
│                                                             │
│  Plenary (10 min)                                  [Edit ✎] │
│  "Exit ticket: students write one fraction fact..."         │
│                                                             │
│  Homework                                          [Edit ✎] │
│  "Complete questions 1–5 from the worksheet..."             │
└─────────────────────────────────────────────────────────────┘

┌─ Teacher Notes ─────────────────────────────────────────────┐
│  "Watch out for common misconception: students often..."    │
│                                                    [Edit ✎] │
└─────────────────────────────────────────────────────────────┘

[Regenerate Plan]              [Mark as Used ✓]
```

---

## `EditableSection.tsx`

Click-to-edit pattern — no separate edit page.

```tsx
interface EditableSectionProps {
  label: string
  value: string
  fieldKey: keyof LessonPlanEditRequest
  planId: string
  onSave: (fieldKey: string, value: string) => Promise<void>
}

// Behaviour:
// - Default state: shows text with small [Edit ✎] button on hover
// - Click Edit: text becomes a <textarea> pre-filled with current value
// - [Save] and [Cancel] buttons appear
// - Save → calls PATCH /lesson-plans/{planId} with { [fieldKey]: newValue }
// - On success: update local state, show saved indicator for 2 seconds
// - On error: show inline error, keep edit mode open
```

---

## `RegenerateModal.tsx`

```tsx
// Confirmation before regenerating — warn teacher their edits will be lost
<Modal>
  <h2>Regenerate lesson plan?</h2>
  <p>
    This will create a new plan based on your class's latest gap data.
    Any edits you've made to the current plan will be lost.
  </p>
  <button onClick={onCancel}>Keep current plan</button>
  <button onClick={onConfirm}>Yes, regenerate</button>
</Modal>

// On confirm:
// - POST /lesson-plans/{planId}/regenerate
// - Show loading spinner with "Generating... (this takes ~30 seconds)"
// - On success: refresh plan data, close modal, show success toast
// - On error: close modal, show error toast with "Regeneration failed — try again"
```

---

## Notification Badge

In the teacher app nav bar, show a badge on the "Lesson Plans" nav item when a new plan has been generated (status = "GENERATED" and `created_at` is this week).

```tsx
// In NavBar.tsx:
const { data: plans } = useLessonPlans(classId)
const hasNewPlan = plans?.some(
  p => p.status === "GENERATED" &&
       isThisWeek(new Date(p.created_at))
)
// <NavItem badge={hasNewPlan} />
```

---

## `useLessonPlans.ts` Hooks

```ts
// List plans for a class
const useLessonPlans = (classId: string) =>
  useQuery({
    queryKey: ["lesson-plans", classId],
    queryFn: () => apiClient.get(`/classes/${classId}/lesson-plans`),
  })

// Edit a plan field
const useEditLessonPlan = (planId: string) =>
  useMutation({
    mutationFn: (body: LessonPlanEditRequest) =>
      apiClient.patch(`/lesson-plans/${planId}`, body),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["lesson-plans"] }),
  })

// Regenerate
const useRegenerateLessonPlan = (planId: string) =>
  useMutation({
    mutationFn: () => apiClient.post(`/lesson-plans/${planId}/regenerate`),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["lesson-plans"] }),
  })

// Mark as used
const useUpdateLessonPlanStatus = (planId: string) =>
  useMutation({
    mutationFn: (status: "USED" | "ARCHIVED") =>
      apiClient.patch(`/lesson-plans/${planId}/status`, { status }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["lesson-plans"] }),
  })
```

---

## Acceptance Criteria

- [ ] E2E test: teacher navigates to lesson plans page → sees this week's plan
- [ ] E2E test: teacher clicks [Edit ✎] on starter → textarea opens with current text
- [ ] E2E test: teacher types new text, clicks Save → text updated in UI, status badge changes to "EDITED"
- [ ] E2E test: teacher clicks Cancel → original text restored, no API call made
- [ ] E2E test: teacher clicks Regenerate → confirmation modal appears
- [ ] E2E test: teacher confirms regenerate → loading spinner → plan refreshes with new content
- [ ] E2E test: teacher clicks "Mark as Used" → status badge changes to "USED", button disabled
- [ ] E2E test: nav badge shows when new plan available, clears after teacher views it
- [ ] Unit test: `EditableSection` — save calls correct `fieldKey` in PATCH body
- [ ] Unit test: `StudentGroupTabs` — clicking Group B tab shows Group B activity
- [ ] Responsive: all sections readable at 768px (tablet — teacher's most likely device)

---

## Output (what M5 needs)

- Teacher lesson plan UI fully functional — teachers are engaged with the Copilot feature
- `LessonPlanService.generate_for_class()` validated in production via teacher-triggered regeneration
- Celery beat confirmed working (teachers see new plans every Monday)
