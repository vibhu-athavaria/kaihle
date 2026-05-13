# Kaihle Student App — Task Board v2
> Supersedes v1. Cross-review pass by Kramer (engineering) · Pixel (design/UX) · Vidhya (pedagogy) — each persona reviewed their own sections and each other's.
> 13 issues found and corrected in v2: import merges, vague agent instructions, missing type mapping, MCQ spec, copy accuracy, conditional CTA logic.
> Kaihle is curriculum-agnostic — topics and subtopics drive all AI features, not any specific framework.

---

## Strategic Context — What Makes Kaihle Matter for Students

**The honest diagnosis:** Kaihle's student app is currently a progress tracker, not a learning tool. Students complete a diagnostic, see their gap map, and then hit a wall. The three pages that should drive daily engagement — Study Plans, Assessments, My Progress actions — are either empty placeholders or read-only displays. There is no step a student can take independently to get better.

**What needs to change, in priority order:**

**1. Close the loop between gap and action.** The gap map shows a student they're at 31% in Simultaneous Equations. Right now, nothing happens. The highest-leverage thing Kaihle can do is surface an immediate "work on this now" pathway directly from that gap data. Whether that's a study session, an AI concept explainer, or a curated practice sequence — the student must be able to act without waiting for a teacher.

**2. Build the AI Concept Guide (not generic chat).** Kaihle has uniquely valuable context: this specific student, their mastery on this specific subtopic, their learning style, their interests. A generic AI chatbot ignores all of this. The Concept Guide should be triggered from within the Gap Map or study plan — not a global chat bubble. It uses stored context to explain a specific subtopic at the student's level, in their preferred modality, with examples drawn from their interests. It asks a check question to verify understanding before moving on. This is defensible pedagogically (Socratic, bounded) and safer for 11–18 year olds than open-ended chat.

**3. Make the learning profile visibly affect the experience.** Students completed a 5-step questionnaire. If they cannot see their visual/auditory/kinesthetic preference reflected in the content they receive, they will conclude the questionnaire was theater. The learning profile must surface in: study plan activity style, concept guide approach, and ideally the student's own settings page showing "this is how Kaihle is personalising for you."

**4. Fix the diagnostic gate logic.** Blocking a student from seeing their Maths assessment results because their Science diagnostic is incomplete is a retention killer. Each class should unlock independently.

---

## Architecture Decisions (locked)

**Student sidebar nav items:**
```
LEARN
  Home          → /student/dashboard       active dot
  My progress   → /student/my-progress     BarChart2
  Study plans   → /student/study-plans     BookOpen
  Assessments   → /student/assessments     ClipboardList

CLASSES (dynamic, per enrolled class)
  [ClassName]   → /student/classes/:id/topics (unlocked)
              OR /student/assessments/:diagnosticAttemptId/take (locked)

ACCOUNT (sidebar bottom — profile card + logout)
```

**Student layout:** Custom `StudentLayout` in `packages/ui` (not `DashboardLayout`). This is correct — do not change.

**Gap map endpoint:** `GET /api/v1/students/me/gap-map?subject_id=` — never construct student ID in URLs.

**Learning profile endpoint:** `GET /api/v1/onboarding/learning-profile` — used in Settings. Should also be used by AI Concept Guide to personalise explanations.

**AI Concept Guide context payload (planned):**
```json
{
  "student_id": "me",
  "subtopic_id": "uuid",
  "mastery_score": 0.28,
  "learning_style": "visual",
  "interests": ["football", "music"],
  "curriculum_topic": "Solving simultaneous equations by substitution"
}
```

---

## 🔴 P0 — Critical Bugs (fix before any other work)

---

### ST-001 · Stale closure in handleSubmitRequest — wrong answers can be submitted
**File:** `src/pages/assessments/TakeAssessmentPage.tsx`

**Problem:**
```ts
const handleSubmitRequest = useCallback(() => {
  const unanswered = totalQuestions - answeredCount;
  if (unanswered > 0) {
    setShowSubmitModal(true);
  } else {
    void doSubmit();
  }
}, [answeredCount, totalQuestions]); // eslint-disable-line react-hooks/exhaustive-deps
```
`doSubmit` depends on `answers` — a new reference every time a student selects an option. `handleSubmitRequest` holds a stale `doSubmit` from the last render where `answeredCount` or `totalQuestions` changed. On "Submit anyway" from the modal, the stale `doSubmit` runs with old `answers`. This is a real data integrity bug.

**Fix:**
```ts
const handleSubmitRequest = useCallback(() => {
  const unanswered = totalQuestions - answeredCount;
  if (unanswered > 0) {
    setShowSubmitModal(true);
  } else {
    void doSubmit();
  }
}, [answeredCount, totalQuestions, doSubmit]); // doSubmit included — no eslint-disable needed
```

