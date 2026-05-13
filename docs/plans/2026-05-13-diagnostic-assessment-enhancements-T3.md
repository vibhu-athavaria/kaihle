# T3 — Frontend Wizard UI Redesign
**Branch:** `feat/diagnostic-enhancements-T3_feature/diagnostic-wizard-ui`
**Parent:** `feat/diagnostic-enhancements-T2_feature/diagnostic-service-and-api`
**Executor:** Coding agent
**Status:** Blocked on T2

---

## What This Task Does

Redesigns the diagnostic assessment creation wizard step ("Topics") into a combined
"Topics & Settings" step with:
- Grade-grouped topic picker (current grade + previous grade, collapsible sections)
- Per-topic availability warnings fetched live from the new `topic-availability` API endpoint
- Configuration panel (questions_per_topic, time_limit_minutes, question_types, difficulty range)
- Merged into one step (Topics + Configure become one "Topics & Settings" step)

Read `docs/design/DESIGN_SYSTEM.md` §5.3 in full before writing any component.

---

## UI Design Reference

See mockups produced by Pixel — annotated ASCII mockups are the authoritative layout reference.
All Tailwind class choices must match the annotation table exactly.

### Layout: Two-column on desktop, stacked on mobile

- **Left column (`flex-1`):** Grade-grouped topic picker
- **Right column (`w-72`):** Configuration panel (sticky, doesn't scroll with topic list)
- **Mobile (`md:` breakpoint):** Configuration panel stacks ABOVE topic picker

---

## Component Breakdown

All new components live in the teacher app wizard directory (find it under
`frontend/apps/teacher/src/`).

### 1. `TopicGroupSection` (new)

Collapsible section for one grade group.

Props:
```typescript
interface TopicGroupSectionProps {
  gradeLabel: string          // "Current Grade (Grade 8)" | "Previous Grade (Grade 7)"
  isCurrent: boolean          // true = gold tint header, false = muted header
  topics: TopicWithAvailability[]
  selectedIds: Set<string>
  onToggle: (id: string) => void
  onSelectAll: () => void
  defaultOpen?: boolean       // current grade defaults open, previous defaults closed
}
```

Collapsed state shows selection count in header: `"2 selected"` text-xs text-brand-muted.

### 2. `TopicRow` (new)

Single topic checkbox row with availability indicator.

Props:
```typescript
interface TopicRowProps {
  topic: TopicWithAvailability
  selected: boolean
  onToggle: () => void
}
```

Availability states:
- **Sufficient** (`available >= questions_per_topic`): show `"N ✓"` gold badge, `bg-white`
- **Warning** (`0 < available < questions_per_topic`): amber-50 bg, `border-l-2 border-amber-400`,
  `TriangleAlert` icon + `"Only N question available — need M"` text-xs text-amber-700
- **Error** (`available === 0`): red-50 bg, `border-l-2 border-brand-red`,
  `XCircle` icon + `"No questions in bank for this topic"` text-xs text-brand-red

### 3. `AssessmentConfigPanel` (new)

Right-column settings panel.

Props:
```typescript
interface AssessmentConfigPanelProps {
  questionsPerTopic: number
  onQuestionsPerTopicChange: (n: number) => void
  timeLimitMinutes: number | null
  onTimeLimitChange: (n: number | null) => void
  questionTypes: string[]
  onQuestionTypesChange: (types: string[]) => void
  minimumDifficulty: number
  maximumDifficulty: number
  onDifficultyChange: (min: number, max: number) => void
}
```

Fields:
- **Questions per topic**: `input type="number"` min=1 max=20, `w-20`
- **Time limit**: `input type="number"` min=1 max=300, placeholder="—", helper: "leave blank = untimed"
- **Question types**: checkbox group — MCQ, True/False (at least one must be selected; SHORT_ANSWER not supported)
- **Difficulty range**: two `input type="number"` w-16, min 1 max 5; visual pip strip between them showing range

### 4. Updated wizard step component

Replace current Topics step (and Configure step if separate) with one combined step.

State managed at wizard level:
```typescript
const [selectedTopicIds, setSelectedTopicIds] = useState<Set<string>>(new Set())
const [questionsPerTopic, setQuestionsPerTopic] = useState(2)
const [timeLimitMinutes, setTimeLimitMinutes] = useState<number | null>(null)
const [questionTypes, setQuestionTypes] = useState<string[]>(['MCQ'])
const [minimumDifficulty, setMinimumDifficulty] = useState(1)
const [maximumDifficulty, setMaximumDifficulty] = useState(5)
```

### 5. Topic availability hook: `useTopicAvailability`

```typescript
// frontend/apps/teacher/src/hooks/useTopicAvailability.ts

function useTopicAvailability(params: {
  classId: string
  topicIds: string[]
  questionsPerTopic: number
  minimumDifficulty: number
  maximumDifficulty: number
  questionTypes: string[]
}): {
  data: TopicAvailability[] | undefined
  isLoading: boolean
}
```

- React Query `useQuery` calling `POST /classes/{classId}/assessments/topic-availability`
- `enabled: topicIds.length > 0`
- `staleTime: 30_000` — re-fetches when questionsPerTopic or difficulty changes
- Query key: `['topic-availability', classId, topicIds, questionsPerTopic, minimumDifficulty, maximumDifficulty, questionTypes]`

Availability check fires debounced (300ms) when `questionsPerTopic`, difficulty, or `questionTypes` change while topics are selected.

### 6. Topic loading: topics by grade

New query hook `useClassTopicsWithGrades`:
```typescript
// Fetches topics for class.grade and class.grade - 1
// Returns { currentGradeTopics: CurriculumTopic[], previousGradeTopics: CurriculumTopic[] }
```

This requires a backend endpoint — confirm with T2 that `GET /classes/{classId}/topics?include_previous_grade=true`
returns topics grouped by grade. If not added in T2, add it as part of this task.

---

## Request Body on Submit

```typescript
const body: DesignTier1DiagnosticRequest = {
  topic_ids: Array.from(selectedTopicIds),
  questions_per_topic: questionsPerTopic,
  time_limit_minutes: timeLimitMinutes,
  question_types: questionTypes,
  minimum_difficulty: minimumDifficulty,
  maximum_difficulty: maximumDifficulty,
  deadline: deadline ?? null,
}
```

---

## Validation Before "Next" / Submit

Block progression if:
- No topics selected
- At least one selected topic has `available === 0` AND that topic is checked (error state)
- `questionTypes` is empty
- `minimumDifficulty > maximumDifficulty`

Warn (allow progression) if:
- Any selected topic has `0 < available < questionsPerTopic` (amber warning)

Show a summary warning banner above the CTA if any warnings exist:
```
⚠  2 topics have fewer questions than requested.
   The diagnostic will use what's available for those topics.
```
`bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-700`

---

## Loading & Error States (DESIGN_SYSTEM §10)

- Topic list loading: skeleton rows (`animate-pulse`) while `useClassTopicsWithGrades` loads
- Availability check loading: skeleton badge `animate-pulse w-12 h-5 rounded-full` in each topic row
- Config panel: no skeleton needed (inputs render immediately)
- If availability check errors: show neutral badges, don't block submission

---

## Acceptance Criteria

- [ ] Grade sections render: "Current Grade (Grade N)" open by default, "Previous Grade (Grade N-1)" collapsed with selection count.
- [ ] Selecting/deselecting a topic triggers debounced availability re-fetch.
- [ ] Changing `questionsPerTopic`, difficulty, or `questionTypes` re-fetches availability.
- [ ] Topic rows show correct availability state (sufficient / warning / error).
- [ ] "Next" / submit is blocked when any selected topic has 0 available questions.
- [ ] Warning banner appears when any selected topic is amber (but Next is not blocked).
- [ ] Config panel fields submit correct values to `POST /classes/{classId}/diagnostics/tier1`.
- [ ] `time_limit_minutes` submits as `null` when input is blank.
- [ ] Follows Teacher design spec: gold CTAs, Fraunces heading, Nunito body, white card on `role-teacher-bg`.
- [ ] All interactive elements have focus rings: `focus-visible:ring-2 focus-visible:ring-brand-gold`.
- [ ] Touch targets >= 44px on all checkboxes and buttons.
- [ ] Passes `npx tsc --noEmit` with no errors.

---

## Files Changed

```
frontend/apps/teacher/src/hooks/useTopicAvailability.ts           ← new
frontend/apps/teacher/src/hooks/useClassTopicsWithGrades.ts       ← new
frontend/apps/teacher/src/components/wizard/TopicGroupSection.tsx ← new
frontend/apps/teacher/src/components/wizard/TopicRow.tsx          ← new
frontend/apps/teacher/src/components/wizard/AssessmentConfigPanel.tsx ← new
frontend/apps/teacher/src/pages/[wizard-step-file].tsx            ← update existing step
```

Confirm exact paths by reading the existing wizard directory before writing any file.
