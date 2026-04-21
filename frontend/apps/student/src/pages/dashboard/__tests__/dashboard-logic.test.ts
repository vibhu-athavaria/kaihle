/**
 * Unit tests for student dashboard logic.
 *
 * Tests cover:
 *   - ST-A: buildNextSteps — route assignment, urgent flag, step priority
 *   - ST-A: studyPlanBadgeCount — counts only ACTIVE + IN_PROGRESS plans
 */

// ─────────────────────────────────────────────────────────────
//  Helpers extracted from StudentDashboard.tsx for testability
// ─────────────────────────────────────────────────────────────

interface NextStep {
  type:
    | "assessment"
    | "study-plan-ready"
    | "study-plan-progress"
    | "weakest-area";
  id: string;
  title: string;
  subtitle: string;
  actionLabel: string;
  route: string;
  urgent?: boolean;
}

interface ResolvedSubjectScore {
  subjectId: string;
  subjectName: string;
  avgMastery: number | null;
}

function buildNextSteps(
  assessments: Array<{ id: string; subjectName: string; dueDate: string }>,
  activeStudyPlans: Array<{ id: string; title: string; status: string }>,
  inProgressStudyPlans: Array<{ id: string; title: string; status: string }>,
  subjectScores: ResolvedSubjectScore[],
): NextStep[] {
  const nextSteps: NextStep[] = [];

  if (assessments.length > 0) {
    const daysUntilDue = Math.ceil(
      (new Date(assessments[0].dueDate).getTime() - Date.now()) /
        (1000 * 60 * 60 * 24),
    );
    nextSteps.push({
      type: "assessment",
      id: `assessment-${assessments[0].id}`,
      title: `${assessments.length} assessment${assessments.length > 1 ? "s" : ""} due`,
      subtitle: `${assessments[0].subjectName} · Due ${new Date(assessments[0].dueDate).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`,
      actionLabel: "Start now →",
      route: "/student/assessments",
      urgent: daysUntilDue <= 3,
    });
  }

  if (activeStudyPlans.length > 0) {
    nextSteps.push({
      type: "study-plan-ready",
      id: "study-plan-ready",
      title: `${activeStudyPlans.length} study plan${activeStudyPlans.length > 1 ? "s" : ""} ready`,
      subtitle: "Start learning where it counts",
      actionLabel: "Begin →",
      route: "/student/study-plans",
    });
  }

  if (inProgressStudyPlans.length > 0) {
    nextSteps.push({
      type: "study-plan-progress",
      id: `study-plan-progress-${inProgressStudyPlans[0].id}`,
      title: "Continue your study plan",
      subtitle: inProgressStudyPlans[0].title,
      actionLabel: "Continue →",
      route: `/student/study-plans/${inProgressStudyPlans[0].id}`,
    });
  }

  const assessedScores = subjectScores.filter((s) => s.avgMastery !== null);
  if (assessedScores.length > 0 && activeStudyPlans.length === 0) {
    const weakest = assessedScores.reduce((a, b) =>
      (a.avgMastery ?? 1) < (b.avgMastery ?? 1) ? a : b,
    );
    if ((weakest.avgMastery ?? 1) < 0.7) {
      nextSteps.push({
        type: "weakest-area",
        id: `weakest-${weakest.subjectName}`,
        title: `Your weakest area: ${weakest.subjectName}`,
        subtitle: `${Math.round((weakest.avgMastery ?? 0) * 100)}% — keep going`,
        actionLabel: "View progress →",
        route: "/student/my-progress",
      });
    }
  }

  return nextSteps;
}

function deriveStudyPlanBadgeCount(
  plans: Array<{ status: string }>,
): number | undefined {
  return (
    plans.filter((sp) => sp.status === "ACTIVE" || sp.status === "IN_PROGRESS")
      .length || undefined
  );
}

// ─────────────────────────────────────────────────────────────
//  buildNextSteps — route assignment
// ─────────────────────────────────────────────────────────────

const futureDate = new Date(
  Date.now() + 10 * 24 * 60 * 60 * 1000,
).toISOString();
const soonDate = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString();

describe("buildNextSteps — route assignment", () => {
  test("test_next_steps_when_assessment_exists_then_route_is_assessments_page", () => {
    const steps = buildNextSteps(
      [{ id: "a1", subjectName: "Maths", dueDate: futureDate }],
      [],
      [],
      [],
    );
    expect(steps[0].route).toBe("/student/assessments");
  });

  test("test_next_steps_when_active_study_plan_exists_then_route_is_study_plans_list", () => {
    const steps = buildNextSteps(
      [],
      [{ id: "sp1", title: "Algebra", status: "ACTIVE" }],
      [],
      [],
    );
    expect(steps[0].route).toBe("/student/study-plans");
  });

  test("test_next_steps_when_in_progress_study_plan_exists_then_route_includes_plan_id", () => {
    const steps = buildNextSteps(
      [],
      [],
      [{ id: "sp2", title: "Geometry", status: "IN_PROGRESS" }],
      [],
    );
    expect(steps[0].route).toBe("/student/study-plans/sp2");
  });

  test("test_next_steps_when_weakest_area_below_threshold_then_route_is_my_progress", () => {
    const steps = buildNextSteps(
      [],
      [],
      [],
      [{ subjectId: "s1", subjectName: "Physics", avgMastery: 0.4 }],
    );
    expect(steps[0].route).toBe("/student/my-progress");
  });
});

