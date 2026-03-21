# M6-1-T2 — Analytics Dashboard UI (School Admin App)
**Milestone:** M6 · **Epic:** M6-1 · **Task:** T2
**Depends on:** M6-1-T1 (analytics routes return real data)
**Blocks:** Nothing — final feature UI in M6
**Estimated effort:** 4–5 hours

---

## App Target — Critical Correction

This task builds in `frontend/apps/school-admin`. Not `apps/teacher`. Not
`apps/kaihle-admin`.

The previous version of this task file incorrectly specified the path as
`apps/teacher/src/pages/admin/AnalyticsDashboard.tsx`. That is wrong — the analytics
dashboard is a school admin feature, and school admin pages live in the school admin
app. Any developer who built at that path would be adding school management UI to
the teacher's workspace, which violates the five-app architecture from CONSTITUTION
Rule 14.

The correct file paths are under `frontend/apps/school-admin/src/pages/analytics/`.

Read `docs/design/DESIGN_SYSTEM.md` §5.2 (School Admin) before writing anything. The
school admin app uses a sage green palette (`brand-school-admin #4a7c59`) and the
Inter font throughout.

---

## User Story

As a school admin, I want a dashboard showing how my school is progressing through
onboarding, assessments, and study plans so I can identify which classes or teachers
need support.

---

## Files to Create

```
frontend/apps/school-admin/src/pages/analytics/
  AnalyticsDashboardPage.tsx    ← main analytics page
  components/
    KpiCard.tsx                  ← single metric card (count + label + trend)
    OnboardingProgressBar.tsx    ← onboarding completion rate progress bar
    ClassBreakdownTable.tsx      ← table of all classes with metrics
    MasteryBySubjectChart.tsx    ← recharts bar chart of avg mastery per subject

frontend/apps/school-admin/src/tests/
  analytics-dashboard.spec.ts   ← Playwright E2E tests
  KpiCard.test.tsx               ← Jest unit tests
```

---

## Route

`/school-admin/analytics` — `AnalyticsDashboardPage`. Protected by `PrivateRoute` +
`RoleRoute(['SCHOOL_ADMIN', 'KAIHLE_ADMIN'])`. The KaihleAdmin role is included
because KaihleAdmin may view any school's analytics (and the impersonation token from
M6-1-T1 carries `KAIHLE_ADMIN` role).

---

## Complete List of API Calls This UI Makes

`GET /api/v1/schools/{schoolId}/analytics` — called once by `useSchoolAnalytics(schoolId)`
on page mount. This single endpoint provides all data for the entire dashboard. There
are no secondary data fetches.

That is the only API call. The `schoolId` comes from `current_user.school_id` stored
in the auth context. For a KaihleAdmin viewing a specific school via the impersonation
token, it comes from the token's `impersonated_school_id` claim.

---

## Page Layout (`AnalyticsDashboardPage.tsx`)

The page is divided into four vertical sections.

**KPI row:** Four `KpiCard` components in a 2×2 grid on mobile, four columns on
desktop. The four KPIs are: Total Students, Active This Week, Assessments Completed,
and Onboarding Completion Rate (expressed as a percentage here, not a decimal).

**Onboarding section:** An `OnboardingProgressBar` showing the completion rate as a
wide progress bar, the count of students pending onboarding below it, and an
explanatory sentence: "Students must complete a learning profile and at least one
diagnostic per subject to be counted as fully onboarded."

**Mastery by subject:** A `MasteryBySubjectChart` using Recharts. One bar per subject
showing the average mastery score. Bar colours use the mastery colour bands (red for
below 0.4, amber for 0.4–0.7, green above 0.7). The y-axis shows 0–100%. Hovering
a bar shows a tooltip with the exact percentage and the number of students assessed.

This chart data is derived from the `classes` breakdown in the `SchoolAnalytics`
response — group by subject, average the per-class `avg_mastery` values. There is no
separate API call for this.

**Class breakdown table:** A `ClassBreakdownTable` showing all classes from the
`classes` array. Columns: Class Name, Subject, Grade, Teacher, Students, Avg Mastery
(shown as a coloured percentage badge), and Assessments Completed.

The table is sorted by Avg Mastery ascending by default (lowest-performing classes
at the top) so the school admin's attention is drawn to where help is needed most.
Allow sorting by any column via column header clicks.

---

## `KpiCard` Component