Also the Submit modal's confirm button calls `doSubmit` directly — this is fine since `doSubmit` is in scope via closure at render time.

**Acceptance:** ESLint exhaustive-deps warning gone. Submitting via modal and direct submit both use the current answers state.

---

### ST-002 · ClassCard — two silent rendering bugs
**File:** `src/components/ClassCard.tsx`

**Problem 1 — `ffont-sans` (double f):**
```tsx
// Line ~58
<div className="ffont-sans text-card-meta text-brand-body mb-">
```
`ffont-sans` is not a Tailwind class. The Nunito font will not be applied. Body text renders in browser default.

**Problem 2 — `mb-` (no value):**
Same line. `mb-` is not a valid Tailwind class. The margin between meta text and the CTA footer is zero — content appears cramped.

**Fix:**
```tsx
<div className="font-sans text-card-meta text-brand-body mb-2">
```
`mb-2` (8px) gives the meta line appropriate breathing room above the CTA footer.

**Acceptance:** ClassCard meta text renders in Nunito. Correct gap between meta and CTA.

---

### ST-003 · useOnboardingStatus — loading state can get permanently stuck
**File:** `src/hooks/useOnboardingStatus.ts`

**Problem:**
The hook manually manages loading state with a `useRef` flag. If the initial fetch fails and `refetch()` is called:
- `isInitialFetch.current` is already `false` → `setIsLoading(true)` never runs
- `finally` block only calls `setIsLoading(false)` when `!isRefetch`
- The component stays in whatever loading state it was in, permanently out of sync

Additionally, `fetchStatus` is defined outside `useEffect` without `useCallback`, so technically it's a new function reference every render and should be in the dependency array.

**Fix — replace with useQuery:**
```ts
import { useQuery } from "@tanstack/react-query";
import { apiClient, useAuth } from "@kaihle/auth"; // merged — was two separate lines in v1

export function useOnboardingStatus() {
  const { user } = useAuth();

  return useQuery<OnboardingStatus>({
    queryKey: ["student", "onboarding-status", user?.id],
    queryFn: async () => {
      const res = await apiClient.get<OnboardingStatus>(
        `/api/v1/onboarding/status/${user!.id}`,
      );
      return res.data;
    },
    enabled: !!user?.id,
    staleTime: 30 * 1000, // 30s — re-check frequently during onboarding
    refetchOnWindowFocus: true, // refetch when student tabs back in (was manual before)
  });
}
```

Update all consumers: replace `status`/`isLoading`/`error`/`refetch` destructuring with `data`/`isPending`/`isError`/`refetch` from useQuery.

**Acceptance:** Loading state always reflects actual fetch state. Window focus re-fetch works without manual event listener. No `useRef` flag.

---

### ST-004 · AccountSection — unused useAuth() call
**File:** `src/components/settings/AccountSection.tsx`

**Problem:**
```tsx
export function AccountSection() {
  useAuth(); // ← result is never used
  const queryClient = useQueryClient();
```
Calling a hook for its side effects is a React anti-pattern and confuses future readers about what state is being used.

**Fix:** Remove the `useAuth()` call entirely. If auth state is needed later, add it back with proper destructuring.

**Acceptance:** No unused hook calls. ESLint `no-unused-vars` would catch this if enabled for hooks.

---

### ST-005 · useStudentDashboard — sequential refetch and single-class gap map
**File:** `src/hooks/useStudentDashboard.ts`

**Problem 1 — Sequential refetch:**
```ts
refetch: async () => {
  await gapMapQuery.refetch();     // serial — waits for each
  await studyPlansQuery.refetch();
  await assessmentsQuery.refetch();
  await studentInfoQuery.refetch();
},
```
Four serial requests. On mobile, 4–8 seconds. Should be parallel.

**Fix:**
```ts
refetch: async () => {
  await Promise.all([
    gapMapQuery.refetch(),
    studyPlansQuery.refetch(),
    assessmentsQuery.refetch(),
    studentInfoQuery.refetch(),
  ]);
},
```

**Problem 2 — Gap map hardcoded to first enrolled class:**
```ts
const primarySubjectId = studentInfoQuery.data?.enrolledClasses?.[0]?.subjectId;
```
A student in Maths + Science only ever gets Maths gap data on the dashboard. The `buildNextSteps` "weakest area" logic is wrong for any student with more than one subject.

**Fix — use the subject with the lowest mastery across all enrolled classes:**

Do NOT add a second parallel gap-map fetch. The `SubjectScoresSection` already fetches per-subject gap maps and resolves them into `resolvedSubjectScores`. Wire that directly:

