# M1-3-T3 — Assessment Creation UI (Teacher App)
**Milestone:** M1 · **Epic:** M1-3 · **Task:** T3
**Depends on:** M1-3-T2 (assessment API routes), M0-3-T4 (auth frontend)

---

## User Story
As a teacher, I want a step-by-step wizard to create and publish an assessment for my class so I can quickly set up a diagnostic without confusion.

---

## Files to Create

```
frontend/apps/teacher/src/pages/assessments/NewAssessment.tsx    # 5-step wizard
frontend/apps/teacher/src/pages/assessments/AssessmentList.tsx   # class assessments list
frontend/apps/teacher/src/hooks/useAssessments.ts
frontend/apps/teacher/src/store/newAssessmentStore.ts            # Zustand wizard state
frontend/apps/teacher/src/tests/assessment-creation.spec.ts      # Playwright E2E
```

---

## 5-Step Wizard (`NewAssessment.tsx`)

### Step 1 — Select Class & Type
- Dropdown: select class (fetches `GET /api/v1/schools/{school_id}/classes`)
- Radio cards: Assessment Type (DIAGNOSTIC / TOPIC_SPECIFIC / PROGRESS_CHECK / FINAL)
- Each type has a one-line description below the label

### Step 2 — Select Topics
- Only shown for TOPIC_SPECIFIC and PROGRESS_CHECK (skip to Step 3 for DIAGNOSTIC/FINAL)
- Checklist of curriculum topics for the class's subject + grade
- At least one topic must be selected to proceed

### Step 3 — Configure Questions
- Number of questions: slider 5–30 (default 10)
- Question types: multi-checkbox (MCQ / True-False / Short Answer)
- Difficulty: range slider 1.0–5.0 (default: full range)
- Optional: set deadline (date picker)

### Step 4 — Preview Questions
- Calls `POST /api/v1/assessments` with `status=DRAFT` to generate
- Shows question list: question text + type badge
- Teacher can click ✕ to remove individual questions
- "Regenerate" button calls API again with same config
- Question count badge updates as teacher removes questions

### Step 5 — Review & Publish
- Summary card: class name, type, topic(s), question count, deadline
- Two buttons:
  - "Save as Draft" — keeps `status=DRAFT`
  - "Publish Now" — calls `POST /api/v1/assessments/{id}/publish`
- On publish: success toast → navigate to `/teacher/classes/{class_id}/assessments`

---

## Assessment List (`AssessmentList.tsx`)

Route: `/teacher/classes/{class_id}/assessments`

- Table with columns: Title, Type, Status badge, Questions, Deadline, Actions
- Status badges: DRAFT (grey) / ACTIVE (green) / CLOSED (slate)
- Actions: View Results | Close | Delete (Draft only)
- "Create New Assessment" button → `/teacher/assessments/new`

---

## Wizard State (`newAssessmentStore.ts`)

```typescript
interface NewAssessmentState {
  step: 1 | 2 | 3 | 4 | 5
  classId: string | null
  assessmentType: AssessmentType | null
  topicIds: string[]
  numQuestions: number
  questionTypes: QuestionType[]
  difficultyRange: [number, number]
  deadline: Date | null
  draftAssessmentId: string | null   // set after Step 4 API call
  goNext: () => void
  goBack: () => void
  reset: () => void
}
```

---

## Acceptance Criteria

- [ ] E2E: teacher completes 5-step wizard → assessment created and published
- [ ] E2E: DIAGNOSTIC type skips topic selection step
- [ ] E2E: teacher removes a question in Step 4 → question count updates
- [ ] E2E: "Save as Draft" → assessment appears in list with DRAFT badge
- [ ] E2E: "Publish Now" → assessment appears with ACTIVE badge
- [ ] E2E: student can see ACTIVE assessment (via student app check)
- [ ] Unit: step validation — cannot proceed from Step 1 without selecting class and type
- [ ] Unit: Step 2 not rendered for DIAGNOSTIC type
- [ ] Responsive: wizard usable at 768px (tablet — teacher likely on iPad)

---

## Tests to Write (Playwright)

```typescript
test('wizard_completes_and_publishes_assessment')
test('diagnostic_type_skips_topic_step')
test('remove_question_updates_count')
test('save_draft_shows_draft_badge_in_list')
test('publish_shows_active_badge_in_list')
```
