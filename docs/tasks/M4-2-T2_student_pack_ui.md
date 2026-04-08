# M4-2-T2 — Student Pack UI
**Milestone:** M4 — Teacher Copilot
**Epic:** M4-2 — Student Pack
**Task:** T2
**Executor:** Coding agent
**Depends on:**
  - M4-2-T1 (student pack service + API endpoint must be live)
  - M0-8-T8 (4-band mastery tokens must exist)
  - M0-8-T7 (Modal component from packages/ui)
  - M0-8-T6 (Toast system)
**Blocks:** Nothing — final task of M4

> **App target:** `apps/student` ONLY.
> Load `DESIGN_SYSTEM.md` §5.4 (Student) before writing any component.
> Green is the action color. Sidebar navigation. Fraunces headings, Nunito body.

---

## User Story

As a student, I want to open my personalised lesson pack and work through it at my
own pace — watching the video, reading the explanation, completing the pre-quiz
before the lesson and the post-quiz after — so I feel prepared and can see how my
understanding has grown.

---

## Context

The student pack is generated on-demand by M4-2-T1 when the student first opens
a lesson plan. It contains:
- A motivating "what you'll learn" sentence
- A real-life intro matched to the student's interests
- A short explanation (≤200 words) adapted to their learning style
- A YouTube video (or explanation text) sequenced by learning style
- A pre-lesson quiz (3 MCQ from question bank, easier difficulty)
- A post-lesson quiz (3 MCQ from question bank, mastery-calibrated)

The UI is the student-facing counterpart to M4-1-T5 (teacher preview) — but
this is what students actually experience, not a teacher read-only view.

---

## Files to Create

```
frontend/apps/student/src/pages/lesson-plans/
  StudentPackPage.tsx               ← page shell, route, data fetching

frontend/apps/student/src/components/lesson-plans/
  PackHero.tsx                      ← "what you'll learn" + real-life intro card
  PackVideoSection.tsx              ← YouTube embed (video_first learners)
  PackExplanationSection.tsx        ← text explanation card
  PackContentBlock.tsx              ← composes video + explanation in correct sequence
  PackPreQuiz.tsx                   ← pre-lesson quiz (3 questions, locked until started)
  PackPostQuiz.tsx                  ← post-lesson quiz (3 questions, unlocked after content)
  PackQuizQuestion.tsx              ← single MCQ question with option selection
  PackProgressBar.tsx               ← visual tracker: Intro → Content → Pre-quiz → Post-quiz
  PackCompletionCard.tsx            ← score reveal + mastery change after post-quiz

frontend/apps/student/src/hooks/
  useStudentPack.ts                 ← React Query hook for GET /lesson-plans/:id/student-pack
  useSubmitPostQuiz.ts              ← mutation hook for POST .../quiz/submit

frontend/apps/student/src/tests/
  student-pack.spec.ts              ← Playwright E2E tests
```

---

## Route

`/student/lesson-plans/:planId/pack` — `StudentPackPage`

Protected by `PrivateRoute` + `RoleRoute(['STUDENT'])`.

Add to `apps/student/src/App.tsx` inside the authenticated student routes:
```tsx
<Route path="lesson-plans/:planId/pack" element={<StudentPackPage />} />
```

The lesson plan list (wherever it lives in the student app) should link to this
route as "Start lesson" or "Continue lesson" depending on pack state.

---

## API Calls

```typescript
// On mount — get or generate the pack
GET /api/v1/lesson-plans/{planId}/student-pack
→ StudentPackResponse (see M4-2-T1 schema)

// On post-quiz submit
POST /api/v1/lesson-plans/{planId}/student-pack/quiz/submit
Body: { answers: { [questionId: string]: string } }
→ { score: number }
```

---

## Page Layout & Component Specs

### Overall Structure

