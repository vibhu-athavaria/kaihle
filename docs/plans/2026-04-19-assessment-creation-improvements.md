# Assessment Creation Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three issues in the Teacher assessment creation wizard: add topic selection for all assessment types, fix the silent-error bug in topics loading, and replace the static question preview modal with an interactive attempt mode.

**Architecture:** Pure frontend changes across three existing step components. No backend changes, no new dependencies, no schema changes. All changes are self-contained within each step file.

**Tech Stack:** React, TypeScript, Tailwind CSS, React Query v5, Zustand, `@kaihle/ui` Modal (Radix Dialog)

---

## File Map

| File | What changes |
|---|---|
| `frontend/apps/teacher/src/pages/assessments/steps/Step1ClassAndType.tsx` | Remove skip logic for Diagnostic/Final; update card descriptions |
| `frontend/apps/teacher/src/pages/assessments/steps/Step2Topics.tsx` | Remove silent error catch; add `isError` state; remove skip link |
| `frontend/apps/teacher/src/pages/assessments/steps/Step4Preview.tsx` | Replace static preview + student-view modals with interactive attempt mode |

---

## Task 1 — Remove topic-skip logic for Diagnostic and Final

**Files:**
- Modify: `frontend/apps/teacher/src/pages/assessments/steps/Step1ClassAndType.tsx`

- [ ] **Step 1: Open the file and locate the skip check**

  Open `frontend/apps/teacher/src/pages/assessments/steps/Step1ClassAndType.tsx`.
  Find `handleNext` at line ~60. It currently reads:

  ```typescript
  function handleNext() {
    if (!canProceed) return;
    const skipsTopics =
      assessmentType === "DIAGNOSTIC" || assessmentType === "FINAL";
    setStep(skipsTopics ? 3 : 2);
  }
  ```

- [ ] **Step 2: Remove the skip logic — all types go to Step 2**

  Replace the entire `handleNext` function body with:

  ```typescript
  function handleNext() {
    if (!canProceed) return;
    setStep(2);
  }
  ```

- [ ] **Step 3: Update the DIAGNOSTIC card description**

  In the `ASSESSMENT_TYPES` array, find the `DIAGNOSTIC` entry (line ~18–23):

  ```typescript
  {
    type: "DIAGNOSTIC",
    icon: <ClipboardList className="w-5 h-5" aria-hidden="true" />,
    title: "Diagnostic",
    description: "Assess baseline knowledge across all topics",
  },
  ```

  Change the description to:

  ```typescript
  {
    type: "DIAGNOSTIC",
    icon: <ClipboardList className="w-5 h-5" aria-hidden="true" />,
    title: "Diagnostic",
    description: "Assess baseline knowledge across selected topics",
  },
  ```

- [ ] **Step 4: Update the FINAL card description**

  Find the `FINAL` entry (line ~36–41):

  ```typescript
  {
    type: "FINAL",
    icon: <Award className="w-5 h-5" aria-hidden="true" />,
    title: "Final",
    description: "End-of-term comprehensive assessment",
  },
  ```

  Change the description to:

  ```typescript
  {
    type: "FINAL",
    icon: <Award className="w-5 h-5" aria-hidden="true" />,
    title: "Final",
    description: "End-of-term assessment across selected topics",
  },
  ```

- [ ] **Step 5: Verify in dev server**

  ```bash
  cd frontend && pnpm dev:teacher
  ```

  Open http://localhost:3001, create a new assessment, select **Diagnostic** or **Final**, click Next — you should land on Step 2 (Topics) not Step 3.

- [ ] **Step 6: Commit**

  ```bash
  git add frontend/apps/teacher/src/pages/assessments/steps/Step1ClassAndType.tsx
  git commit -m "feat(assessments): show topic selection step for all assessment types"
  ```

---

## Task 2 — Fix silent error bug in topic loading

**Files:**
- Modify: `frontend/apps/teacher/src/pages/assessments/steps/Step2Topics.tsx`

- [ ] **Step 1: Remove the silent try/catch from the fetcher**

  Find `fetchTopicsForClass` at lines 11–30. It currently wraps the API call in try/catch and returns `[]` on any error:

  ```typescript
  async function fetchTopicsForClass(
    subjectId: string,
    gradeId: string,
    curriculumId: string,
  ): Promise<Topic[]> {
    try {
      const res = await apiClient.get(`/api/v1/subjects/${subjectId}/topics`, {
        params: {
          curriculum_id: curriculumId,
          grade_id: gradeId,
        },
      });
      return (res.data || []).map((t: { id: string; name: string }) => ({
        id: t.id,
        name: t.name,
      }));
    } catch {
      return [];
    }
  }
  ```

  Replace with (no try/catch — let React Query capture the error):

  ```typescript
  async function fetchTopicsForClass(
    subjectId: string,
    gradeId: string,
    curriculumId: string,
  ): Promise<Topic[]> {
    const res = await apiClient.get(`/api/v1/subjects/${subjectId}/topics`, {
      params: {
        curriculum_id: curriculumId,
        grade_id: gradeId,
      },
    });
    return (res.data || []).map((t: { id: string; name: string }) => ({
      id: t.id,
      name: t.name,
    }));
  }
  ```

