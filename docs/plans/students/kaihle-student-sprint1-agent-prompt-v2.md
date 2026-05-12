# Kaihle Student App — Sprint 1 Agent Prompt
# Version 2 — based on actual code review of App.tsx, Sidebar.tsx,
# StudentDashboard.tsx, StudentSettings.tsx, Assessments.tsx,
# ClassCard.tsx, StudentLayout.tsx, guards.tsx, useOnboardingStatus.ts,
# useStudentDashboard.ts, OnboardingRouter.tsx
#
# Usage: claude --task plans/student/kaihle-student-sprint1-agent-prompt.md
# Or paste directly into an active Claude Code session.

---

You are implementing the Kaihle Student App Sprint 1.

Primary task file:    plans/student/kaihle-student-tasks-v2.md
Architecture doc:     plans/student/kaihle-concept-guide-architecture.md  (ST-020 only)

---

## PHASE 0 — MANDATORY READS (no code before these are done)

Read in this order. Every file. No skipping.

```
1.  CLAUDE.md
2.  docs/CONSTITUTION.md                   (22 rules — you are held to all of them)
3.  docs/design/DESIGN_SYSTEM.md           (required before any component — Rule 16)
4.  docs/kaihle_v2_1_schema.sql            (schema is source of truth — Rule 8)
5.  docs/API_ENDPOINT_TASK_MAP.md          (live vs stubbed endpoints)
6.  plans/student/kaihle-student-tasks-v2.md
```

Then open and read these source files — the ones marked ✓ have confirmed bugs,
the ones marked ? still need verification. Read all of them.

```
✓  apps/student/src/components/ClassCard.tsx
✓  packages/ui/src/layouts/StudentLayout.tsx
✓  packages/auth/src/guards.tsx
✓  apps/student/src/hooks/useOnboardingStatus.ts
✓  apps/student/src/hooks/useStudentDashboard.ts     (read full file — refetch method too)
✓  apps/student/src/pages/dashboard/StudentDashboard.tsx
✓  apps/student/src/pages/settings/StudentSettings.tsx
✓  apps/student/src/pages/assessments/Assessments.tsx
✓  apps/student/src/pages/onboarding/OnboardingRouter.tsx
?  apps/student/src/pages/study-plans/StudyPlans.tsx
?  apps/student/src/pages/my-progress/MyProgress.tsx
?  apps/student/src/pages/dashboard/NextStepCard.tsx
?  apps/student/src/pages/onboarding/ProfileQuestionnaire.tsx
?  apps/student/src/store/questionnaireStore.ts
?  apps/student/src/components/settings/LearningProfileSection.tsx
?  apps/student/src/components/settings/AccountSection.tsx
?  apps/student/src/components/settings/AccountActionsSection.tsx
?  apps/student/src/hooks/useStudentGapMap.ts
?  apps/student/src/hooks/useSubjectScores.ts
?  apps/student/src/pages/assessments/TakeAssessmentPage.tsx
?  backend/app/ai/providers/router.py
?  backend/app/api/v1/routes/onboarding.py            (is /students/me/learning-profile a stub?)
?  apps/student/package.json
?  frontend/e2e/diagnostic-gate.spec.ts
```

Do not skip the ? files. Do not assume their content from the task description.

---

## PHASE 1 — PRE-FLIGHT GRAPH

After reading all files, output a pre-flight graph. Format:

```
TASK    BRANCH FROM   DEPENDS ON    BUG EXISTS?   SPEC CORRECT?   NOTE
ST-001  main          —             VERIFY        YES
ST-002  main          —             YES           YES             ffont-sans + mb- confirmed
...
```

For every task:
- BUG EXISTS? — confirm the described issue is actually present in the code you read
- SPEC CORRECT? — flag any task where the described fix contradicts what you found
  (see KNOWN SPEC ERRORS below before doing this)

Stop and present the graph. Wait for approval before executing any task.

---

## PHASE 2 — KNOWN SPEC ERRORS (read before writing the graph)

The following errors were found by code review after the task file was written.
The agent MUST follow the corrections below, not the task file description.

### ST-005 — buildNextSteps signature must NOT be changed

The task file says to rebuild `buildNextSteps` with signature
`buildNextSteps(resolvedScores: ResolvedSubjectScore[])`.

**This is wrong.** The actual function already has this signature:
```ts
function buildNextSteps(
  assessments: Array<...>,
  activeStudyPlans: Array<...>,
  inProgressStudyPlans: Array<...>,
  subjectScores: ResolvedSubjectScore[],  // ← already exists
): NextStep[]
```
And the dashboard already calls it with `resolvedSubjectScores` as the 4th arg.
Do NOT change the function signature.

Correct fix for ST-005:
1. In `useStudentDashboard.ts`: remove the `gapMapQuery` that hardcodes
   `primarySubjectId = enrolledClasses?.[0]?.subjectId` — the refetch should
   be parallel (Promise.all), and the gap map should not be fetched redundantly
   when SubjectScoresSection already fetches per-subject scores.