```ts
// useStudentDashboard.ts
// REMOVE: the single primarySubjectId gap-map query entirely
// REMOVE: const primarySubjectId = studentInfoQuery.data?.enrolledClasses?.[0]?.subjectId;

// The dashboard component already receives resolvedSubjectScores via handleScoresResolved (ST-007).
// Update buildNextSteps to accept ResolvedSubjectScore[] instead of a single gap map:

export function buildNextSteps(resolvedScores: ResolvedSubjectScore[]): NextStep[] {
  if (!resolvedScores.length) return [];
  // Find the subject with lowest average mastery
  const weakest = resolvedScores.reduce((a, b) =>
    (a.averageMastery ?? 1) <= (b.averageMastery ?? 1) ? a : b
  );
  // Return next steps based on weakest subject's gap data
  return weakest.weakSubtopics?.slice(0, 3).map(s => ({
    subtopicId: s.id,
    subtopicName: s.name,
    subjectName: weakest.subjectName,
    masteryScore: s.masteryScore,
  })) ?? [];
}
```

**Acceptance:** Refetch is parallel. `buildNextSteps` receives all subject scores. Weakest-area logic considers all enrolled subjects. No duplicate gap-map fetch alongside `SubjectScoresSection`.

---

### ST-006 · ProfileQuestionnaire — dual currentStep state and hardcoded store cap
**File:** `src/pages/onboarding/ProfileQuestionnaire.tsx`, `src/store/questionnaireStore.ts`

**Problem 1 — Two separate step states can diverge:**
Local state `currentStep` and `useQuestionnaireStore().currentStep` are incremented separately. If the store resets or the component remounts, local step does not reset with it.

**Problem 2 — Store caps at hardcoded 6:**
```ts
// questionnaireStore.ts
nextStep: () => set((state) => ({ currentStep: Math.min(state.currentStep + 1, 6) })),
```
The API returns a dynamic `questions.length`. If a curriculum's learning profile has 7+ questions, the store prevents reaching the final question.

**Fix — use a single source of truth:**
Remove `currentStep` from the Zustand store entirely. The questionnaire is a single-session flow; local React state is sufficient and simpler.

```tsx
// ProfileQuestionnaire.tsx
const [currentStep, setCurrentStep] = useState(1);

// Remove: nextStep, prevStep from store
// Remove: store.currentStep field
// totalQuestions from API: const totalQuestions = questionnaire?.questions.length ?? 0;

const goNext = () => setCurrentStep(s => Math.min(s + 1, totalQuestions));
const goPrev = () => setCurrentStep(s => Math.max(s - 1, 1));
```

Also update `questionnaireStore.ts` to remove `currentStep`, `nextStep`, `prevStep` — they're unused once `ProfileQuestionnaire` manages its own step.

**Before removing store fields:** Search ALL files for `useQuestionnaireStore()` and confirm no other component reads `currentStep` or calls `nextStep`/`prevStep`. If any other consumer exists, it must be updated in the same PR. Do not remove store fields without confirming zero remaining consumers.

**Acceptance:** One step counter. Dynamic question count works for any number of questions. No hardcoded cap. Zero remaining references to `store.currentStep`, `store.nextStep`, `store.prevStep`.

---

### ST-007 · SubjectScoresSection — onScoresResolved causes re-render loop risk
**File:** `src/pages/dashboard/StudentDashboard.tsx`

**Problem:**
```tsx
// StudentDashboard.tsx — not memoized
const handleScoresResolved = (scores: ResolvedSubjectScore[]) => {
  setResolvedSubjectScores(scores);
};

// SubjectScoresSection.tsx — onScoresResolved in dep array
useEffect(() => {
  if (!onScoresResolved || hasCalledCallback) return;
  // ...
  onScoresResolved(resolvedScores);
}, [resolvedScores, subjects, onScoresResolved, hasCalledCallback]);
```
Every render of `StudentDashboard` creates a new `handleScoresResolved` reference → triggers the effect → `setResolvedSubjectScores` → re-render → repeat. `hasCalledCallback` prevents infinite API calls but not infinite effect runs.

**Fix:**
```tsx
// StudentDashboard.tsx
const handleScoresResolved = useCallback((scores: ResolvedSubjectScore[]) => {
  setResolvedSubjectScores(scores);
}, []); // stable reference — no deps needed
```

**Acceptance:** `handleScoresResolved` reference is stable. `useEffect` in SubjectScoresSection runs only when `resolvedScores` or `subjects` actually change.

---

### ST-008 · OnboardingRoute — blocks all results if any single diagnostic is incomplete
**File:** `packages/auth/src/guards.tsx`

**Problem:**
```ts
function isOnboardingComplete(status: OnboardingStatus): boolean {
  if (!status.learning_profile_complete) return false;
  // ALL diagnostics must be COMPLETED — even unrelated classes
}
```
A student with Maths (COMPLETED) and Science (PENDING) cannot view their Maths assessment results. This is a retention-killing product decision masquerading as a guard.