- [ ] **Step 2: Destructure `isError` and `refetch` from `useQuery`**

  Find line ~36 where `useQuery` is used:

  ```typescript
  const { data: topics = [], isLoading } = useQuery({
  ```

  Replace with:

  ```typescript
  const { data: topics = [], isLoading, isError, refetch } = useQuery({
  ```

- [ ] **Step 3: Add the error state render branch**

  Find the loading/empty/list conditional block starting at line ~80:

  ```typescript
  {isLoading ? (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  ) : topics.length === 0 ? (
    <div className="border border-brand-border rounded-xl p-6 text-center">
      <p className="text-sm font-sans text-brand-muted">
        No topics found for this class. You can continue — all available
        questions will be included.
      </p>
      <button
        type="button"
        onClick={() => setStep(3)}
        className="mt-3 text-xs font-sans font-bold text-brand-gold hover:text-brand-gold-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
      >
        Skip to configuration →
      </button>
    </div>
  ) : (
  ```

  Replace the entire conditional with:

  ```typescript
  {isLoading ? (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  ) : isError ? (
    <div className="border border-red-200 bg-red-50 rounded-xl p-6 text-center">
      <p className="text-sm font-sans font-semibold text-red-700 mb-1">
        Failed to load topics
      </p>
      <p className="text-xs font-sans text-brand-muted mb-3">
        Could not connect to the curriculum service. Please try again.
      </p>
      <button
        type="button"
        onClick={() => void refetch()}
        className="text-xs font-sans font-bold text-brand-gold hover:text-brand-gold-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
      >
        Try again →
      </button>
    </div>
  ) : topics.length === 0 ? (
    <div className="border border-brand-border rounded-xl p-6 text-center">
      <p className="text-sm font-sans text-brand-muted">
        No topics defined for this subject and grade yet.
      </p>
    </div>
  ) : (
  ```

- [ ] **Step 4: Update `canProceed` and `disabled` to block on error or empty**

  Current `canProceed` at line ~42:

  ```typescript
  const canProceed = topicIds.length > 0;
  ```

  No change needed — when `topics.length === 0` (error or empty), no topics can be selected, so `topicIds.length` stays 0 and `canProceed` stays `false`.

  Current Next button disabled condition at line ~150:

  ```typescript
  disabled={topics.length > 0 && !canProceed}
  ```

  Update to also disable when there's an error:

  ```typescript
  disabled={isError || (topics.length > 0 && !canProceed)}
  ```

- [ ] **Step 5: Verify**

  In the dev server, create a new assessment for any type. Step 2 should show topics if the API works. To test the error state, temporarily set a wrong URL in `fetchTopicsForClass` (change `/api/v1/subjects/...` to `/api/v1/bad`) — "Failed to load topics" should appear with a retry button. Revert the URL after verifying.

- [ ] **Step 6: Commit**

  ```bash
  git add frontend/apps/teacher/src/pages/assessments/steps/Step2Topics.tsx
  git commit -m "fix(assessments): distinguish API error from empty topics in Step2"
  ```

---

## Task 3 — Replace static preview modal with interactive attempt mode

**Files:**
- Modify: `frontend/apps/teacher/src/pages/assessments/steps/Step4Preview.tsx`

This is the largest change. We're replacing two modals (single-question preview + student view) with one attempt-mode modal that lets the teacher click through questions with immediate feedback. All state is local React state — no API calls.

- [ ] **Step 1: Add attempt-mode state variables**

  In `Step4Preview`, the existing state declarations are at lines 27–36. Add these after the existing state:

  ```typescript
  const [attemptOpen, setAttemptOpen] = useState(false);
  const [attemptIndex, setAttemptIndex] = useState(0);
  // key: question_id, value: selected option key (e.g. "a")
  const [attemptAnswers, setAttemptAnswers] = useState<Record<string, string>>({});
  const [attemptDone, setAttemptDone] = useState(false);
  ```

- [ ] **Step 2: Add a helper to open the attempt modal**

  After the `removeQuestion` function (line ~120), add:

  ```typescript
  function openAttempt(startIndex = 0) {
    setAttemptIndex(startIndex);
    setAttemptAnswers({});
    setAttemptDone(false);
    setAttemptOpen(true);
  }
  ```