2. In `buildNextSteps`: verify the weakest-area step (type `"weakest-area"`)
   actually uses the `subjectScores` parameter to find the lowest-mastery
   subtopic across all subjects. If it doesn't, implement that logic.
   Do not touch the other three priority steps.

### ST-008 — two files, one already fixed

`apps/student/src/pages/onboarding/OnboardingRouter.tsx` — ALREADY CORRECTLY
implements Gate 1 only (learning_profile). Do not touch this file.

Fix target is `packages/auth/src/guards.tsx` only.
The `isOnboardingComplete()` function currently reads:
```ts
function isOnboardingComplete(status: OnboardingStatus): boolean {
  if (!status.learning_profile_complete) return false;
}
```
Fix: gate on `learning_profile_complete` only. Remove the diagnostics check entirely.
```ts
function isOnboardingComplete(status: OnboardingStatus): boolean {
  return status.learning_profile_complete === true;
}
```

Additionally: `frontend/e2e/diagnostic-gate.spec.ts` uses text `'Complete diagnostic to unlock'`
and `[aria-label="Locked"]`. Both will break when ST-013 and ST-018 ship.
Update the E2E test in the same PR as ST-013+ST-018.

---

## PHASE 3 — EXECUTION PROTOCOL

Execute tasks in this priority order: P0 → P1 → P2 → P3 → P4.
Complete one task fully before starting the next.

### For every task:

