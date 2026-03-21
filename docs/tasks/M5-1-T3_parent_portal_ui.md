# M5-1-T3 — Parent Portal UI (Parent App)
**Milestone:** M5 · **Epic:** M5-1 · **Task:** T3
**Depends on:** M5-1-T2 (parent API routes return real data)
**Blocks:** Nothing — final task of M5
**Estimated effort:** 5–6 hours

---

## Context

All code in this task lives in `frontend/apps/parent`. No code goes in any other app.

Read `docs/design/DESIGN_SYSTEM.md` §5.5 (Parent) before writing anything. The parent
app uses a warm cream background (`bg-role-parent-bg #fdf8f0`), the Lora serif font
for headings, and a calm, non-technical visual language. It is mobile-first — design
for 375px width as the primary canvas.

The three React Query hooks (`useMyChildren`, `useChildReports`, `useChildGapMap`)
already exist from M0-10-T12. They now return real data after M5-1-T2 completes.

---

## User Story

As a parent, I want a warm, simple dashboard that shows me my child's latest progress
summary and lets me explore their topic map without needing to understand educational
jargon or numeric scores.

---

## Files to Create

```
frontend/apps/parent/src/pages/
  DashboardPage.tsx             ← landing page after login
  ChildProgressPage.tsx         ← detailed progress for one child

frontend/apps/parent/src/components/
  ChildSelector.tsx             ← dropdown to switch between children
  NarrativeCard.tsx             ← latest weekly narrative + highlights
  SubjectOverviewCard.tsx       ← per-subject traffic-light summary
  SimpleGapMap.tsx              ← full topic-level gap map accordion
  TopicTrafficLight.tsx         ← single topic row with status indicator
  WeeklyReportAccordion.tsx     ← list of past weekly reports (expandable rows)

frontend/apps/parent/src/tests/
  parent-portal.spec.ts         ← Playwright E2E tests
  components.test.tsx           ← Jest unit tests
```

---

## Routes

`/parent/dashboard` — `DashboardPage`. Protected by `PrivateRoute` +
`RoleRoute(['PARENT'])`. The post-login redirect goes here.

`/parent/children/:studentId/progress` — `ChildProgressPage`. Same guards.

---

## Complete List of API Calls This UI Makes

`GET /api/v1/parent/children` — called once by `useMyChildren` on `DashboardPage`
mount and whenever the child selector changes.

`GET /api/v1/parent/children/{studentId}/reports?page=1&page_size=10` — called by
`useChildReports(studentId)` on both `DashboardPage` (for the latest narrative card)
and `ChildProgressPage` (for the full report history accordion).

`GET /api/v1/parent/children/{studentId}/gap-map` — called by `useChildGapMap(studentId)`
on `ChildProgressPage`.

Those are the only three API calls. Do not call any student, teacher, or gap map
endpoint directly from the parent app — all data flows through the parent portal endpoints.

---

## Child Selector (`ChildSelector.tsx`)

Shown only when the parent has two or more children. Hidden when there is exactly one
child — single-child parents should not see UI that implies managing multiple children.

On mobile, renders as a native `<select>` element for accessibility. On screens wider
than 768px, renders as a styled dropdown that shows each child's name and grade.

When the selected child changes, update the `studentId` used in all downstream queries.
Store the selected child ID in component state — not in URL params. The URL at
`/parent/dashboard` stays consistent regardless of which child is selected.

---

## Dashboard Page (`DashboardPage.tsx`)

The dashboard shows two things: the latest narrative for the selected child, and a
quick subject overview grid.

The narrative section uses `NarrativeCard` to show the most recent weekly report.
It shows the week label ("Week of 18 March 2026"), the narrative text (truncated to
three lines with a "Read more" toggle that expands inline — do not navigate away),
and a highlights list (the `highlights` array from the report, shown as small pill
badges). If no reports exist yet, show a placeholder card: "Your first weekly update
will appear here after your child completes their first diagnostic."

The subject overview shows one `SubjectOverviewCard` per subject from the child's
`ChildSummary.subjects` list. Each card shows the subject name and a row of topic
traffic-light dots. The dots come from the child's gap map — aggregate to topic level.
Tapping a subject card navigates to `/parent/children/{studentId}/progress` with that
subject pre-selected.

---

## Child Progress Page (`ChildProgressPage.tsx`)

The progress page has two tab sections: "Progress Map" and "Weekly Reports."

**Progress Map tab:** Shows `SimpleGapMap` for the selected child. At the top, show
a brief legend: 🟢 Strong  🟡 Developing  🔴 Needs Work. Below the legend, render one
accordion group per subject. Within each subject, list topics using `TopicTrafficLight`.

**Weekly Reports tab:** Shows `WeeklyReportAccordion` — a vertical list of past
reports, each as a collapsed row. The row header shows the week date and subject name.
Expanding a row shows the full narrative text and the highlights as bullet points.
The most recent report is expanded by default when the tab loads.

---

## TopicTrafficLight (`TopicTrafficLight.tsx`)

```typescript
interface TopicTrafficLightProps {
  topicName: string
  status: 'Strong' | 'Developing' | 'Needs Work' | 'Not yet assessed'
  statusLabel: 'green' | 'amber' | 'red' | 'grey'
}
```