```
┌─────────────────────────────────────────────────────┐
│  StudentLayout sidebar (unchanged)                  │
│                                                     │
│  Page content area:                                 │
│  ┌───────────────────────────────────────────────┐  │
│  │  PackProgressBar                              │  │
│  │  [Intro] ──── [Content] ──── [Pre-Quiz] ──── [Post-Quiz]  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │  PackHero                                     │  │
│  │  (what_you_will_learn + real_life_intro)      │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │  PackPreQuiz  (unlocked at page load)         │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │  PackContentBlock                             │  │
│  │  (video + explanation, sequenced by style)   │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │  PackPostQuiz  (locked until content viewed)  │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

### `PackProgressBar.tsx`

Four steps: Intro, Content, Pre-Quiz, Post-Quiz.
Current step highlighted with `bg-brand-primary` dot and label.
Completed steps show a checkmark. Future steps are grey.

```tsx
type PackStep = 'intro' | 'content' | 'pre-quiz' | 'post-quiz'

const STEPS: { id: PackStep; label: string }[] = [
  { id: 'intro',    label: 'Introduction' },
  { id: 'content',  label: 'Learn'        },
  { id: 'pre-quiz', label: 'Check-In'     },
  { id: 'post-quiz',label: 'Quiz'         },
]
```

```
● Introduction  ──  ○ Learn  ──  ○ Check-In  ──  ○ Quiz
```

Tailwind:
```
Completed step dot:  w-3 h-3 rounded-full bg-brand-primary
Active step dot:     w-3 h-3 rounded-full bg-brand-primary ring-2 ring-brand-primary ring-offset-2
Future step dot:     w-3 h-3 rounded-full bg-brand-border
Connector line:      h-px flex-1 bg-brand-border (completed: bg-brand-primary)
Step label:          text-xs font-medium (active: text-brand-primary, completed: text-brand-body, future: text-brand-muted)
```

---

### `PackHero.tsx`

```
┌──────────────────────────────────────────────────────┐
│  Forces and Motion                  Grade 7 · SCI    │
│  (font-display text-2xl text-brand-ink)              │
│                                                      │
│  "By the end of this lesson, you will be able to     │
│  explain why a football travels further when you     │
│  kick it harder."                                    │
│  (font-sans text-base text-brand-body leading-relaxed)│
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  🌍 Real-world connection                      │  │
│  │  "When a goalkeeper saves a penalty kick, they │  │
│  │  apply a force to change the ball's direction. │  │
│  │  This is Newton's Second Law in action — the  │  │
│  │  harder the kick, the more force needed to    │  │
│  │  stop it."                                    │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

```tsx
// Hero card
<div className="bg-white rounded-2xl border border-role-student-border p-5 mb-4">
  <div className="flex items-center justify-between mb-3">
    <h1 className="font-display font-bold text-2xl text-brand-ink">
      {subtopicName}
    </h1>
    <span className="text-xs font-sans font-bold uppercase tracking-wide
                     text-brand-muted bg-brand-border-soft px-2 py-1 rounded-full">
      {gradeLevel} · {subjectCode}
    </span>
  </div>
  <p className="font-sans text-base text-brand-body leading-relaxed mb-4">
    {whatYouWillLearn}
  </p>

  {/* Real-life intro callout */}
  <div className="bg-brand-light rounded-xl p-4 border border-brand-mid">
    <div className="flex items-center gap-2 mb-2">
      <span className="text-lg" aria-hidden="true">🌍</span>
      <span className="font-sans text-xs font-bold uppercase tracking-wide
                       text-brand-primary">
        Real-world connection
      </span>
    </div>
    <p className="font-sans text-sm text-brand-ink leading-relaxed">
      {realLifeIntro}
    </p>
  </div>
</div>
```

---

### `PackContentBlock.tsx`

Sequences `PackVideoSection` and `PackExplanationSection` based on `content_sequence`.

```tsx
interface PackContentBlockProps {
  videoUrl: string | null
  videoTitle: string | null
  explanation: string
  contentSequence: 'video_first' | 'text_first'
  onContentViewed: () => void   // called when student has seen content, unlocks post-quiz
}

// content_sequence = 'video_first' → video renders above explanation
// content_sequence = 'text_first'  → explanation renders above video
```

