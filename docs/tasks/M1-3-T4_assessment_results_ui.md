# M1-3-T4 — Teacher Assessment Results UI
**Milestone:** M1 — Core Diagnostics Flow · **Epic:** M1-3
**Authors:** Kramer (engineering) · Pixel (design) · Vidhya (education)
**Depends on:** M1-3-T3 (assessment wizard), M1-4-T1 (attempt routes)
**Blocks:** Nothing · **Effort:** 4–5 hours

---

## Vidhya — Educational Context

Understanding what a teacher actually needs when reviewing results is what separates a useful tool from a grade-book clone.

**The teacher's three questions:**

1. *"Who needs my help right now?"* — The class overview must surface struggling students at the top, not the top scorers. Sorting lowest-first is an instructional design choice, not a preference. A teacher looking at results after a lesson has limited time and limited energy — make the highest-priority students impossible to miss.

2. *"Is this a class-wide problem or individual gaps?"* — If the majority of students scored below 40% on the same assessment, the lesson failed to land, not the students. The product must flag this pattern explicitly. Vidhya's rule: when more than 30% of submitted students score below 40%, show an amber contextual note: *"More than 30% of students scored below 40%. This topic may benefit from whole-class reteaching before moving on."* Teachers need permission to acknowledge this without shame.

3. *"What did this student actually misunderstand, specifically?"* — The per-student question breakdown has no value if it only shows a ✓ or ✕. Teachers need to see: what was the question, what did the student answer, and what was the correct answer. This mirrors how Cambridge and IB mark schemes work — teachers are trained to do side-by-side comparison. Reproduce that mental model.

**Assessment type context matters.** A 45% score on a Tier 1 Diagnostic is expected and appropriate — students haven't been taught the material yet. A 45% on a Tier 2 Topic-Specific assessment after teaching means something completely different. Always show the assessment type prominently so teachers interpret scores in context.

**Band labels, not just percentages.** "74% — Developing" is more instructionally useful than "74%". A Cambridge teacher knows what "Developing" means for their next lesson. Always show `getMasteryStyle(score).label` alongside the number.

---

## Pixel — Design Spec

### Page architecture

Two pages. Both share the same breadcrumb and `DashboardLayout variant="teacher"`. The flow is linear: class overview → student detail. There is no sidebar navigation between students — use prev/next on the detail page only if M2-2-T2 (Student Profile) already implements it.

### Component: ResultsKPIRow

```
Component: ResultsKPIRow
──────────────────────────────────────────────────────────
Layout:     grid-cols-2 gap-4 md:grid-cols-4
Card:       bg-white rounded-2xl border border-gray-100
            shadow-sm p-5
Label:      font-nunito text-[11px] uppercase tracking-[0.08em]
            text-gray-400 mb-1
Value:      font-fraunces text-[28px] leading-none
Sub:        font-nunito text-xs text-gray-400 mt-1
──────────────────────────────────────────────────────────
Submitted:  value "17 of 28"  color text-ink
Class avg:  value "68%"       color getMasteryStyle(score).textClass
            sub   "Developing"
Highest:    value "Emma R."   color text-ink
            sub   "94% · Strong"
Needs attn: value "4 students" color text-red-600 if >0, text-gray-400 if 0
            sub   "Scored below 40%"
──────────────────────────────────────────────────────────
Loading state: 4 skeleton cards — animate-pulse bg-gray-100
               DO NOT show "0 of 0" during load (Vidhya: misread as empty class)
Empty (0 submitted): "No students have submitted yet" below KPI row — not zeroed values
──────────────────────────────────────────────────────────
Accessibility: aria-label per card — e.g. aria-label="Class average: 68%, Developing"
```

### Component: ScoreDistributionChart

Horizontal Recharts BarChart. Not a pie chart — horizontal bars make count comparison faster to read and easier to explain to students.

```
Component: ScoreDistributionChart
──────────────────────────────────────────────────────────
Height:     180px
Bars (top to bottom):
  "Strong (≥70%)"     fill #16a34a
  "Developing (40–69%)" fill #f59e0b
  "Needs Work (<40%)"  fill #ef4444
  "Not submitted"      fill #d1d5db
Label inside bar: count (Nunito 12px text-white) if bar ≥ 48px wide
Label outside:    count (Nunito 12px text-gray-600) if bar < 48px
Y-axis labels:    Nunito 12px text-gray-500
X-axis:           Hidden (count is the label)
Tooltip:          "N students" — bg-gray-900 text-white text-xs px-2 py-1 rounded
──────────────────────────────────────────────────────────
Vidhya reteaching banner (conditional — see engineering spec):
  bg-amber-50 border border-amber-200 rounded-xl p-3 mt-3
  text-amber-800 text-sm leading-relaxed
  Icon: ⚠ inline before text
──────────────────────────────────────────────────────────
Accessibility: role="img" on the chart wrapper
               aria-label="Score distribution: {N} Strong, {N} Developing,
               {N} Needs Work, {N} not submitted"
               Visible text legend below chart (never colour-only)
```