**Fix — learning profile gate only. Diagnostic status is per-class, not global:**
```ts
function isOnboardingComplete(status: OnboardingStatus): boolean {
  // Only gate on learning profile — diagnostic lock is handled per-class by ClassCard
  return status.learning_profile_complete === true;
}
```

The per-class diagnostic lock already exists in `ClassCard` and `StudentLayout`. `OnboardingRoute` should only enforce the learning profile gate. Everything else is class-level, not global.

**Before shipping:** Verify in code that `ClassCard` correctly shows a locked/diagnostic state for classes with `diagnosticStatus !== "COMPLETED"`. The global gate removal assumes per-class locking is already reliable. If in doubt, add a test.

**Acceptance:** Student who completes their learning profile can access Take/Results pages for any diagnostic they've completed, regardless of other classes' diagnostic status.

---

### ST-009 · identity-obj-proxy missing from devDependencies
**File:** `apps/student/package.json`

**Problem:**
`jest.config.js` maps all CSS imports to `identity-obj-proxy` but it's not in `devDependencies`. Works locally if installed globally or via hoisting, fails in clean CI environments.

**Fix:**
```json
"devDependencies": {
  "identity-obj-proxy": "^3.0.0",
  ...
}
```

---

### ST-010 · React Query v5 — isPending vs isLoading for disabled queries
**File:** `src/hooks/useStudentDashboard.ts`

