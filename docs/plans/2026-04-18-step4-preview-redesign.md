# Step 4 Preview Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign Step 4 of the teacher assessment wizard to show a stats bar, difficulty distribution chart, paginated compact question list with per-question preview modal, and a student-view modal.

**Architecture:** Two-part change — backend adds `difficulty_level` and `subtopic_name` to the assessment creation response, frontend consumes these to render the new Step 4 UI. All modals use `Modal` from `@kaihle/ui` (Radix Dialog, focus-trapped). No new routes or services needed.

**Tech Stack:** FastAPI + SQLAlchemy (backend), React + Tailwind + Zustand (frontend), `@kaihle/ui` Modal, Lucide icons.

---

## File Map

| File | Change |
|---|---|
| `backend/app/schemas/assessments.py` | Add `difficulty_level: int` and `subtopic_name: str` to `AssessmentQuestion` |
| `backend/app/api/v1/routes/assessments.py` | Populate new fields via subtopic lookup in `create_assessment` |
| `frontend/apps/teacher/src/hooks/useAssessmentWizard.ts` | Extend `PreviewQuestion` with `difficulty_level` and `subtopic_name` |
| `frontend/apps/teacher/src/pages/assessments/steps/Step4Preview.tsx` | Full redesign — stats, chart, paginated list, two modals |

---

## Task 1: Add `difficulty_level` and `subtopic_name` to backend schema

**Files:**
- Modify: `backend/app/schemas/assessments.py`

- [ ] **Step 1: Update `AssessmentQuestion` schema**

Open `backend/app/schemas/assessments.py`. Replace the `AssessmentQuestion` class:

```python
class AssessmentQuestion(BaseModel):
    """Student-facing question — no correct_answer field by design."""

    question_id: UUID
    question_text: str
    options: list[QuestionOption]
    difficulty_level: int
    subtopic_name: str
```

- [ ] **Step 2: Verify mypy passes**

```bash
cd backend
mypy app/schemas/assessments.py
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/assessments.py
git commit -m "feat(assessments): add difficulty_level and subtopic_name to AssessmentQuestion schema"
```

---

## Task 2: Populate new fields in the `create_assessment` route

**Files:**
- Modify: `backend/app/api/v1/routes/assessments.py`

- [ ] **Step 1: Add Subtopic import**

At the top of `backend/app/api/v1/routes/assessments.py`, add to the existing model import line:

```python
from app.models.assessment import Assessment
from app.models.curriculum import Subtopic   # ← add this line
from app.models.user import UserRole
```

- [ ] **Step 2: Replace the question-building block in `create_assessment`**

Find this block (around line 204):

```python
    questions = [
        AssessmentQuestion(
            question_id=q.id,
            question_text=q.question_text,
            options=[QuestionOption(key=o["key"], text=o["text"]) for o in (q.options or [])],
        )
        for q in question_bank_rows
    ]
```

Replace it with:

```python
    # Batch-fetch subtopic names to avoid N+1
    subtopic_ids = [q.subtopic_id for q in question_bank_rows]
    subtopic_result = await db.execute(
        select(Subtopic.id, Subtopic.name).where(Subtopic.id.in_(subtopic_ids))
    )
    subtopic_name_map: dict = {row[0]: row[1] for row in subtopic_result.all()}

    questions = [
        AssessmentQuestion(
            question_id=q.id,
            question_text=q.question_text,
            options=[QuestionOption(key=o["key"], text=o["text"]) for o in (q.options or [])],
            difficulty_level=q.difficulty_level,
            subtopic_name=subtopic_name_map.get(q.subtopic_id, "Unknown"),
        )
        for q in question_bank_rows
    ]
```