```typescript
interface KpiCardProps {
  label: string           // e.g. "Total Students"
  value: number | string  // e.g. 47 or "83%"
  icon: React.ReactNode   // a Lucide icon component
  description?: string    // optional explanatory tooltip text
}
```

The card shows the value in a large bold number, the label below in a muted size,
and the icon in the top-right corner in the school admin green. If `description` is
provided, show a small ⓘ icon that reveals a tooltip on hover.

---

## `OnboardingProgressBar` Component

The progress bar shows the `onboarding_completion_rate` (0.0–1.0) as a filled
horizontal bar. The fill colour transitions from red (0%) to amber (40%) to green
(70%+) based on the current rate, using the standard mastery colour bands. The
percentage label is shown above the right end of the bar.

Below the bar: "{ students_pending_onboarding } students have not yet completed
onboarding." If this number is zero, show "✅ All students have completed onboarding!"
in green text instead.

---

## `MasteryBySubjectChart` Component

Use `BarChart` from `recharts`. The data format expected by the chart is derived from
the `classes` array:

```typescript
const chartData = subjects.map(subject => ({
  subject: subject.name,
  avg_mastery_pct: Math.round(avg_mastery_for_subject * 100),
  student_count: student_count_for_subject,
}))
```

The bar fill color is determined by `avg_mastery_pct`:
below 40 → `#EF4444`, 40–70 → `#F59E0B`, above 70 → `#16a34a` (same mastery
bands used throughout Kaihle). Do not use the Tailwind class here because Recharts
requires inline CSS colour strings.

If no mastery data exists (no assessments taken yet), show a placeholder inside the
chart area: "No assessment data yet. Mastery scores will appear here once students
complete their first diagnostic."

---

## Acceptance Criteria

**Playwright E2E tests in `analytics-dashboard.spec.ts`**

`test_dashboard_when_loaded_then_four_kpi_cards_visible` — Navigate to
`/school-admin/analytics`. Assert four KPI card elements are present on the page.

`test_dashboard_kpi_shows_correct_total_students` — Mock the analytics API to return
`total_students: 42`. Assert a card showing "42" is visible.

`test_dashboard_onboarding_bar_when_rate_0_6_then_amber_fill` — Mock
`onboarding_completion_rate: 0.6`. Assert the progress bar has the amber colour class.

`test_dashboard_onboarding_bar_when_all_complete_then_success_message` — Mock
`students_pending_onboarding: 0`. Assert the "All students have completed onboarding!"
message is visible instead of the pending count.

`test_dashboard_class_table_when_multiple_classes_then_sorted_by_mastery_ascending` —
Mock the analytics API to return two classes with `avg_mastery: 0.8` and `avg_mastery: 0.3`.
Assert the class with 0.3 mastery appears in the first data row of the table.

`test_dashboard_class_table_when_column_header_clicked_then_sort_changes` — Click the
"Class Name" column header. Assert the rows reorder alphabetically by class name.

`test_dashboard_mastery_chart_when_no_data_then_placeholder_shown` — Mock all classes
with `avg_mastery: null`. Assert the "No assessment data yet" placeholder message is
visible inside the chart area.

`test_dashboard_when_school_admin_role_then_200_accessible` — Authenticate as a school
admin. Assert the page loads without a redirect or error.

`test_dashboard_when_teacher_role_then_redirected` — Authenticate as a teacher and
navigate to `/school-admin/analytics`. Assert the URL changes away from that path
(redirect to teacher dashboard).

**Jest unit tests in `KpiCard.test.tsx`**

`test_kpi_card_displays_label_and_value` — Render `KpiCard` with `label="Total Students"`
and `value=47`. Assert both texts are present in the rendered output.

`test_kpi_card_when_description_provided_then_info_icon_shown` — Render with a
`description` prop. Assert an ⓘ icon element is present.

`test_kpi_card_when_no_description_then_no_info_icon` — Render without a `description`
prop. Assert no ⓘ icon is present.

`test_onboarding_bar_when_rate_0_75_then_green_fill_class` — Render
`OnboardingProgressBar` with `rate=0.75`. Assert the filled bar element has the green
colour style.

`test_onboarding_bar_percentage_label_shows_rounded_value` — `rate=0.6333`. Assert
the label shows "63%" (rounded down to integer).

---

## Do NOT Touch

`frontend/apps/teacher/` — no code goes here. `frontend/apps/student/` — no code.
`frontend/apps/parent/` — no code. Any backend file. The `useSchoolAnalytics` hook
from M0-10-T10 — use as-is, do not rewrite it.