Content is considered "viewed" when:
- Video: student plays the video (listen for YouTube iframe postMessage, or use a
  "Mark as watched" button as fallback since postMessage can be unreliable cross-origin)
- Text: student scrolls to the bottom of the explanation card (IntersectionObserver)

Use the simpler "Mark as watched" button pattern for MVP — iframe postMessage
integration can be a future enhancement. Once either content piece is marked,
`onContentViewed()` is called and the post-quiz unlocks.

```tsx
// Mark as watched button (video section)
<button
  className="mt-3 text-sm font-semibold text-brand-primary
             hover:text-brand-dark transition-colors
             focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1"
  onClick={onContentViewed}
>
  ✓ I've watched this video
</button>
```

---

### `PackVideoSection.tsx`

```tsx
// YouTube embed with correct security and accessibility attributes
const videoId = extractYouTubeId(videoUrl)  // same utility as M3-0-T2a

{videoId ? (
  <div className="bg-white rounded-2xl border border-role-student-border p-5 mb-4">
    <h2 className="font-display font-semibold text-lg text-brand-ink mb-3">
      Watch
    </h2>
    <div className="relative w-full rounded-xl overflow-hidden"
         style={{ paddingBottom: '56.25%' }}>
      <iframe
        className="absolute inset-0 w-full h-full"
        src={`https://www.youtube.com/embed/${videoId}`}
        title={`${videoTitle} — video explanation`}
        aria-label={`Video: ${videoTitle}`}
        sandbox="allow-scripts allow-same-origin allow-presentation"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
        loading="lazy"
      />
    </div>
    {videoTitle && (
      <p className="mt-2 text-xs text-brand-muted font-sans">{videoTitle}</p>
    )}
    <button
      className="mt-3 inline-flex items-center gap-1.5 text-sm font-semibold
                 text-brand-primary hover:text-brand-dark transition-colors
                 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1"
      onClick={onContentViewed}
    >
      <span aria-hidden="true">✓</span> I've watched this video
    </button>
  </div>
) : (
  // No video available — show explanation only, mark auto-viewed
  null
)}
```

---

### `PackExplanationSection.tsx`

```tsx
<div className="bg-white rounded-2xl border border-role-student-border p-5 mb-4"
     ref={explanationRef}>   // IntersectionObserver target for scroll detection
  <h2 className="font-display font-semibold text-lg text-brand-ink mb-3">
    Explanation
  </h2>
  <div className="font-sans text-sm text-brand-ink leading-relaxed space-y-3">
    {/* Split explanation into paragraphs on newlines */}
    {explanation.split('\n').filter(Boolean).map((para, i) => (
      <p key={i}>{para}</p>
    ))}
  </div>
</div>
```

---

### `PackPreQuiz.tsx` and `PackPostQuiz.tsx`

Both share the same `PackQuizQuestion` component. Differences:

| | Pre-quiz | Post-quiz |
|---|---|---|
| Label | "Check your starting knowledge" | "Check what you've learned" |
| When available | Always (from page load) | Only after content viewed |
| Answers revealed | After submission | After submission |
| Correct answer shown | No (diagnostic only) | Yes |
| Score shown | No | Yes (with mastery change) |
| Submit CTA | "Submit check-in" | "Submit quiz" |

```tsx
// Pre-quiz header
<div className="bg-white rounded-2xl border border-role-student-border p-5 mb-4">
  <div className="flex items-center justify-between mb-1">
    <h2 className="font-display font-semibold text-lg text-brand-ink">
      Check your starting knowledge
    </h2>
    <span className="text-xs font-sans text-brand-muted">
      3 questions · won't affect your score
    </span>
  </div>
  <p className="font-sans text-sm text-brand-muted mb-4">
    Answer honestly — this helps us understand what you already know.
  </p>
  {/* PackQuizQuestion × 3 */}
  ...
</div>