### Component: StudentResultsTable

```
Component: StudentResultsTable
──────────────────────────────────────────────────────────
Default sort: Score ascending (lowest first) — Vidhya's requirement
Row height:   56px (touch target ≥ 44px)
Hover:        bg-gray-50 transition-colors duration-100
──────────────────────────────────────────────────────────
Score pill (submitted):
  getMasteryStyle(score) — e.g. bg-green-100 text-green-700 border border-green-200
  rounded-full px-3 py-1 text-sm font-medium
Score (not submitted):
  "Pending" bg-gray-100 text-gray-400 rounded-full px-3 py-1 text-xs
──────────────────────────────────────────────────────────
Actions:
  Submitted:     "View answers →" — text-brand-gold text-sm font-medium
  Not submitted: "—" muted
──────────────────────────────────────────────────────────
Search: top-right, max-w-64, debounce 150ms, client-side filter
Sort:   dropdown — Name A–Z · Score ↑ (default) · Score ↓ · Date submitted
```

### Component: ScoreRing (SVG)

```
Component: ScoreRing
──────────────────────────────────────────────────────────
Dimensions: 100 × 100px, viewBox="0 0 100 100"
Track:      <circle cx="50" cy="50" r="42" stroke="#f3f4f6"
             stroke-width="10" fill="none" />
Fill:       <circle cx="50" cy="50" r="42"
             stroke={getMasteryStyle(score).hex}
             stroke-width="10" fill="none"
             stroke-linecap="round"
             stroke-dasharray={circumference}
             stroke-dashoffset={circumference * (1 - score)}
             transform="rotate(-90 50 50)" />
Circumference: 2 × π × 42 ≈ 263.9
Animation:  stroke-dashoffset transition 600ms cubic-bezier(0.4,0,0.2,1)
            @media (prefers-reduced-motion): remove transition entirely
Center:     Score % — font-fraunces text-[22px] font-bold text-ink
            Band label — font-nunito text-[10px] text-gray-500
──────────────────────────────────────────────────────────
Accessibility:
  <svg role="img" aria-label="{score}% — {band}">
    <title>{score}% · {band}</title>
  </svg>
```

### Component: QuestionBreakdown

```
Component: QuestionBreakdown
──────────────────────────────────────────────────────────
Card:       bg-white rounded-xl border border-gray-100 p-4 mb-3
Q header:   flex items-start gap-3
  Icon:     w-6 h-6 rounded-full flex-shrink-0
            ✓ correct:   bg-green-50 text-green-600
            ✕ incorrect: bg-red-50 text-red-500
  Number:   "Q{n}" font-nunito text-xs text-gray-400 font-semibold w-6
  Text:     font-nunito text-sm text-ink leading-relaxed
Answer rows (ml-9 to align with question text):
  Correct answer:
    Single row — "Answer: {text} ✓"
    bg-green-50 text-green-700 rounded-lg px-3 py-1.5 text-sm
  Wrong answer:
    Row 1 — "Given:   {text} ✕"  bg-red-50   text-red-700
    Row 2 — "Correct: {text} ✓"  bg-green-50 text-green-700  mt-1
──────────────────────────────────────────────────────────
Pagination:
  Show first 6. Button: "+ {N} more questions"
    variant ghost, text-brand-gold text-sm
  Reveal: fade-in opacity-0→1 duration-200 — or instant if reduced motion
  After expand: "Show less" link at bottom
──────────────────────────────────────────────────────────
Empty state: "No answers submitted yet."
  bg-gray-50 rounded-xl p-8 text-center text-gray-400 text-sm
```

---

## Kramer — Engineering Spec

### Files