- [ ] **Step 3: Add "Try assessment" button to the stats bar**

  The stats bar is a 4-column grid starting at line ~209. Change the outer `<div>` wrapper to include the button below the grid:

  ```tsx
  {/* Stats bar + try button */}
  <div className="space-y-2">
    <div className="grid grid-cols-4 gap-3">
      {/* ... existing 4 stat tiles unchanged ... */}
    </div>
    <div className="flex justify-end">
      <button
        type="button"
        onClick={() => openAttempt(0)}
        disabled={localQuestions.length === 0}
        className="text-xs font-sans font-bold text-brand-gold border border-[#fde68a] bg-[#fffbeb] rounded-full px-4 py-1.5 hover:bg-[#fef3c7] transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
      >
        Try assessment →
      </button>
    </div>
  </div>
  ```

- [ ] **Step 4: Replace the per-question "Preview" button with "Try"**

  In the question rows (line ~319–325), find:

  ```tsx
  <button
    type="button"
    onClick={() => setPreviewQuestion(q)}
    className="text-xs font-sans font-bold text-brand-gold bg-[#fffbeb] border border-[#fde68a] rounded-md px-2 py-1 hover:bg-[#fef3c7] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
  >
    Preview
  </button>
  ```

  Replace with (uses `openAttempt` with the global index of this question):

  ```tsx
  <button
    type="button"
    onClick={() => openAttempt((currentPage - 1) * PAGE_SIZE + idx)}
    className="text-xs font-sans font-bold text-brand-gold bg-[#fffbeb] border border-[#fde68a] rounded-md px-2 py-1 hover:bg-[#fef3c7] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
  >
    Try
  </button>
  ```

- [ ] **Step 5: Remove the "Student view" banner**

  Remove the entire `<div>` block from line ~376–392 (the banner that says "👁 Student view" with "Open preview →" button). It's superseded by the new attempt mode.

- [ ] **Step 6: Remove old state variables that are no longer used**

  Delete these two `useState` declarations (lines ~34–36):

  ```typescript
  const [previewQuestion, setPreviewQuestion] =
    useState<PreviewQuestion | null>(null);
  const [studentViewOpen, setStudentViewOpen] = useState(false);
  ```

  Also delete `const sampleQuestion = localQuestions[2] ?? localQuestions[0];` (line ~203) — it was only used by the student view modal.