// Post-quiz locked state (before content viewed)
<div className="bg-white rounded-2xl border border-role-student-border p-5 mb-4
                opacity-60 pointer-events-none select-none"
     aria-disabled="true">
  <div className="flex items-center gap-2 mb-2">
    <span className="text-lg" aria-hidden="true">🔒</span>
    <h2 className="font-display font-semibold text-lg text-brand-ink">
      Final Quiz
    </h2>
  </div>
  <p className="font-sans text-sm text-brand-muted">
    Complete the lesson content above to unlock this quiz.
  </p>
</div>
```

---

### `PackQuizQuestion.tsx`

```tsx
interface PackQuizQuestionProps {
  question: QuizQuestionResponse
  selectedKey: string | null
  onSelect: (key: string) => void
  submitted: boolean
  revealAnswer: boolean   // true only in post-quiz after submission
  questionNumber: number
}

// Option button — unselected
className="w-full text-left px-4 py-3 rounded-xl border border-role-student-border
           font-sans text-sm text-brand-ink
           hover:bg-brand-light hover:border-brand-mid transition-colors
           focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1"

// Option button — selected (before submit)
className="... bg-brand-light border-brand-primary text-brand-primary font-semibold"

// Option button — correct answer (post-quiz, after submit, revealAnswer=true)
className="... bg-brand-green-light border-brand-green text-brand-green font-semibold"

// Option button — wrong selected (post-quiz, after submit, revealAnswer=true)
className="... bg-brand-red-light border-brand-red text-brand-red line-through"
```

Each option must have an accessible radio pattern:
```tsx
<div role="radiogroup" aria-labelledby={`q${questionNumber}-text`}>
  <p id={`q${questionNumber}-text`} className="font-sans text-sm font-semibold
     text-brand-ink mb-3">
    {questionNumber}. {question.question_text}
  </p>
  {question.options.map(option => (
    <button
      key={option.key}
      role="radio"
      aria-checked={selectedKey === option.key}
      onClick={() => !submitted && onSelect(option.key)}
      disabled={submitted}
      className={getOptionClass(option.key, selectedKey, submitted, question.correct_answer, revealAnswer)}
    >
      <span className="font-bold mr-2">{option.key}.</span>
      {option.text}
    </button>
  ))}
</div>
```

---

### `PackCompletionCard.tsx`

Shown after post-quiz submission. Reveals score and mastery change.

```
┌──────────────────────────────────────────────────────┐
│  ✨ Quiz complete!                                    │
│                                                      │
│  Your score:  2 / 3                                  │
│               ██████████░  67%                       │
│                                                      │
│  Progress on Forces and Motion:                      │
│  Before:  ● Developing  →  After:  ● Approaching     │
│                                                      │
│  [Back to dashboard]   [View study plan]             │
└──────────────────────────────────────────────────────┘
```

The "Before/After" mastery labels use `getMasteryStyle()` for colours.
"Before" is the mastery score from before the quiz (fetched from gap_states at
pack load time). "After" is recalculated after submission (from the updated
gap_states — may require a refetch with a short delay for the Celery update).

Celebration tone uses `bg-brand-gold text-white` for the completion banner
(gold = achievement moments in student app per DESIGN_SYSTEM.md §5.4 Buttons).

---

### Loading State

First-time pack generation takes up to 30 seconds. Show a loading skeleton
with pulsing badge per CONSTITUTION Rule 22:

```tsx
// Full page skeleton while generating
<div className="space-y-4">
  {/* Hero skeleton */}
  <div className="bg-white rounded-2xl border border-role-student-border p-5 animate-pulse">
    <div className="h-6 bg-brand-border rounded w-1/2 mb-3" />
    <div className="h-4 bg-brand-border rounded w-3/4 mb-2" />
    <div className="h-4 bg-brand-border rounded w-2/3" />
  </div>

  {/* Generation status badge */}
  <div className="flex justify-center">
    <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full
                     bg-brand-light border border-brand-mid text-sm font-sans
                     text-brand-primary">
      <span className="w-2 h-2 rounded-full bg-brand-primary animate-pulse" />
      Preparing your personalised lesson...
    </span>
  </div>
