# M3-2-T3 — Student Study Plan UI (Student App)
**Milestone:** M3 — Smart Study Plans
**Epic:** M3-2 — Study Plan Lifecycle
**Task:** T3 of 4

---

## Context

The student-facing study plan experience. Students see assigned plans, consume resources matched to their learning style, and take the practice quiz. A "Matched to your style" badge makes the personalisation visible.

**Depends on:** M3-2-T2 (study plan routes)

---

## Files to Create

```
CREATE  frontend/apps/student/src/pages/study-plans/StudyPlanList.tsx
CREATE  frontend/apps/student/src/pages/study-plans/StudyPlanDetail.tsx
CREATE  frontend/apps/student/src/pages/study-plans/ResourceCard.tsx
CREATE  frontend/apps/student/src/pages/study-plans/StudyPlanQuiz.tsx
CREATE  frontend/apps/student/src/hooks/useStudyPlan.ts
CREATE  frontend/apps/student/src/pages/study-plans/__tests__/StudyPlanDetail.test.tsx
```

Also update `/student/my-progress` "Suggested Next Steps" section to link to actual study plans (wires the stub from M2-1-T4).

---

## Routes

```
/student/study-plans              → StudyPlanList.tsx
/student/study-plans/:planId      → StudyPlanDetail.tsx
```

Add "Study Plans" to student nav.

---

## `StudyPlanList.tsx` — Plans List

- Fetches `GET /api/v1/students/me/study-plans`
- Groups plans by subject
- Plan card per item:
  - Subtopic name + subject icon
  - 3 resource thumbnails (or placeholder if still GENERATING)
  - Status badge: "Generating..." / "Ready" / "Completed ✓"
  - Quiz score if completed: "Quiz: 80%"
- Empty state: "No study plans yet — your teacher will assign them based on your assessment results"

---

## `StudyPlanDetail.tsx` — Plan Detail Page

### Section 1 — Resources

Header: "**Learning Resources** — *Matched to your style* ✨" (small badge)

`ResourceCard` components for each resource (ordered by `resource_order`):
- Thumbnail image (YouTube thumbnail or subject icon fallback)
- Resource type icon: 📹 Video / 📄 Article / 🎮 Interactive
- Title (truncated to 2 lines)
- Source + duration ("YouTube · 8 min")
- "Watch / Read / Try" button → opens URL in new tab
- Checkbox "Mark as done" → calls `PATCH .../watched`

After all resources marked done: "Quiz unlocked!" prompt appears.

### Section 2 — Practice Quiz

Only fully visible after at least 1 resource is marked watched (soft gate — not enforced by backend, just UX).

Uses `StudyPlanQuiz` component.

"View quiz" → expands quiz questions.

After submission: shows score + per-question breakdown with explanations.

---

## `StudyPlanQuiz.tsx` — Quiz Component

- Renders questions from `study_plan_quizzes.questions` (no correct_answer exposed)
- MCQ: radio buttons per option
- SHORT_ANSWER: textarea
- "Submit Quiz" button → calls `POST .../quiz/submit`
- After submit: reveals correct answers + explanations per question
- Score display: "4 / 5 correct — Great work!" or "2 / 5 correct — Keep practising!"
- If score < 70%: "Recommended: review the resources above and try again next time"

---

## Acceptance Criteria

### Unit Tests (`StudyPlanDetail.test.tsx`)

- [ ] `test_resource_card_when_watched_then_checkbox_checked`
- [ ] `test_quiz_section_when_no_resources_watched_then_shows_unlock_prompt`
- [ ] `test_quiz_section_when_one_resource_watched_then_quiz_visible`
- [ ] `test_quiz_when_submitted_then_correct_answers_revealed`
- [ ] `test_quiz_score_display_when_4_of_5_correct_then_shows_80_pct`
- [ ] `test_plan_list_when_generating_then_shows_generating_badge_not_resources`

### E2E Tests (Playwright)

- [ ] `test_student_sees_plan_watches_resource_takes_quiz_sees_score`
  - Full journey: plan list → plan detail → mark resource watched → take quiz → see score

- [ ] `test_completed_plan_shows_quiz_score_on_list_card`

---

## Output of This Task

- 4 React component files + 1 hook
- Unit + E2E tests passing
- `/student/my-progress` "Suggested Next Steps" links to study plans

**Next task:** M3-2-T4 (teacher study plan assignment UI)