- [ ] **Step 7: Replace the two old modals with the attempt-mode modal**

  Remove the entire `{/* Single-question preview modal */}` Modal block (lines ~410–445) and the `{/* Student view modal */}` Modal block (lines ~448–492).

  Add the new attempt-mode modal in their place, just before the closing `</div>` of the component:

  ```tsx
  {/* Attempt-mode modal */}
  <Modal
    open={attemptOpen}
    onOpenChange={(open) => {
      if (!open) setAttemptOpen(false);
    }}
    title="Try assessment"
    description="Preview only — no answers are stored."
  >
    {(() => {
      const currentQ = localQuestions[attemptIndex];
      const totalQ = localQuestions.length;
      const progressPct = totalQ > 0 ? Math.round((attemptIndex / totalQ) * 100) : 0;
      const selectedKey = currentQ ? attemptAnswers[currentQ.question_id] : undefined;
      const answered = selectedKey !== undefined;

      // We don't have the correct answer key from the API, so we show
      // which option the teacher picked and mark it; all others stay neutral.
      // When the API returns a `correct_option` field in future, swap this logic.

      if (attemptDone) {
        const total = localQuestions.length;
        return (
          <div className="space-y-6 text-center py-4">
            <p className="font-display font-bold text-2xl text-brand-ink">
              You attempted all {total} questions
            </p>
            <p className="text-sm font-sans text-brand-body">
              This was a preview — no answers were stored.
            </p>
            <button
              type="button"
              onClick={() => setAttemptOpen(false)}
              className="px-6 py-2 bg-brand-primary text-white rounded-full text-sm font-sans font-bold hover:bg-brand-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            >
              Close
            </button>
          </div>
        );
      }

      if (!currentQ) return null;

      return (
        <div className="space-y-5">
          {/* Progress */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-sans font-bold uppercase tracking-wide text-brand-muted">
                Question {attemptIndex + 1} of {totalQ}
              </span>
              <span className="text-xs font-sans text-brand-muted">
                {"●".repeat(Math.min(currentQ.difficulty_level, 5))}{"○".repeat(Math.max(0, 5 - currentQ.difficulty_level))} Lvl {currentQ.difficulty_level}
              </span>
            </div>
            <div className="w-full bg-brand-border rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-brand-primary h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${progressPct}%` }}
                role="progressbar"
                aria-valuenow={progressPct}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            </div>
          </div>

          {/* Question text */}
          <p className="text-sm font-sans font-semibold text-brand-ink leading-relaxed">
            {currentQ.question_text}
          </p>

          {/* Options */}
          <div className="space-y-2">
            {currentQ.options.map((opt) => {
              const isSelected = selectedKey === opt.key;
              return (
                <button
                  key={opt.key}
                  type="button"
                  disabled={answered}
                  onClick={() =>
                    setAttemptAnswers((prev) => ({
                      ...prev,
                      [currentQ.question_id]: opt.key,
                    }))
                  }
                  className={[
                    "w-full text-left flex items-center gap-3 px-4 py-2.5 rounded-xl border-[1.5px] transition-colors text-sm font-sans",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1",
                    answered && !isSelected
                      ? "border-brand-border text-brand-muted cursor-default opacity-60"
                      : isSelected
                        ? "border-brand-primary bg-brand-light text-brand-primary font-semibold"
                        : "border-brand-border text-brand-ink hover:border-brand-primary hover:bg-brand-light cursor-pointer",
                  ].join(" ")}
                >
                  <span
                    className={[
                      "w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0",
                      isSelected
                        ? "bg-brand-primary text-white"
                        : "bg-brand-border-soft text-brand-muted",
                    ].join(" ")}
                  >
                    {opt.key.toUpperCase()}
                  </span>
                  <span>{opt.text}</span>
                  {isSelected && (
                    <span className="ml-auto text-xs font-bold text-brand-primary">
                      ✓ Selected
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Footer note */}
          <p className="text-xs font-sans text-brand-muted text-center italic">
            Preview only — no answers stored
          </p>

          {/* Navigation */}
          <div className="flex justify-between pt-1">
            <button
              type="button"
              disabled={attemptIndex === 0}
              onClick={() => setAttemptIndex((i) => i - 1)}
              className="px-4 py-2 border border-brand-border rounded-full text-xs font-sans font-semibold text-brand-body hover:text-brand-ink disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
            >
              ← Previous
            </button>
            {answered && (
              attemptIndex < totalQ - 1 ? (
                <button
                  type="button"
                  onClick={() => setAttemptIndex((i) => i + 1)}
                  className="px-4 py-2 bg-brand-primary text-white rounded-full text-xs font-sans font-bold hover:bg-brand-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1"
                >
                  Next →
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => setAttemptDone(true)}
                  className="px-4 py-2 bg-brand-primary text-white rounded-full text-xs font-sans font-bold hover:bg-brand-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1"
                >
                  See results →
                </button>
              )
            )}
          </div>
        </div>
      );
    })()}
  </Modal>
  ```

- [ ] **Step 8: TypeScript check**

  ```bash
  cd frontend && pnpm typecheck
  ```

  Expected: no errors in `Step4Preview.tsx`. Fix any TS errors before continuing.

- [ ] **Step 9: Lint**

  ```bash
  cd frontend && pnpm lint
  ```

  Expected: no new lint errors. Fix if any.

- [ ] **Step 10: Verify in dev server**

  In http://localhost:3001, create an assessment through to Step 4. Verify:
  - "Try assessment →" button appears below the stats bar.
  - Clicking it opens a full attempt-mode modal showing Question 1 of N.
  - Selecting an option highlights it in green with "✓ Selected".
  - "Next →" appears after selection; previous questions can be revisited.
  - On the last question, "See results →" appears and leads to the done screen.
  - "Try" button on each row opens attempt mode starting at that question.
  - Closing the modal and reopening resets state.
  - The old "Student view" banner is gone from the step.

- [ ] **Step 11: Commit**

  ```bash
  git add frontend/apps/teacher/src/pages/assessments/steps/Step4Preview.tsx
  git commit -m "feat(assessments): replace static preview modal with interactive attempt mode"
  ```

---

## Self-Review Notes

- **Spec coverage:** All three improvements are covered by Tasks 1–3.
- **No placeholders:** All code is complete.
- **Type consistency:** `attemptAnswers` is `Record<string, string>` throughout. `openAttempt(startIndex = 0)` is called with a number in all uses. `PreviewQuestion` type unchanged.
- **Note on correct-answer highlighting:** The `PreviewQuestion` type does not include a `correct_option` field (the backend schema does not return it). Attempt mode shows which option the teacher selected (green highlight) but cannot show correct vs incorrect. This is intentional — a future improvement would add `correct_option` to the backend response. The "Preview only" caption makes this clear to the teacher.