</div>
```

---

## React Query Hooks

```typescript
// useStudentPack.ts
export function useStudentPack(planId: string) {
  return useQuery({
    queryKey: ['studentPack', planId],
    queryFn: () => apiClient.get<StudentPackResponse>(
      `/lesson-plans/${planId}/student-pack`
    ),
    staleTime: Infinity,   // pack is immutable once generated — never re-fetch automatically
    retry: 1,
  })
}

// useSubmitPostQuiz.ts
export function useSubmitPostQuiz(planId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (answers: Record<string, string>) =>
      apiClient.post<{ score: number }>(
        `/lesson-plans/${planId}/student-pack/quiz/submit`,
        { answers }
      ),
    onSuccess: () => {
      // Invalidate gap map so mastery change reflects immediately
      queryClient.invalidateQueries({ queryKey: ['studentGapMap'] })
    },
  })
}
```

---

## Acceptance Criteria

### Content and sequencing
- [ ] `content_sequence = 'video_first'` → video renders above explanation
- [ ] `content_sequence = 'text_first'` → explanation renders above video
- [ ] `video_url = null` → video section not rendered; explanation auto-marked as content viewed
- [ ] Pre-quiz available immediately on page load (no lock)
- [ ] Post-quiz locked until "I've watched this video" or explanation scroll triggers `onContentViewed`
- [ ] Post-quiz unlocks after content viewed — no page reload required

### Quiz behaviour
- [ ] Selecting an option highlights it; selecting another option deselects first
- [ ] Submit button disabled until all 3 questions answered
- [ ] Pre-quiz: after submit, no correct answers revealed (diagnostic only)
- [ ] Post-quiz: after submit, correct answers shown in green, wrong selections in red strikethrough
- [ ] Post-quiz submission shows `PackCompletionCard` with score and mastery change
- [ ] Post-quiz submission triggers gap_states invalidation via React Query

### Loading and error states
- [ ] First-time generation (< 30s): skeleton shown with pulsing generation badge
- [ ] Second visit: pack loads instantly from cache (no skeleton delay)
- [ ] Network error: toast shown, retry button available
- [ ] Empty pack (no video, no explanation): graceful fallback messages shown

### Accessibility
- [ ] Quiz questions use `role="radiogroup"` with `aria-labelledby`
- [ ] Each option button has `role="radio"` and `aria-checked`
- [ ] YouTube iframe has `title` and `aria-label` attributes
- [ ] YouTube iframe has `sandbox` attributes (allow-scripts, allow-same-origin, allow-presentation)
- [ ] Post-quiz locked state has `aria-disabled="true"` and `pointer-events-none`
- [ ] PackCompletionCard mastery labels have `aria-label` on colour dots

---

## Tests to Write

```typescript
// frontend/apps/student/src/tests/student-pack.spec.ts (Playwright)
test('student opens lesson pack — first time — sees loading state then content')
test('student opens lesson pack — second time — instant load no skeleton')
test('pre-quiz available immediately on pack load')
test('post-quiz locked before content viewed')
test('clicking I have watched video unlocks post-quiz')
test('pre-quiz submit shows questions without revealing answers')
test('post-quiz submit reveals correct and incorrect answers')
test('post-quiz submit shows completion card with score')
test('video renders above explanation when content_sequence is video_first')
test('explanation renders above video when content_sequence is text_first')
test('video section not rendered when video_url is null')
```

---

## Do NOT Touch

- `apps/teacher` — the teacher preview (M4-1-T5) is a separate page with separate design
- Any backend files — M4-2-T1 owns the API
- `curriculum_chunks` — never reference
- `subtopics.embedding` — never reference

---

*Task M4-2-T2 · Pixel (UX/UI Lead) + Kramer (Technical Lead) · April 2026*
*Student-facing counterpart to M4-1-T5 (teacher read-only preview).*