```
frontend/apps/teacher/src/pages/assessments/
  AssessmentResultsPage.tsx
  StudentResultDetailPage.tsx

frontend/apps/teacher/src/components/results/
  ResultsKPIRow.tsx
  ScoreDistributionChart.tsx
  StudentResultsTable.tsx
  QuestionBreakdown.tsx
  ScoreRing.tsx           ← export from here; also imported by M1-4-T4 student results

frontend/apps/teacher/src/hooks/
  useAssessmentResults.ts

frontend/apps/teacher/src/tests/
  assessment-results.spec.ts
  score-ring.test.tsx
  question-breakdown.test.tsx
  score-distribution.test.tsx
```

### Routes

```tsx
<Route path="/teacher/assessments/:assessmentId/results"
  element={<AssessmentResultsPage />} />
<Route path="/teacher/assessments/:assessmentId/results/:studentId"
  element={<StudentResultDetailPage />} />
```

### Vidhya's 30% Threshold

```typescript
// ScoreDistributionChart.tsx
const submitted = students.filter(s => s.score !== null)
const needsWork = submitted.filter(s => s.score! < 0.4)
const showReteachBanner = submitted.length > 0 && needsWork.length / submitted.length > 0.3
```

### Assessment type badge mapping

```typescript
const TYPE_BADGE: Record<string, { label: string; className: string }> = {
  DIAGNOSTIC:     { label: 'Diagnostic',      className: 'bg-blue-50 text-blue-700 border-blue-200' },
  TOPIC_SPECIFIC: { label: 'Topic Specific',  className: 'bg-purple-50 text-purple-700 border-purple-200' },
  PROGRESS_CHECK: { label: 'Progress Check',  className: 'bg-orange-50 text-orange-700 border-orange-200' },
  FINAL:          { label: 'Final',           className: 'bg-gray-100 text-gray-600 border-gray-200' },
}
```

### React Query

```typescript
export function useAssessmentResults(assessmentId: string) {
  return useQuery({
    queryKey: ['assessment-results', assessmentId],
    queryFn: () => apiClient.get(`/api/v1/assessments/${assessmentId}/results`),
    staleTime: 60_000,
  })
}

export function useAttemptResult(attemptId: string) {
  return useQuery({
    queryKey: ['attempt-result', attemptId],
    queryFn: () => apiClient.get(`/api/v1/attempts/${attemptId}/results`),
    // Returns correct_answer_key for teachers — confirmed in M1-3-T2
    staleTime: 60_000,
  })
}
```

### API Calls

| Action | Endpoint |
|---|---|
| Assessment metadata + type | `GET /api/v1/assessments/{id}` |
| Per-student result | `GET /api/v1/attempts/{attemptId}/results` |

---

## Playwright E2E

```typescript
test('results_default_sort_lowest_score_first', ...)       // Vidhya
test('results_assessment_type_badge_visible', ...)          // Vidhya
test('results_reteach_banner_when_over_30pct_fail', ...)   // Vidhya
test('results_kpi_shows_skeleton_not_zeros_during_load', ...)// Pixel
test('results_chart_has_aria_label', ...)                   // Pixel
test('results_chart_has_visible_legend', ...)               // Pixel
test('results_score_ring_respects_reduced_motion', ...)     // Pixel
test('results_score_ring_has_aria_label', ...)              // Pixel
test('results_correct_answer_no_redundant_correct_row', ...)// Vidhya
test('results_wrong_answer_shows_given_and_correct', ...)   // Vidhya
test('results_question_pagination_expand_collapse', ...)    // Pixel
test('results_no_green_action_buttons', ...)                // Teacher design spec
```

---

## Acceptance Criteria

- [ ] Assessment type badge visible — teachers interpret scores in context (Vidhya)
- [ ] Default sort: lowest score first (Vidhya)
- [ ] Reteaching banner when > 30% score below 40% (Vidhya)
- [ ] KPI skeletons shown during load — never show 0s (Pixel)
- [ ] Distribution chart: horizontal bars, NOT pie (Pixel + Vidhya)
- [ ] Chart `aria-label` + visible text legend (Pixel)
- [ ] Score ring animation respects `prefers-reduced-motion` (Pixel)
- [ ] Score ring has `aria-label` and SVG `<title>` (Pixel)
- [ ] Correct answers: "Answer: X ✓" only (Vidhya)
- [ ] Wrong answers: "Given: X ✕" AND "Correct: Y ✓" (Vidhya)
- [ ] Band label shown alongside percentage (Vidhya)
- [ ] Question pagination: 6 visible, expand/collapse (Pixel)
- [ ] No green action buttons (Teacher design spec)
- [ ] All keyboard navigable (Pixel)
- [ ] WCAG AA contrast on all text (Pixel)
