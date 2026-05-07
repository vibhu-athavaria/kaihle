# ST-A — Dashboard: Fix NextStep Actions + Streak Placeholder
Executor: Coding agent
Branch: `st-a-dashboard-actions` (branch from `main`)

---

## Context

The student dashboard has a "What's waiting for you" section with `NextStepCard` components. Every card renders an action label ("Start now →", "View plans →") but clicking does nothing — `onAction` is never passed in `StudentDashboard.tsx`. This is a P0 usability bug.

Additionally, the dashboard needs a streak bar. The backend `streakDays` field exists but always returns `null` (not yet implemented). Show a visual placeholder only — no backend work.

---

## Files to Modify

- `frontend/apps/student/src/pages/dashboard/StudentDashboard.tsx`
- `frontend/apps/student/src/pages/dashboard/NextStepCard.tsx`
- `frontend/apps/student/src/pages/dashboard/SubjectScoresSection.tsx`

---

## Task 1 — Fix NextStepCard to navigate internally

**File:** `src/pages/dashboard/NextStepCard.tsx`

Remove the `onAction?: () => void` prop entirely. The card navigates itself using `useNavigate`.

Replace the component with:

```tsx
import { useNavigate } from "react-router-dom";

interface NextStepCardProps {
  type: "assessment" | "study-plan-ready" | "study-plan-progress" | "weakest-area";
  title: string;
  subtitle: string;
  actionLabel: string;
  route: string;           // ← new required prop replacing onAction
  urgent?: boolean;        // ← new: shows red tint when true
}

const emojiMap: Record<string, string> = {
  assessment: "📝",
  "study-plan-ready": "📚",
  "study-plan-progress": "📈",
  "weakest-area": "🎯",
};

export function NextStepCard({
  type,
  title,
  subtitle,
  actionLabel,
  route,
  urgent = false,
}: NextStepCardProps) {
  const navigate = useNavigate();
  const emoji = emojiMap[type];

  return (
    <div
      className={`border rounded-card px-3.5 py-2.5 flex items-center justify-between ${
        urgent
          ? "bg-red-50 border-red-200"
          : "bg-white border-role-student-border"
      }`}
    >
      <div className="flex items-center gap-2.5">
        <span className="text-step-title w-4 text-center flex-shrink-0" role="img" aria-label={type}>
          {emoji}
        </span>
        <div>
          <div className={`font-sans font-semibold text-step-title ${urgent ? "text-red-800" : "text-brand-ink"}`}>
            {title}
          </div>
          <div className="font-sans text-step-sub text-brand-muted mt-0.5">{subtitle}</div>
        </div>
      </div>
      <button
        type="button"
        onClick={() => navigate(route)}
        className={`font-sans font-bold text-step-action whitespace-nowrap hover:underline min-h-[44px] flex items-center ml-3 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 ${
          urgent ? "text-red-700" : "text-brand-primary"
        }`}
      >
        {actionLabel}
      </button>
    </div>
  );
}
```

Keep `EmptyNextSteps` unchanged.

---

## Task 2 — Update buildNextSteps to return route and urgent flag

**File:** `src/pages/dashboard/StudentDashboard.tsx`

Update the `NextStep` interface:

```ts
interface NextStep {
  type: "assessment" | "study-plan-ready" | "study-plan-progress" | "weakest-area";
  id: string;
  title: string;
  subtitle: string;
  actionLabel: string;
  route: string;       // ← new
  urgent?: boolean;    // ← new
}
```

Update `buildNextSteps` route assignments:

```ts
// Priority 1: assessments — route to assessments page, mark urgent if due ≤ 3 days
const daysUntilDue = assessments.length > 0
  ? Math.ceil((new Date(assessments[0].dueDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
  : null;

nextSteps.push({
  type: "assessment",
  id: `assessment-${assessments[0].id}`,
  title: `${assessments.length} assessment${assessments.length > 1 ? "s" : ""} due`,
  subtitle: `${assessments[0].subjectName} · Due ${new Date(assessments[0].dueDate).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`,
  actionLabel: "Start now →",
  route: "/student/assessments",
  urgent: daysUntilDue !== null && daysUntilDue <= 3,
});

// Priority 2: study plans ready (ACTIVE)
nextSteps.push({
  type: "study-plan-ready",
  id: "study-plan-ready",
  title: `${activeStudyPlans.length} study plan${activeStudyPlans.length > 1 ? "s" : ""} ready`,
  subtitle: "Start learning where it counts",
  actionLabel: "Begin →",
  route: "/student/study-plans",
});

// Priority 3: study plan in progress
nextSteps.push({
  type: "study-plan-progress",
  id: `study-plan-progress-${inProgressStudyPlans[0].id}`,
  title: "Continue your study plan",
  subtitle: inProgressStudyPlans[0].title,
  actionLabel: "Continue →",
  route: `/student/study-plans/${inProgressStudyPlans[0].id}`,
});

// Priority 4: weakest area
nextSteps.push({
  type: "weakest-area",
  id: `weakest-${weakest.subjectName}`,
  title: `Your weakest area: ${weakest.subjectName}`,
  subtitle: `${Math.round((weakest.avgMastery ?? 0) * 100)}% — keep going`,
  actionLabel: "View progress →",
  route: "/student/my-progress",
});
```

Update the render call — remove `onAction`, pass `route` and `urgent`:

```tsx
nextSteps.slice(0, 3).map((step) => (
  <NextStepCard
    key={step.id}
    type={step.type}
    title={step.title}
    subtitle={step.subtitle}
    actionLabel={step.actionLabel}
    route={step.route}
    urgent={step.urgent}
  />
))
```

---

## Task 3 — Add Study Plans badge to sidebar

**File:** `frontend/packages/ui/src/layouts/StudentLayout.tsx`

Read this file first. The sidebar nav renders nav items in a list. Find the "Study plans" nav item and add a badge showing the count of active + in-progress plans.

The `StudentLayout` component receives a `classes` prop already. Add a new optional prop:

```ts
studyPlanBadge?: number;   // count of ACTIVE + IN_PROGRESS plans to show on sidebar
```

In the sidebar nav item for Study Plans, render the badge when `studyPlanBadge > 0`:

```tsx
<span className="ml-auto bg-brand-primary text-white text-[8px] font-bold px-1.5 py-0.5 rounded-full leading-none">
  {studyPlanBadge}
</span>
```

**In `StudentDashboard.tsx`:** derive the badge count from `dashboardData`:

```ts
const studyPlanBadgeCount = (
  (dashboardData?.studyPlans ?? []).filter(
    (sp) => sp.status === "ACTIVE" || sp.status === "IN_PROGRESS"
  ).length
) || undefined;
```

Pass it: `<StudentLayout ... studyPlanBadge={studyPlanBadgeCount}>`. 

Also pass `studyPlanBadge` through in `MyProgress.tsx`, `StudyPlans.tsx`, `Assessments.tsx`, and `AssessmentResultsPage.tsx` — each of these uses `StudentLayout`. For these pages, pass `studyPlanBadge={undefined}` (badge only shown on dashboard for now — acceptable for MVP).

---

## Task 4 — Add streak placeholder bar

**File:** `src/pages/dashboard/StudentDashboard.tsx`

After the subject scores section and before the "What's next for you" section, add:

```tsx
{/* Streak placeholder — backend streakDays always null until implemented */}
<div className="bg-white border border-brand-border rounded-card px-4 py-3 flex items-center gap-3">
  <span className="text-brand-muted text-lg">🔥</span>
  <div>
    <div className="font-sans font-semibold text-sm text-brand-muted">
      Daily streak — coming soon
    </div>
    <div className="font-sans text-xs text-brand-muted">
      Keep checking in daily to build your streak
    </div>
  </div>
</div>
```

Do NOT render this based on `streakDays` — always show it. When the backend implements streaks, this component will be replaced.

---

## Acceptance Criteria

- [ ] Clicking "Start now →" on an assessment card navigates to `/student/assessments`
- [ ] Clicking "Begin →" on a study plan card navigates to `/student/study-plans`
- [ ] Clicking "Continue →" on in-progress card navigates to `/student/study-plans/:planId`
- [ ] Clicking "View progress →" on weakest-area card navigates to `/student/my-progress`
- [ ] Assessment card with due date ≤ 3 days shows red tint (`urgent={true}`)
- [ ] Study Plans sidebar item shows green badge when plans are active/in-progress
- [ ] Streak placeholder bar renders between subject scores and "What's next" section
- [ ] TypeScript compiles with zero errors (`pnpm typecheck`)
- [ ] No ESLint errors (`pnpm lint`)