**Step 1 — Verify (don't assume)**
Open the specific file. Confirm the described issue is present.
If the issue is not there, mark the task SKIP and document why — do not write a fix.
Confirmed bugs (no verification needed): ST-002, ST-003, ST-007, ST-010, ST-011,
ST-013, ST-017, ST-018. Everything else: verify before touching.

**Step 2 — Write the test first (Constitution Rule 20, non-negotiable)**
Write the named test function first. Run it. Confirm it FAILS for the right reason.
Test naming: `test_<what>_when_<condition>_then_<expected>` (Constitution Rule 7).
For React/frontend: Jest + React Testing Library. Write failing test, then implement.
For backend tasks: pytest. Named unit + integration tests, mocks defined.
Service file coverage must be ≥ 90% before any PR (Constitution Rule 6).

**Step 3 — Implement**
Make the minimum change that passes the test.
Constitution rules that always apply:
- Rule 1: service layer owns all logic — routes are thin
- Rule 4: all LLM calls through `router.complete()` — never import provider SDKs
- Rule 7: test naming convention
- Rule 8: schema is source of truth
- Rule 16: read DESIGN_SYSTEM.md before any component
- Never use raw `gray-*` Tailwind classes — use design tokens
- Never use `font-fraunces` or `font-nunito` — use `font-display` and `font-sans`
- `isPending` not `isLoading` for React Query v5 (confirmed relevant in ST-010)

**Step 4 — Verify acceptance criteria**
Each acceptance criterion checked explicitly, not assumed.

**Step 5 — Commit, push, PR, self-review**
```bash
git add -A
git commit -m "ST-XXX: <title>"
git push origin <branch>
gh pr create --title "ST-XXX: <title>" --body "What changed and why"
```
Self-review the diff: any untouched-file changes? any coverage drop? any
raw gray values? any cross-app boundary violations?

**Step 6 — Wait for CI**
CI green (or actionable failure resolved) before starting the next task.
Do not merge. Merging is a human action.

---

## PHASE 4 — TASK-SPECIFIC NOTES

Tasks already verified against actual code. Apply these notes during execution.

**ST-001 (stale closure in handleSubmitRequest)**
Before fixing, read `TakeAssessmentPage.tsx`. Confirm `doSubmit` is itself a
`useCallback` with `answers` in its deps. If `doSubmit` is not memoised,
add `useCallback` to `doSubmit` first, then add it to `handleSubmitRequest`'s
deps. A non-memoised `doSubmit` in the deps array creates an unstable reference
on every render — both must be stable.

**ST-003 (replace useOnboardingStatus with useQuery)**
After replacing: `grep -r "useOnboardingStatus" apps/student/src packages/`
Every consumer calling `.isLoading`, `.status`, `.error`, `.refetch` must be
updated to the useQuery return shape (`isPending`, `data`, `isError`, `refetch`).
`OnboardingRouter.tsx` uses `{ status, isLoading }` from this hook — update that
destructuring too. Partial migration causes runtime errors.

**ST-005 (parallel refetch + weakest-area fix)**
See PHASE 2 KNOWN SPEC ERRORS above. Do not change `buildNextSteps` signature.
Fix the `gapMapQuery` to remove the hardcoded `[0]` first-class fetch.
Fix the weakest-area logic inside the existing function.

**ST-006 (ProfileQuestionnaire dual step state)**
Before removing `currentStep` from questionnaireStore, run:
`grep -r "useQuestionnaireStore" apps/student/src`
Confirm zero other consumers of `currentStep`, `nextStep`, `prevStep`.
If other consumers exist, update them in the same PR.

**ST-008 (OnboardingRoute gate fix)**
Target: `packages/auth/src/guards.tsx` `isOnboardingComplete()` only.
Do not touch `OnboardingRouter.tsx` — already correct.
Update `frontend/e2e/diagnostic-gate.spec.ts` in the same PR:
- Remove `[aria-label="Locked"]` selector (changes with ST-018)
- Remove `'Complete diagnostic to unlock'` text (changes with ST-018)
- Replace with the post-ST-018 framing: `Begin [subject] →`

**ST-013 + ST-018 — ship together, same branch**
These must be one PR. Both touch `StudentLayout.tsx` and `ClassCard.tsx`.
After ST-018 removes the Lock icon and opacity-60, the only locked/unlocked
visual distinction is the CTA text ("Begin [Subject] →" vs "View class →").
The ST-013 aria-label must say "tap to begin your diagnostic", not lock language.
Update `frontend/e2e/diagnostic-gate.spec.ts` here too (see ST-008 note).

**ST-019 (merge duplicate hooks)**
Before deleting `useSubjectGapMap` from `useSubjectScores.ts`:
`grep -r "useSubjectGapMap" apps/student/src packages/`
All import sites updated in the same commit. Do not delete an export with
remaining importers — causes a build failure.

**ST-020 (AI Concept Guide)**
Read `plans/student/kaihle-concept-guide-architecture.md` in full before starting.
Pre-checks before any frontend work:
1. Open `backend/app/api/v1/routes/onboarding.py`. Find `GET /students/me/learning-profile`.
   If its body is a stub (returns hardcoded data or raises NotImplementedError), stop.
   Flag to human: this endpoint must return real `student_learning_profiles` data
   before ST-020 can ship. Implementing the stub is a prerequisite.
2. Open `backend/app/ai/providers/router.py`. Confirm `"concept_guide"` is not yet
   in `TASK_MODEL_MAP`. Add it per the architecture doc before writing the backend handler.
3. `interests` field in `student_learning_profiles` is `TEXT[]` — already human-readable
   (e.g. `["football", "music"]`). Do NOT add any enum mapping. Pass directly.

**ST-023 (extract useStudentLayoutProps)**
The 15-line boilerplate is confirmed in at minimum:
- `StudentSettings.tsx`
- `Assessments.tsx`
- `StudentDashboard.tsx`
Grep for all files before writing the hook to know the full list of consumers.
The hook must return `isPending` from both underlying queries (see task file).

---

## PHASE 5 — BRANCH STRATEGY

Established dependency chains from reading actual code:

```
main ──→ ST-003  (useOnboardingStatus → useQuery)
          └──→ ST-008  (depends on clean onboarding status hook)

main ──→ ST-013 + ST-018  (same branch — lock framing, must ship together)
          includes: update frontend/e2e/diagnostic-gate.spec.ts

main ──→ ST-005  (dashboard fix — buildNextSteps weakest-area)
          └──→ ST-007  (useCallback on handleScoresResolved — same file)

main ──→ ST-019  (merge duplicate hooks)
          └──→ ST-023  (extract useStudentLayoutProps — do after hooks consolidated)
               └──→ ST-025  (tests for new hook)

All P0 quick fixes branch from main independently:
  ST-001, ST-002, ST-004, ST-006, ST-009, ST-010, ST-011, ST-012, ST-015
```

Branch naming: `student/ST-XXX-short-description`

---

## PHASE 6 — OUTPUT FORMAT

After each task:

```
✓ ST-XXX — <title>
  Verified:   <what you confirmed existed in the actual code before touching it>
  Test:       <test function name(s) written>
  Files:      <list of files changed>
  Acceptance: <each criterion — pass / fail>
  PR:         student/ST-XXX-description → #<number>
  CI:         pending / green / failed (<reason>)
  Notes:      <deviations from spec, discoveries, flags for human>
```

If skipped:
```
— ST-XXX — SKIPPED
  Reason:   <not found in file — what you actually found instead>
  Verified: grep <command> showed <result>
```

---

## HARD STOPS — pause and report to human if:

- Any confirmed bug is not present where the task says it is
- `GET /students/me/learning-profile` returns stub data (blocks ST-020)
- Any task requires touching `apps/teacher/`, `apps/parent/`, `apps/school-admin/`,
  or `apps/kaihle-admin/` — student tasks must not cross app boundaries
- Any change would modify a frozen API contract (check API_ENDPOINT_TASK_MAP.md)
- CI failure cannot be resolved within the scope of the task

---

Begin Phase 0. No code until all files are read.