// ─────────────────────────────────────────────────────────────
//  buildNextSteps — urgent flag
// ─────────────────────────────────────────────────────────────

describe("buildNextSteps — urgent flag", () => {
  test("test_next_steps_when_assessment_due_within_3_days_then_urgent_is_true", () => {
    const steps = buildNextSteps(
      [{ id: "a1", subjectName: "Maths", dueDate: soonDate }],
      [],
      [],
      [],
    );
    expect(steps[0].urgent).toBe(true);
  });

  test("test_next_steps_when_assessment_due_beyond_3_days_then_urgent_is_false", () => {
    const steps = buildNextSteps(
      [{ id: "a1", subjectName: "Maths", dueDate: futureDate }],
      [],
      [],
      [],
    );
    expect(steps[0].urgent).toBe(false);
  });
});

// ─────────────────────────────────────────────────────────────
//  buildNextSteps — weakest area gating
// ─────────────────────────────────────────────────────────────

describe("buildNextSteps — weakest area gating", () => {
  test("test_next_steps_when_weakest_mastery_above_0_7_then_weakest_area_step_omitted", () => {
    const steps = buildNextSteps(
      [],
      [],
      [],
      [{ subjectId: "s1", subjectName: "Physics", avgMastery: 0.85 }],
    );
    expect(steps.find((s) => s.type === "weakest-area")).toBeUndefined();
  });

  test("test_next_steps_when_active_study_plan_exists_then_weakest_area_step_suppressed", () => {
    // Weakest-area step is only shown when there are no active plans
    const steps = buildNextSteps(
      [],
      [{ id: "sp1", title: "Algebra", status: "ACTIVE" }],
      [],
      [{ subjectId: "s1", subjectName: "Physics", avgMastery: 0.3 }],
    );
    expect(steps.find((s) => s.type === "weakest-area")).toBeUndefined();
  });

  test("test_next_steps_when_no_assessed_scores_then_weakest_area_step_omitted", () => {
    const steps = buildNextSteps(
      [],
      [],
      [],
      [{ subjectId: "s1", subjectName: "Physics", avgMastery: null }],
    );
    expect(steps.find((s) => s.type === "weakest-area")).toBeUndefined();
  });
});

// ─────────────────────────────────────────────────────────────
//  buildNextSteps — step priority (assessment first)
// ─────────────────────────────────────────────────────────────

describe("buildNextSteps — step ordering", () => {
  test("test_next_steps_when_all_step_types_present_then_assessment_is_first", () => {
    const steps = buildNextSteps(
      [{ id: "a1", subjectName: "Maths", dueDate: futureDate }],
      [{ id: "sp1", title: "Algebra", status: "ACTIVE" }],
      [{ id: "sp2", title: "Geometry", status: "IN_PROGRESS" }],
      [],
    );
    expect(steps[0].type).toBe("assessment");
    expect(steps[1].type).toBe("study-plan-ready");
    expect(steps[2].type).toBe("study-plan-progress");
  });

  test("test_next_steps_when_no_data_then_returns_empty_array", () => {
    const steps = buildNextSteps([], [], [], []);
    expect(steps).toHaveLength(0);
  });
});

// ─────────────────────────────────────────────────────────────
//  studyPlanBadgeCount — counts ACTIVE + IN_PROGRESS only
// ─────────────────────────────────────────────────────────────

describe("deriveStudyPlanBadgeCount", () => {
  test("test_badge_count_when_mix_of_statuses_then_counts_only_active_and_in_progress", () => {
    const plans = [
      { status: "ACTIVE" },
      { status: "IN_PROGRESS" },
      { status: "COMPLETED" },
      { status: "GENERATING" },
      { status: "ABANDONED" },
    ];
    expect(deriveStudyPlanBadgeCount(plans)).toBe(2);
  });

  test("test_badge_count_when_no_active_plans_then_returns_undefined", () => {
    const plans = [{ status: "COMPLETED" }, { status: "GENERATING" }];
    expect(deriveStudyPlanBadgeCount(plans)).toBeUndefined();
  });

  test("test_badge_count_when_empty_plans_array_then_returns_undefined", () => {
    expect(deriveStudyPlanBadgeCount([])).toBeUndefined();
  });

  test("test_badge_count_when_all_plans_active_then_returns_full_count", () => {
    const plans = [
      { status: "ACTIVE" },
      { status: "ACTIVE" },
      { status: "IN_PROGRESS" },
    ];
    expect(deriveStudyPlanBadgeCount(plans)).toBe(3);
  });
});