Renders a single row with a coloured circle and the topic name. The circle must carry
`aria-label={topicName + ': ' + status}` — colour is never the only indicator.

Status to CSS class mapping (use design token variables from `DESIGN_SYSTEM.md`):
green → `bg-brand-mastery-strong` (#16a34a), amber → `bg-brand-mastery-developing`
(#F59E0B), red → `bg-brand-mastery-needs-work` (#EF4444), grey → `bg-gray-300`.

Never hardcode hex strings in the component — use the design token class names.

---

## SimpleGapMap (`SimpleGapMap.tsx`)

Renders the `ParentGapMap` response as an accordion grouped by subject. Each subject
group can be collapsed or expanded. Within a subject group, topics are rendered in
the order received from the API (which sorts Needs Work first — see M5-1-T2).

When all a subject's topics are Strong, show a subtle green celebration row: "Great
work in [subject]! 🌟" instead of the topic list. This is a small but meaningful
positive reinforcement moment for the parent.

---

## Mobile-First Layout Rules

All cards stack vertically on a 375px screen. No horizontal overflow anywhere.
Subject tabs on the progress page scroll horizontally with `overflow-x: auto`
and `-webkit-overflow-scrolling: touch` for smooth momentum scrolling on iOS.
All interactive elements have a minimum tap target of 44×44px. Accordion rows
have at minimum 48px height. The child selector `<select>` element uses the native
font and size on mobile for OS-level accessibility.

---

## Acceptance Criteria

**Playwright E2E tests in `parent-portal.spec.ts`**

`test_dashboard_when_one_child_then_no_child_selector_shown` — Seed one parent linked
to one student. Navigate to the dashboard. Assert no child selector element is visible.

`test_dashboard_when_two_children_then_child_selector_shown` — Seed two linked children.
Assert a selector element is visible showing both children's names.

`test_dashboard_when_child_switched_then_narrative_updates` — Mock reports for two
different children with different narrative texts. Switch the child selector. Assert
the narrative text changes to the second child's report.

`test_dashboard_when_reports_exist_then_latest_narrative_shown` — Mock the reports API
to return two reports for different weeks. Assert the most recent week's narrative is
shown in the narrative card.

`test_dashboard_when_no_reports_then_placeholder_card_shown` — Mock the reports API
to return an empty list. Assert the placeholder message about the first diagnostic is
visible.

`test_dashboard_subject_card_when_clicked_then_navigates_to_progress_page` — Click a
subject overview card. Assert the URL changes to `/parent/children/{id}/progress`.

`test_progress_page_gap_map_tab_shows_topics_grouped_by_subject` — Navigate to the
progress page. Assert accordion groups with subject names are visible and each group
contains topic rows.

`test_progress_page_topic_traffic_light_shows_needs_work_first` — Seed a subject with
one Needs Work topic and one Strong topic. Assert the Needs Work topic appears above
the Strong topic in the list.

`test_progress_page_when_all_topics_strong_then_celebration_row_shown` — Seed a
subject where all topics have label "Strong". Assert the "Great work in [subject]! 🌟"
row is shown instead of the topic list.

`test_progress_page_reports_tab_most_recent_expanded_by_default` — Switch to the
Weekly Reports tab. Assert the first (most recent) accordion row is already expanded
without any user interaction.

`test_progress_page_accordion_when_row_expanded_then_narrative_text_visible` — Click
a collapsed report row. Assert the narrative text becomes visible.

`test_dashboard_responsive_at_375px_no_overflow` — Set the viewport to 375px wide.
Navigate to the dashboard. Assert no element has a scroll width greater than the
viewport width (no horizontal overflow).

**Jest unit tests in `components.test.tsx`**

`test_topic_traffic_light_when_status_needs_work_then_red_circle` — Render
`TopicTrafficLight` with `status="Needs Work"` and `statusLabel="red"`. Assert the
circle element has the `bg-brand-mastery-needs-work` class.

`test_topic_traffic_light_aria_label_includes_topic_name_and_status` — Render with
`topicName="Algebra"` and `status="Developing"`. Assert the circle has `aria-label`
containing both "Algebra" and "Developing".

`test_narrative_card_when_text_long_then_truncated_with_read_more` — Render
`NarrativeCard` with 200 words of narrative text. Assert the card initially shows
truncated text and a "Read more" button. Click "Read more." Assert the full text is
visible and the "Read more" button is gone.

`test_child_selector_when_one_child_then_not_rendered` — Render `ChildSelector` with
one child in the children list. Assert the component renders nothing (null or empty).

`test_child_selector_when_two_children_then_both_names_shown` — Render with two
children. Assert both children's first names are present in the rendered output.

`test_simple_gap_map_sorts_needs_work_before_strong` — Render `SimpleGapMap` with
a subject containing topics in mixed status order. Assert the rendered topic list
shows Needs Work topics before Strong topics.

---

## Do NOT Touch

`frontend/apps/teacher/` — no code goes here. `frontend/apps/student/` — no code
goes here. `frontend/apps/school-admin/` — no code goes here. Any backend file.
The three parent data hooks from M0-10-T12 — use them as-is.