**Problem:**
`studyPlansQuery` is only enabled when `isEnrolled === true`. Until enrollment is confirmed:
- `studyPlansQuery.isLoading` is `false` (disabled query)
- `studyPlansQuery.isPending` is `true` (hasn't fetched yet)

The dashboard checks `studyPlansQuery.isLoading` for the skeleton. Unenrolled or pending-enrollment students never see the loading skeleton for study plans — the section flickers from nothing to empty.

**Fix:** Replace `isLoading` with `isPending` throughout `useStudentDashboard.ts`. In React Query v5, `isPending` correctly reflects "has no data yet" for both enabled and disabled queries.

---

## 🟠 P1 — Design System Compliance

---

### ST-011 · Settings page — wrong font tokens and raw gray values throughout
**Files:** `src/components/settings/AccountSection.tsx`, `AccountActionsSection.tsx`, `LearningProfileSection.tsx`, `src/pages/settings/StudentSettings.tsx`

**StudentSettings.tsx:**
```tsx
// Current — missing font-bold
<h1 className="font-display text-2xl text-brand-ink mb-6">Settings</h1>

// Fixed
<h1 className="font-display font-bold text-2xl text-brand-ink mb-6">Settings</h1>
```

**All three settings components — replace raw values with design tokens:**

| Replace | With |
|---|---|
| `border-gray-100` | `border-brand-border` |
| `border-gray-50` | `border-brand-border` |
| `shadow-sm` | `shadow-card` |
| `bg-gray-50/50` | `bg-brand-bg/50` ⚠️ keep the `/50` opacity — this is semi-transparent, not solid |
| `text-gray-400` | `text-brand-muted` |
| `text-gray-500` | `text-brand-body` |
| `text-gray-700` | `text-brand-ink` |
| `bg-gray-100` | `bg-brand-border-soft` |
| `bg-gray-200` | `bg-brand-border` |
| `font-fraunces` | `font-display` |
| `font-nunito` | `font-sans` |
| `border-gray-200` | `border-brand-border` |
| `text-gray-600` | `text-brand-body` |

This applies to every `className` string in all three files. The settings page must match the visual language of the rest of the student app.

**Acceptance:** Settings page uses zero raw `gray-*` Tailwind classes. Visual diff before/after is subtle but consistent.

---

### ST-012 · LearningProfileSection — fix duration-600 (non-existent Tailwind class)
**File:** `src/components/settings/LearningProfileSection.tsx`

**Problem:**
```tsx
className={`h-full rounded-full transition-all duration-600 ease-out ${...}`}
```
`duration-600` is not in Tailwind's default scale. Bars animate instantly (browser default 0ms).

**Fix:**
```tsx
className={`h-full rounded-full transition-all duration-500 ease-out ${...}`}
```

**Acceptance:** Modality bars animate smoothly over 500ms when the settings section loads.

---

### ST-013 · Locked class sidebar items — add accessible aria-label
**File:** `packages/ui/src/layouts/StudentLayout.tsx`
**Ships with ST-018** — do not ship ST-013 alone. The aria-label text must match the visual framing change in ST-018.

**Problem:** Screen reader users hear only the class name (e.g. "Science 9A") with no indication that clicking starts a diagnostic, not class content.

**Fix — aria-label uses "begin" language, consistent with ST-018 (no lock metaphor):**
```tsx
<Link
  key={cls.id}
  to={route}
  aria-label={
    isLocked
      ? `${cls.name} — tap to begin your diagnostic`
      : cls.name
  }
  className={[...]}
>
```

Note: "start diagnostic to unlock" is the OLD framing. After ST-018 ships, the diagnostic is the starting point, not a gate. The aria-label must match.

**Acceptance:** Screen readers announce the diagnostic action using invitation language, not lock language. Sighted users are unaffected.

---

### ST-014 · Fix hardcoded "Suggested next steps" amber box on My Progress
**File:** `src/pages/my-progress/MyProgress.tsx`

**Problem:**
The amber "Suggested next steps" box appears even when `topics.length > 0` (student has full mastery data). It shows "Complete more assessments to see personalized recommendations" — which is false and demotivating for students who have assessed.

**Fix — conditional render, only when no data:**
```tsx
{topics.length === 0 && (
  <div className="bg-brand-amber-light border border-brand-amber/30 rounded-xl p-4 mt-6">
    <p className="font-sans text-sm text-brand-amber">
      Take your first assessment to start seeing topic-by-topic progress here.
    </p>
  </div>
)}
```

When `topics.length > 0`, remove the box entirely for this milestone. The real "next steps" content will come from the AI Concept Guide (ST-024).

**Acceptance:** Amber box only appears when student has no topic data. Students with mastery data do not see it.

---

### ST-015 · NextStepCard — add type="button"
**File:** `src/pages/dashboard/NextStepCard.tsx`

**Problem:**
```tsx
<button onClick={onAction} className="...">
```
Missing `type="button"`. Default button type in HTML is `submit`. Defensive coding requires explicit type on all buttons.

**Fix:**
```tsx
<button type="button" onClick={onAction} className="...">
```

---

## 🟡 P2 — Empty States with Actionable Guidance

---

### ST-016 · Study Plans page — replace static placeholder with actionable empty state
**File:** `src/pages/study-plans/StudyPlans.tsx`

**Problem:** Students see "Your study plans will appear here once your teacher assigns them." — dead end, no agency.

**Fix — two-state empty state:**

When no diagnostic completed yet:
```tsx
<div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
  <p className="font-display font-bold text-brand-ink mb-2">No study plans yet</p>
  <p className="text-sm text-brand-muted mb-4">
    Study plans are built automatically from your assessment results —
    personalised to the specific topics where you have gaps.
    Complete your first assessment to unlock them.
  </p>
  <Link
    to="/student/assessments"
    className="text-sm font-semibold text-brand-primary hover:text-brand-dark
               focus-visible:ring-2 focus-visible:ring-brand-primary rounded"
  >
    View your assessments →
  </Link>
</div>
```

When diagnostics are complete but no study plans assigned yet:
```tsx
<div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
  <p className="font-display font-bold text-brand-ink mb-2">Plans are being generated</p>
  <p className="text-sm text-brand-muted mb-4">
    Your study plans are being built from your assessment results.
    They'll appear here soon — in the meantime, explore your progress to see where to focus.
  </p>
  <Link to="/student/my-progress" className="text-sm font-semibold text-brand-primary ...">
    View my progress →
  </Link>
</div>
```

Note: Do NOT say "your teacher is reviewing your gap data" — study plans are AI-generated automatically from diagnostic results, not manually assigned by teachers.

The component needs to know which state to show — add `hasDiagnosticComplete` derived from `useMyClasses()`.

---

### ST-017 · Assessments page — replace static placeholder with actionable empty state
**File:** `src/pages/assessments/Assessments.tsx`

Same pattern as ST-016. Two states:

**No diagnostic attempt exists:**
```tsx
<p className="text-sm text-brand-muted mb-4">
  Your teacher will assign assessments here once you are enrolled.
  These help build your personalised gap map so Kaihle knows exactly where to focus.
</p>
```

**Diagnostic exists, no teacher assessments yet:**
```tsx
<p className="text-sm text-brand-muted mb-4">
  No assessments assigned yet. Your teacher will share them here when ready.
</p>
<Link to="/student/my-progress">
  See your progress so far →
</Link>
```

---

## 🔮 P3 — Strategic Features (Next Sprint)

---

### ST-018 · Fix diagnostic framing — remove lock metaphor from student-facing UI
**Files:** `src/components/ClassCard.tsx`, `packages/ui/src/layouts/StudentLayout.tsx`

**Vidhya's recommendation:** The lock + reduced opacity communicates "you failed to unlock this" rather than "this is your starting point." The diagnostic is not a barrier — it's the foundation. Reframe:

**ClassCard.tsx:**
```tsx
// Replace:
<span className="flex items-center gap-1">
  <Lock className="w-3 h-3" aria-hidden="true" />
  Start diagnostic →
</span>

// With:
<span>Begin [subjectName] →</span>
```

Remove `opacity-60` on locked cards. The card should look inviting, not disabled.

**Important:** With `opacity-60` and the Lock icon removed, the ONLY visual distinction between a locked and unlocked class is the CTA text: unlocked shows "View class →" while locked shows "Begin [subjectName] →". This is intentional — the affordance lives in the CTA label, not in disabling the card. Confirm both locked and unlocked CTA labels are set correctly in the same PR. Do not remove opacity without verifying the CTA text change is also in place.

**StudentLayout.tsx sidebar:**
Replace `<Lock />` icon on locked classes with a `PlayCircle` or similar "start" icon. Remove `text-brand-gold` color differentiation for locked items (gold = developing, not locked — this color carries a different semantic meaning elsewhere).

**Acceptance:** Students see locked classes as "ready to start" not "inaccessible." Teacher-facing gap data still shows diagnostic status correctly — this is student UI only.

---

### ST-019 · Merge duplicate useSubjectGapMap hooks
**Files:** `src/hooks/useStudentGapMap.ts`, `src/hooks/useSubjectScores.ts`

Both files export `useSubjectGapMap` with identical query keys and endpoints. Both are used in different parts of the app. They share the React Query cache (same key) so there's no data duplication — but two files with the same name doing the same thing is confusing.

**Fix:** Keep `useStudentGapMap.ts` (more descriptive return type `StudentGapMap`). Delete `useSubjectGapMap` from `useSubjectScores.ts`.

**Before deleting:** Run `grep -r "useSubjectGapMap" apps/student/src packages/` and update ALL found import sites, not just `SubjectScoresSection.tsx` and `StudentDashboard.tsx`. Do not delete the export until zero import sites remain.

Keep `aggregateSubjectMastery` in `useSubjectScores.ts` — do not move it to `@kaihle/types` unless it is already exported from there.

**Acceptance:** `useSubjectGapMap` export removed from `useSubjectScores.ts`. Zero remaining imports of `useSubjectGapMap` from `useSubjectScores`. All consumers now import from `useStudentGapMap`.

---

### ST-020 · AI Concept Guide — architecture and first implementation
**Files:** New — `src/components/ai/ConceptGuidePanel.tsx`, `src/hooks/useConceptGuide.ts`
**Architecture doc:** See `kaihle-concept-guide-architecture.md` — full backend endpoint spec, LLM routing, data flow, and errata from this task file.
**Note:** This is a panel component, not a page. It renders as an inline right-side panel within the current view (My Progress, Study Plan activity). There is no route change when the Guide opens. Aligns with SP-004 in `kaihle_lesson_study_tasks_v1.md` — both tasks define the same component. Use SP-004 as the implementation spec; ST-020 defines where it's surfaced.

**Strategic framing:** This is the highest-leverage feature Kaihle can build for students. It transforms Kaihle from "shows you where you're stuck" to "helps you get unstuck." The uniqueness is the context — Kaihle knows this student's mastery, learning style, and interests. Generic AI tutors don't.

**How it works:**
1. Student taps a subtopic cell in their gap map (or a topic row in My Progress)
2. A panel opens (not a full page navigation — keep context)
3. The AI explains the concept at the student's level using their preferred modality
4. AI asks one check question
5. Student answers → AI acknowledges and either goes deeper or suggests they're ready to practice

**Context sent to AI (from existing data):**
```ts
interface ConceptGuideContext {
  subtopicName: string;         // e.g. "Solving simultaneous equations by substitution"
  subtopicId:   string;         // UUID — sent to backend
  topicName:    string;         // e.g. "Algebra" — from gap map response
  masteryScore: number | null;  // 0.0–1.0 — already in SubtopicScoreRow props
  gradeName:    string;         // e.g. "Grade 9" — from useStudentInfo()
}
// NOTE: interests and learningStyle are NOT sent from the frontend.
// The backend loads them directly from student_learning_profiles in one DB query.
// student_learning_profiles.interests is TEXT[] e.g. ["football", "music", "gaming"]
// — already human-readable. No enum mapping exists or is needed.
```

⚠️ The v2 cross-review pass incorrectly introduced an interestCategory enum and INTEREST_LABELS mapping.
This was wrong — interests are stored as free-text TEXT[] in the schema, not as an enum.
See kaihle-concept-guide-architecture.md for the full corrected data model.

**System prompt pattern:**
```
You are a patient, encouraging tutor helping a Grade {gradeName} student 
understand "{subtopicName}". 

Their current mastery level is {masteryPct}% — treat them as a learner 
who has encountered this concept but has gaps, not a complete beginner 
or an expert.

Their dominant learning style is {learningStyle}. Adapt your explanation:
- visual: use spatial descriptions, diagrams described in text, step-by-step 
  visual walkthrough
- auditory: use rhythm and pattern ("first... then... finally...")
- reading_writing: structured lists, clear definitions, written examples
- kinesthetic: real-world application first, then theory

Their interests include: {interest_text}. Where it fits naturally, frame one
example using this context. Do not force it.
(Note: interest_text = profile.interests[:2] joined — loaded by backend, not sent from frontend)

Rules:
- Explain the concept only. Do not solve homework problems or write essays.
- Do not engage with questions unrelated to "{subtopicName}". If asked 
  anything off-topic, respond: "I'm here to help you understand {subtopicName} 
  — let's stay focused on that."
- After your explanation, ask ONE multiple choice check question with exactly 
  4 options (A, B, C, D). Return it as JSON:
  {"question": "...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "correct": "B"}
- If they answer correctly, say so warmly and suggest they try an assessment.
- If they answer incorrectly, re-explain from a different angle. Never say "wrong."
- Keep responses concise — this is a mobile app for a student, not a lecture.
```

**Error handling — required:** Wrap the API call in try-catch. On error display: "Something went wrong loading the guide. Please try again." Do not leave the panel in a blank loading state.

**Where to surface it:**
- `MyProgress.tsx` — "Explain this →" text link below each subtopic in `SubtopicScoreRow` where `masteryScore < 0.7` only. Do NOT show on mastered subtopics (≥ 0.7).
- `StudentDashboard.tsx` — from the weakest-area NextStepCard action
- `AssessmentResultsPage.tsx` — "Why did I get this wrong?" (future — requires question-level data)

**Acceptance:** Student can tap any subtopic → panel opens → AI explains → AI asks MCQ check question (4 options, JSON format) → student selects option → AI responds. AI never generates assignment answers. try-catch in place. Session is not persisted (single-session only for M1 of this feature).

---

### ST-021 · Make learning profile visibly affect the experience
**Files:** `src/components/settings/LearningProfileSection.tsx`, study plan components (future)

Currently the learning profile is shown in Settings as a read-only display. Students can retake it. But they have no way to see HOW it affects what they receive.

**Fix for this milestone — add a visible "how this shapes your experience" explainer:**
```tsx
// Below the modality bars in LearningProfileSection
<div className="px-6 pb-4">
  <p className="font-sans text-xs text-brand-muted">
    Kaihle uses your learning profile to personalise how the AI Concept 
    Guide explains topics to you.
  </p>
</div>
```
Note: Do NOT reference "study activities" — personalised activity styles are not yet live. Scope the copy to only what is actually built: the Concept Guide. Expand the copy in a future sprint once activity personalisation ships.

**Larger fix (future sprint):** Each study plan activity card should display a small tag indicating why it was selected: `"Visual activity · based on your profile"`. This closes the loop between questionnaire input and visible output.

---

### ST-022 · Student-initiated study sessions from Gap Map
**Files:** `src/pages/my-progress/MyProgress.tsx`, new `src/pages/study-plans/StudyPlans.tsx`

**Vidhya's recommendation:** Students should not need teacher approval to practice a topic they know they're struggling with. The gap map shows them exactly what to work on. Add an "Explain this →" text link on `SubtopicScoreRow` that opens the AI Concept Guide panel inline. Render as: `<button type="button" className="text-xs font-semibold text-brand-primary">Explain this →</button>`.

**Mastery condition — required:** Only render "Explain this →" when `masteryScore < 0.7`. Students at Strong mastery (≥ 0.7) do not need an explanation — showing it implies they're struggling when they're not. For ≥ 0.7 subtopics, render nothing (future sprint: "Challenge yourself →").

Label is **"Explain this →"** (not "Practice this") — the Concept Guide explains, it doesn't drill. Students who tap this don't understand something; the first thing they need is an explanation.

For this milestone, "Explain this →" opens `ConceptGuidePanel` (ST-020 / SP-004) for that specific subtopic, pre-loaded with the student's mastery + learning style + interest context. In a future sprint, a separate "Practice →" button triggers a 5-question auto-graded practice set.

---

### ST-023 · Decouple duplicate imports across student pages
**Files:** Multiple student page files

Every page (`Assessments.tsx`, `StudyPlans.tsx`, `MyProgress.tsx`, `AssessmentResultsPage.tsx`, etc.) has identical boilerplate:
```tsx
const { data: studentInfo } = useStudentInfo();
const { data: classesData } = useMyClasses();
const firstName = studentInfo?.firstName ?? "";
const lastName = studentInfo?.lastName ?? "";
const studentName = [firstName, lastName].filter(Boolean).join(" ") || "Student";
const gradeName = studentInfo?.gradeName ?? "";
const curriculumName = studentInfo?.curriculumName ?? "";
const sidebarClasses = (Array.isArray(classesData) ? classesData : []).map(...);
```

This 15-line block appears in 7+ files. Extract to a hook:
```ts
// src/hooks/useStudentLayoutProps.ts
export function useStudentLayoutProps() {
  const { data: studentInfo } = useStudentInfo();
  const { data: classesData } = useMyClasses();

  const studentName = [studentInfo?.firstName, studentInfo?.lastName]
    .filter(Boolean).join(" ") || "Student";

  const sidebarClasses = (Array.isArray(classesData) ? classesData : []).map(
    (cls: StudentClassResponse) => ({
      id: cls.id,
      name: cls.name,
      subjectName: cls.subjectName,
      subjectId: cls.subjectId,
      diagnosticStatus: cls.onboardingDiagnosticStatus,
      diagnosticAttemptId: cls.diagnosticAttemptId,
    }),
  );

  return {
    studentName,
    gradeName: studentInfo?.gradeName ?? "",
    curriculumName: studentInfo?.curriculumName ?? "",
    sidebarClasses,
    isPending: studentInfoPending || classesPending, // expose so pages can show skeletons
  };
}
```
Where `studentInfoPending` and `classesPending` come from destructuring each `useQuery` call:
```ts
const { data: studentInfo, isPending: studentInfoPending } = useStudentInfo();
const { data: classesData, isPending: classesPending } = useMyClasses();
```

Note: this is a plain data hook (no state, no effects beyond the two useQuery calls) — naming it `use` prefix is correct here as it wraps hooks.

---

## 🧪 P4 — Testing

---

### ST-024 · Fix test — StudentLayout locked class aria query
**File:** `packages/ui/src/layouts/__tests__/StudentLayout.test.tsx`

**Problem — two issues:**

1. Test uses a hardcoded class name from a previous demo dataset:
```tsx
expect(screen.getByLabelText(/Chemistry 10A/)).toBeInTheDocument();
```
This should use whatever class name is passed as a prop, not a hardcoded string.

2. After ST-013 and ST-018 ship, the aria-label pattern changes from "start diagnostic to unlock" to "tap to begin your diagnostic". The test's regex must match the new pattern:
```tsx
// OLD — wrong on both counts
expect(screen.getByRole("link", { name: /Chemistry 10A.*start diagnostic/i })).toBeInTheDocument();

// FIXED
expect(
  screen.getByRole("link", { name: /Chemistry 10A.*begin.*diagnostic/i })
).toBeInTheDocument();
```

In the test setup, the locked class is named "Chemistry 10A" as test data — that's fine as long as it's consistent with what's passed in `classes` prop. But the aria pattern must match ST-013's new wording.

**Depends on:** ST-013 + ST-018 both shipped.

---

### ST-025 · Add unit tests for useStudentLayoutProps hook
**File:** New — `src/hooks/__tests__/useStudentLayoutProps.test.ts`

Once ST-023 ships, test:
- Returns correct `studentName` for first + last name
- Returns first name only when no last name
- Returns "Student" when both names absent
- Returns empty `sidebarClasses` array when `classesData` is undefined/non-array
- Correctly maps `onboardingDiagnosticStatus` to `diagnosticStatus`

---

## Quick Wins — Start Here

| Task | File | Effort | Impact |
|---|---|---|---|
| ST-009 | Add identity-obj-proxy to package.json | 1 min | CI won't randomly fail |
| ST-002 | Fix `ffont-sans` and `mb-` in ClassCard | 2 min | Cards render correctly |
| ST-015 | Add `type="button"` to NextStepCard | 1 min | Defensive correctness |
| ST-011 (h1 only) | Add `font-bold` to Settings h1 | 1 min | Visual consistency |
| ST-014 | Fix conditional render of amber box | 5 min | Stops demotivating students |
| ST-012 | Fix duration-600 → duration-500 | 1 min | Modality bars animate correctly |
| ST-004 | Remove unused `useAuth()` call | 1 min | Clean hook usage |

---

## Dependency Map

```
ST-001 (stale closure)            → no deps, do now
ST-002 (ClassCard typos)          → no deps, do now
ST-003 (useOnboardingStatus)      → ST-008 (gate logic change)
ST-006 (ProfileQuestionnaire)     → no deps, isolated change
ST-007 (SubjectScoresSection)     → no deps, isolated useCallback
ST-008 (OnboardingRoute gate)     → ST-003 (after useQuery refactor)
ST-011 (Settings tokens)          → no deps
ST-013 (aria-label locked)        → ST-018 (diagnostic framing, do together)
ST-016 (Study Plans empty state)  → no deps for empty state, ST-020 for CTA destination
ST-017 (Assessments empty state)  → no deps for empty state
ST-019 (merge duplicate hooks)    → ST-023 (extract useStudentLayoutProps, do together)
ST-020 (AI Concept Guide)         → ST-003 (useOnboardingStatus clean), learning profile API
ST-021 (profile visible impact)   → ST-020 (Concept Guide must exist first to reference)
ST-022 (student-initiated study)  → ST-020 (Concept Guide as first destination)
```

---

## Out of Scope
- Parent portal (M5)
- Peer comparison or class rankings (never — see Vidhya's position on competitive metrics for 11–18 year olds)
- AI essay writing assistance (safety and academic integrity concern)
- Real-time collaborative sessions (M6+)