- [ ] **Step 3: Add the missing `select` import (it's already imported via sqlalchemy — verify)**

Check the top of the file for:
```python
from sqlalchemy import and_, func, select
```

If `select` is already there, no change needed. If not, add it.

- [ ] **Step 4: Run mypy**

```bash
cd backend
mypy app/api/v1/routes/assessments.py
```

Expected: no errors.

- [ ] **Step 5: Run existing assessment route tests to confirm nothing broke**

```bash
cd backend
pytest app/tests/ -k "assessment" -v
```

Expected: all existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/routes/assessments.py
git commit -m "feat(assessments): populate difficulty_level and subtopic_name in create_assessment response"
```

---

## Task 3: Extend `PreviewQuestion` type in the frontend hook

**Files:**
- Modify: `frontend/apps/teacher/src/hooks/useAssessmentWizard.ts`

- [ ] **Step 1: Update the `PreviewQuestion` interface**

Open `frontend/apps/teacher/src/hooks/useAssessmentWizard.ts`. Replace:

```typescript
export interface PreviewQuestion {
  question_id: string;
  question_text: string;
  options: Array<{ key: string; text: string }>;
}
```

With:

```typescript
export interface PreviewQuestion {
  question_id: string;
  question_text: string;
  options: Array<{ key: string; text: string }>;
  difficulty_level: number;
  subtopic_name: string;
}
```

- [ ] **Step 2: Run typecheck**

```bash
cd frontend
pnpm typecheck
```

Expected: errors in `Step4Preview.tsx` only (because the mapping there doesn't yet set the new fields). That's expected — Task 4 fixes it.

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/teacher/src/hooks/useAssessmentWizard.ts
git commit -m "feat(assessments): extend PreviewQuestion type with difficulty_level and subtopic_name"
```

---

## Task 4: Redesign `Step4Preview.tsx`

**Files:**
- Modify: `frontend/apps/teacher/src/pages/assessments/steps/Step4Preview.tsx`

- [ ] **Step 1: Replace the entire file content**

```tsx
import { useEffect, useState } from "react";
import { apiClient } from "@kaihle/auth";
import { Button, Badge, Skeleton, Modal } from "@kaihle/ui";
import { X, ChevronLeft, ChevronRight } from "lucide-react";
import {
  useAssessmentWizard,
  type PreviewQuestion,
} from "../../../hooks/useAssessmentWizard";

const PAGE_SIZE = 3;

export function Step4Preview() {
  const {
    classId,
    assessmentType,
    topicIds,
    questionCount,
    difficultyMin,
    difficultyMax,
    deadline,
    draftAssessmentId,
    previewQuestions,
    setDraftAssessment,
    setStep,
  } = useAssessmentWizard();

  const [localQuestions, setLocalQuestions] = useState<PreviewQuestion[]>(
    draftAssessmentId && previewQuestions.length > 0 ? previewQuestions : [],
  );
  const [isLoading, setIsLoading] = useState(false);
  const [insufficientError, setInsufficientError] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [previewQuestion, setPreviewQuestion] = useState<PreviewQuestion | null>(null);
  const [studentViewOpen, setStudentViewOpen] = useState(false);

  useEffect(() => {
    if (draftAssessmentId && previewQuestions.length > 0) return;
    if (!classId) return;

    const abortController = new AbortController();

    async function createDraft() {
      setIsLoading(true);
      setInsufficientError(false);
      setServerError(null);

      try {
        const payload: Record<string, unknown> = {
          assessment_type: assessmentType,
          question_count: questionCount,
          difficulty_min: difficultyMin,
          difficulty_max: difficultyMax,
          topic_ids: topicIds.length > 0 ? topicIds : undefined,
          deadline: deadline ?? undefined,
          is_system_generated: false,
        };

        const res = await apiClient.post(
          `/api/v1/classes/${classId}/assessments`,
          payload,
          { signal: abortController.signal },
        );

        if (abortController.signal.aborted) return;

        const questions: PreviewQuestion[] = (res.data.questions ?? []).map(
          (q: {
            id?: string;
            question_id?: string;
            question_text: string;
            options: Array<{ key: string; text: string }>;
            difficulty_level: number;
            subtopic_name: string;
          }) => ({
            question_id: q.id ?? q.question_id ?? "",
            question_text: q.question_text,
            options: q.options ?? [],
            difficulty_level: q.difficulty_level ?? 1,
            subtopic_name: q.subtopic_name ?? "Unknown",
          }),
        );

        setDraftAssessment(res.data.id, questions);
        setLocalQuestions(questions);
      } catch (err: unknown) {
        if (abortController.signal.aborted) return;
        const axiosErr = err as {
          response?: { status?: number; data?: { detail?: string } };
        };
        if (axiosErr?.response?.status === 422) {
          setInsufficientError(true);
        } else {
          setServerError(
            axiosErr?.response?.data?.detail ??
              "An unexpected error occurred. Please try again.",
          );
        }
      } finally {
        if (!abortController.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    void createDraft();
    return () => { abortController.abort(); };
    // We intentionally only run this on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function removeQuestion(questionId: string) {
    setLocalQuestions((prev) => prev.filter((q) => q.question_id !== questionId));
    setCurrentPage(1);
  }

  // ── Loading state ────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3 mb-4">
          <span
            className="w-4 h-4 border-2 border-brand-gold border-t-transparent rounded-full animate-spin"
            aria-hidden="true"
          />
          <p className="text-sm font-sans text-brand-body italic">
            Selecting questions from the bank…
          </p>
        </div>
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  // ── Error states ─────────────────────────────────────────────────────────
  if (insufficientError) {
    return (
      <div className="space-y-6">
        <div className="bg-brand-red-light border border-brand-red/30 rounded-xl p-4">
          <p className="text-sm font-sans font-semibold text-brand-red mb-1">
            Not enough questions
          </p>
          <p className="text-sm font-sans text-brand-red">
            Not enough questions in the bank for this configuration. Try
            broadening your topic selection or difficulty range.
          </p>
        </div>
        <Button variant="secondary" onClick={() => setStep(3)}>
          Back to Configuration
        </Button>
      </div>
    );
  }

  if (serverError) {
    return (
      <div className="space-y-6">
        <div className="bg-brand-red-light border border-brand-red/30 rounded-xl p-4">
          <p className="text-sm font-sans font-semibold text-brand-red mb-1">
            Something went wrong
          </p>
          <p className="text-sm font-sans text-brand-red">{serverError}</p>
        </div>
        <Button variant="secondary" onClick={() => setStep(3)}>
          Back to Configuration
        </Button>
      </div>
    );
  }

  // ── Computed values ───────────────────────────────────────────────────────
  const difficultyMap = localQuestions.reduce<Record<number, number>>((acc, q) => {
    acc[q.difficulty_level] = (acc[q.difficulty_level] ?? 0) + 1;
    return acc;
  }, {});
  const difficultyLevels = Object.keys(difficultyMap).map(Number).sort((a, b) => a - b);
  const maxCount = difficultyLevels.length > 0 ? Math.max(...Object.values(difficultyMap)) : 1;
  const topicCount = new Set(localQuestions.map((q) => q.subtopic_name)).size;
  const diffMin = difficultyLevels.length > 0 ? Math.min(...difficultyLevels) : difficultyMin;
  const diffMax = difficultyLevels.length > 0 ? Math.max(...difficultyLevels) : difficultyMax;

  const totalPages = Math.max(1, Math.ceil(localQuestions.length / PAGE_SIZE));
  const pageQuestions = localQuestions.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  );

  const sampleQuestion = localQuestions[2] ?? localQuestions[0];

  // ── Main render ───────────────────────────────────────────────────────────
  return (
    <div className="space-y-5">

      {/* Stats bar */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-brand-light border border-brand-border rounded-xl p-3 text-center">
          <p className="font-sans font-extrabold text-2xl text-brand-primary leading-none">
            {localQuestions.length}
          </p>
          <p className="text-xs font-sans text-brand-muted mt-1">in pool</p>
        </div>
        <div className="bg-[#fffbeb] border border-brand-border rounded-xl p-3 text-center">
          <p className="font-sans font-extrabold text-2xl text-brand-gold leading-none">
            {questionCount}
          </p>
          <p className="text-xs font-sans text-brand-muted mt-1">per attempt</p>
        </div>
        <div className="bg-white border border-brand-border rounded-xl p-3 text-center">
          <p className="font-sans font-extrabold text-2xl text-brand-ink leading-none">
            {topicCount}
          </p>
          <p className="text-xs font-sans text-brand-muted mt-1">subtopics</p>
        </div>
        <div className="bg-white border border-brand-border rounded-xl p-3 text-center">
          <p className="font-sans font-extrabold text-2xl text-brand-ink leading-none">
            {diffMin}–{diffMax}
          </p>
          <p className="text-xs font-sans text-brand-muted mt-1">difficulty</p>
        </div>
      </div>

      {/* Difficulty distribution chart */}
      {difficultyLevels.length > 0 && (
        <div className="bg-white border border-brand-border rounded-xl p-4">
          <p className="text-xs font-sans font-bold uppercase tracking-widest text-brand-muted mb-3">
            Difficulty distribution
          </p>
          <div className="flex items-end gap-2 h-10">
            {difficultyLevels.map((level) => {
              const count = difficultyMap[level] ?? 0;
              const heightPct = Math.round((count / maxCount) * 100);
              const isHigher = level > 3;
              return (
                <div key={level} className="flex-1 flex flex-col items-center gap-1">
                  <div
                    className="w-full rounded-t"
                    style={{
                      height: `${heightPct}%`,
                      minHeight: "4px",
                      background: isHigher ? "#c9932a" : "#1a5c38",
                      opacity: 0.5 + level * 0.08,
                    }}
                    aria-label={`Level ${level}: ${count} questions`}
                  />
                </div>
              );
            })}
          </div>
          <div className="flex gap-2 mt-2">
            {difficultyLevels.map((level) => (
              <div key={level} className="flex-1 text-center">
                <p className="text-[10px] font-sans text-brand-muted">Lvl {level}</p>
                <p className="text-[10px] font-sans font-bold text-brand-ink">
                  {difficultyMap[level] ?? 0}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Question list header */}
      <div className="flex items-center justify-between">
        <p className="text-xs font-sans font-bold uppercase tracking-widest text-brand-muted">
          Questions in pool
        </p>
        <p className="text-xs font-sans text-brand-muted">
          {localQuestions.length} total
        </p>
      </div>

      {/* Question rows */}
      <div className="space-y-2">
        {pageQuestions.map((q, idx) => {
          const globalIdx = (currentPage - 1) * PAGE_SIZE + idx + 1;
          return (
            <div
              key={q.question_id}
              className="bg-white border border-brand-border rounded-xl p-3 flex items-center gap-3"
            >
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-brand-light text-brand-primary text-xs font-bold font-sans flex items-center justify-center">
                {globalIdx}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-sans text-brand-ink truncate font-medium">
                  {q.question_text}
                </p>
                <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                  <Badge variant="neutral">
                    {"⭐".repeat(Math.min(q.difficulty_level, 5))} Lvl {q.difficulty_level}
                  </Badge>
                  <Badge variant="info">{q.subtopic_name}</Badge>
                  <span className="text-xs font-sans text-brand-muted">
                    {q.options.length} options
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  type="button"
                  onClick={() => setPreviewQuestion(q)}
                  className="text-xs font-sans font-bold text-brand-gold bg-[#fffbeb] border border-[#fde68a] rounded-md px-2 py-1 hover:bg-[#fef3c7] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
                >
                  Preview
                </button>
                <button
                  type="button"
                  onClick={() => removeQuestion(q.question_id)}
                  className="w-6 h-6 rounded-full flex items-center justify-center text-brand-muted hover:text-brand-red hover:bg-brand-red-light transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
                  aria-label={`Remove question ${globalIdx}`}
                >
                  <X className="w-3 h-3" aria-hidden="true" />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="border border-brand-border rounded-lg p-1.5 text-brand-body hover:text-brand-ink disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
            aria-label="Previous page"
          >
            <ChevronLeft className="w-4 h-4" aria-hidden="true" />
          </button>
          <span className="text-xs font-sans text-brand-body">
            Page {currentPage} of {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            className="border border-brand-border rounded-lg p-1.5 text-brand-body hover:text-brand-ink disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
            aria-label="Next page"
          >
            <ChevronRight className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>
      )}

      {/* Empty state */}
      {localQuestions.length === 0 && (
        <p className="text-sm font-sans text-brand-muted text-center py-8">
          All questions have been removed. Go back to select a different
          configuration.
        </p>
      )}

      {/* Student view banner */}
      <div className="bg-brand-light border border-brand-border rounded-xl p-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-sans font-bold text-brand-primary">
            👁 Student view
          </p>
          <p className="text-xs font-sans text-brand-body mt-0.5">
            See exactly how a student experiences this assessment
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={() => setStudentViewOpen(true)}
          disabled={localQuestions.length === 0}
        >
          Open preview →
        </Button>
      </div>

      {/* Footer */}
      <div className="flex justify-between pt-2">
        <Button variant="secondary" onClick={() => setStep(3)}>
          Back
        </Button>
        <Button
          variant="primary"
          className="bg-brand-gold hover:bg-brand-gold-dark"
          disabled={localQuestions.length === 0}
          onClick={() => setStep(5)}
        >
          Review &amp; Publish
        </Button>
      </div>

      {/* Single-question preview modal */}
      <Modal
        open={previewQuestion !== null}
        onOpenChange={(open) => { if (!open) setPreviewQuestion(null); }}
        title="Question preview"
        description="This is how the student will see this question."
      >
        {previewQuestion && (
          <div className="space-y-4">
            <p className="text-sm font-sans text-brand-ink leading-relaxed font-semibold">
              {previewQuestion.question_text}
            </p>
            <div className="space-y-2">
              {previewQuestion.options.map((opt) => (
                <div
                  key={opt.key}
                  className="border border-brand-border rounded-lg p-3 flex items-center gap-3 text-sm font-sans text-brand-body"
                >
                  <span className="w-6 h-6 rounded flex items-center justify-center bg-brand-border-soft text-brand-muted text-xs font-bold flex-shrink-0">
                    {opt.key.toUpperCase()}
                  </span>
                  {opt.text}
                </div>
              ))}
            </div>
            <div className="flex gap-2 pt-1">
              <Badge variant="neutral">
                {"⭐".repeat(Math.min(previewQuestion.difficulty_level, 5))} Lvl{" "}
                {previewQuestion.difficulty_level}
              </Badge>
              <Badge variant="info">{previewQuestion.subtopic_name}</Badge>
            </div>
          </div>
        )}
      </Modal>

      {/* Student view modal */}
      <Modal
        open={studentViewOpen}
        onOpenChange={setStudentViewOpen}
        title="Student view — adaptive assessment"
        description={`Students answer ${questionCount} questions. Each next question is chosen based on their previous answer.`}
      >
        {sampleQuestion && (
          <div className="space-y-4">
            <div>
              <div className="w-full bg-brand-border rounded-full h-1.5 overflow-hidden mb-1">
                <div
                  className="bg-brand-primary h-1.5 rounded-full"
                  style={{ width: "30%" }}
                  role="progressbar"
                  aria-valuenow={30}
                  aria-valuemin={0}
                  aria-valuemax={100}
                />
              </div>
              <p className="text-xs font-sans text-brand-muted">
                Question 3 of {questionCount}
              </p>
            </div>
            <p className="text-sm font-sans font-semibold text-brand-ink leading-relaxed">
              {sampleQuestion.question_text}
            </p>
            <div className="space-y-2">
              {sampleQuestion.options.map((opt) => (
                <div
                  key={opt.key}
                  className="border border-brand-border rounded-lg p-3 flex items-center gap-3 text-sm font-sans text-brand-body hover:border-brand-primary hover:bg-brand-light transition-colors cursor-pointer"
                >
                  <span className="w-6 h-6 rounded flex items-center justify-center bg-brand-border-soft text-brand-muted text-xs font-bold flex-shrink-0">
                    {opt.key.toUpperCase()}
                  </span>
                  {opt.text}
                </div>
              ))}
            </div>
            <p className="text-xs font-sans text-brand-muted text-center italic">
              Next question adapts based on the student's answer
            </p>
          </div>
        )}
      </Modal>
    </div>
  );
}
```

- [ ] **Step 2: Run typecheck**

```bash
cd frontend
pnpm typecheck
```

Expected: no errors.

- [ ] **Step 3: Run lint**

```bash
cd frontend
pnpm lint
```

Expected: no errors.

- [ ] **Step 4: Smoke-test manually**

Start the teacher app and backend:
```bash
# terminal 1
cd backend && uvicorn app.main:app --reload

# terminal 2
cd frontend && pnpm dev:teacher
```

Navigate to `http://localhost:3001`, create an assessment, reach Step 4 and verify:
- Stats bar shows correct pool count, per-attempt count, subtopic count, difficulty range
- Difficulty chart renders bars
- Question rows show truncated text, level badge, subtopic badge, option count
- "Preview" button opens modal with full question text + A/B/C/D options
- "Open preview →" opens student view modal with progress bar + sample question
- Pagination works (← / →, disabled at boundaries)
- Removing a question with × updates the count and resets to page 1

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/teacher/src/pages/assessments/steps/Step4Preview.tsx
git commit -m "feat(assessments): redesign Step 4 with stats bar, difficulty chart, paginated list, preview modals"
```
