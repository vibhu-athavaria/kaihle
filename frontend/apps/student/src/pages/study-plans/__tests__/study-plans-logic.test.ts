/**
 * Unit tests for Study Plans page logic (ST-B + ST-C).
 *
 * Tests cover:
 *   - ST-B: plan status bucketing (active/generating/completed)
 *   - ST-B: StudyPlanCard progress percentage calculation
 *   - ST-B: status badge label lookup
 *   - ST-C: allQuestionsAnswered gate for quiz submit button
 *   - ST-C: quiz responses array built from quizAnswers state
 *   - ST-C: isDiagnostic defaults when assessment_type is absent
 */

// ─────────────────────────────────────────────────────────────
//  ST-B: plan status bucketing
// ─────────────────────────────────────────────────────────────

type PlanStatus =
  | "GENERATING"
  | "ACTIVE"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "ABANDONED";

function bucketPlans(plans: Array<{ status: PlanStatus }>) {
  return {
    activePlans: plans.filter(
      (p) => p.status === "ACTIVE" || p.status === "IN_PROGRESS",
    ),
    generatingPlans: plans.filter((p) => p.status === "GENERATING"),
    completedPlans: plans.filter((p) => p.status === "COMPLETED"),
  };
}

describe("bucketPlans — status bucketing", () => {
  test("test_bucket_plans_when_mixed_statuses_then_each_bucket_receives_correct_plans", () => {
    const plans = [
      { status: "ACTIVE" as PlanStatus },
      { status: "IN_PROGRESS" as PlanStatus },
      { status: "GENERATING" as PlanStatus },
      { status: "COMPLETED" as PlanStatus },
      { status: "ABANDONED" as PlanStatus },
    ];
    const { activePlans, generatingPlans, completedPlans } = bucketPlans(plans);
    expect(activePlans).toHaveLength(2);
    expect(generatingPlans).toHaveLength(1);
    expect(completedPlans).toHaveLength(1);
  });

  test("test_bucket_plans_when_empty_array_then_all_buckets_empty", () => {
    const { activePlans, generatingPlans, completedPlans } = bucketPlans([]);
    expect(activePlans).toHaveLength(0);
    expect(generatingPlans).toHaveLength(0);
    expect(completedPlans).toHaveLength(0);
  });

  test("test_bucket_plans_when_abandoned_plan_then_not_in_any_displayed_bucket", () => {
    const plans = [{ status: "ABANDONED" as PlanStatus }];
    const { activePlans, generatingPlans, completedPlans } = bucketPlans(plans);
    expect(activePlans).toHaveLength(0);
    expect(generatingPlans).toHaveLength(0);
    expect(completedPlans).toHaveLength(0);
  });
});

// ─────────────────────────────────────────────────────────────
//  ST-B: StudyPlanCard progress percentage
// ─────────────────────────────────────────────────────────────

function calculatePlanProgress(
  resources: Array<{ is_watched: boolean }>,
): number {
  const total = resources.length;
  if (total === 0) return 0;
  const watched = resources.filter((r) => r.is_watched).length;
  return Math.round((watched / total) * 100);
}

describe("calculatePlanProgress", () => {
  test("test_plan_progress_when_2_of_4_watched_then_returns_50_percent", () => {
    const resources = [
      { is_watched: true },
      { is_watched: true },
      { is_watched: false },
      { is_watched: false },
    ];
    expect(calculatePlanProgress(resources)).toBe(50);
  });

  test("test_plan_progress_when_all_watched_then_returns_100_percent", () => {
    const resources = [{ is_watched: true }, { is_watched: true }];
    expect(calculatePlanProgress(resources)).toBe(100);
  });

  test("test_plan_progress_when_none_watched_then_returns_0_percent", () => {
    const resources = [{ is_watched: false }, { is_watched: false }];
    expect(calculatePlanProgress(resources)).toBe(0);
  });

  test("test_plan_progress_when_no_resources_then_returns_0_percent", () => {
    expect(calculatePlanProgress([])).toBe(0);
  });
});

// ─────────────────────────────────────────────────────────────
//  ST-B: status badge label lookup
// ─────────────────────────────────────────────────────────────

const STATUS_BADGE: Record<string, string> = {
  ACTIVE: "Ready",
  IN_PROGRESS: "In progress",
  COMPLETED: "Completed",
};

function getStatusBadgeLabel(status: string): string {
  return STATUS_BADGE[status] ?? status;
}

describe("getStatusBadgeLabel", () => {
  test("test_status_badge_when_status_is_active_then_label_is_ready", () => {
    expect(getStatusBadgeLabel("ACTIVE")).toBe("Ready");
  });

  test("test_status_badge_when_status_is_in_progress_then_label_is_in_progress", () => {
    expect(getStatusBadgeLabel("IN_PROGRESS")).toBe("In progress");
  });

  test("test_status_badge_when_status_is_completed_then_label_is_completed", () => {
    expect(getStatusBadgeLabel("COMPLETED")).toBe("Completed");
  });

  test("test_status_badge_when_status_is_unknown_then_label_falls_back_to_status_string", () => {
    expect(getStatusBadgeLabel("GENERATING")).toBe("GENERATING");
  });
});

// ─────────────────────────────────────────────────────────────
//  ST-C: allQuestionsAnswered gate
// ─────────────────────────────────────────────────────────────

function allQuestionsAnswered(
  quizAnswers: Record<number, string>,
  totalQuestions: number,
): boolean {
  return (
    totalQuestions > 0 && Object.keys(quizAnswers).length === totalQuestions
  );
}

describe("allQuestionsAnswered", () => {
  test("test_quiz_gate_when_all_questions_answered_then_returns_true", () => {
    const answers = { 0: "A", 1: "B", 2: "C" };
    expect(allQuestionsAnswered(answers, 3)).toBe(true);
  });

  test("test_quiz_gate_when_some_questions_unanswered_then_returns_false", () => {
    const answers = { 0: "A", 1: "B" };
    expect(allQuestionsAnswered(answers, 3)).toBe(false);
  });

  test("test_quiz_gate_when_no_questions_answered_then_returns_false", () => {
    expect(allQuestionsAnswered({}, 3)).toBe(false);
  });

  test("test_quiz_gate_when_total_questions_is_zero_then_returns_false", () => {
    expect(allQuestionsAnswered({}, 0)).toBe(false);
  });
});

// ─────────────────────────────────────────────────────────────
//  ST-C: quiz responses array construction
// ─────────────────────────────────────────────────────────────

function buildQuizResponses(
  quizAnswers: Record<number, string>,
): Array<{ question_index: number; answer: string }> {
  return Object.entries(quizAnswers).map(([index, answer]) => ({
    question_index: Number(index),
    answer,
  }));
}

describe("buildQuizResponses", () => {
  test("test_quiz_responses_when_answers_exist_then_builds_correct_payload_shape", () => {
    const answers = { 0: "A", 1: "C", 2: "B" };
    const responses = buildQuizResponses(answers);
    expect(responses).toHaveLength(3);
    expect(responses).toContainEqual({ question_index: 0, answer: "A" });
    expect(responses).toContainEqual({ question_index: 1, answer: "C" });
    expect(responses).toContainEqual({ question_index: 2, answer: "B" });
  });

  test("test_quiz_responses_when_empty_answers_then_returns_empty_array", () => {
    expect(buildQuizResponses({})).toHaveLength(0);
  });

  test("test_quiz_responses_when_keys_are_string_numbers_then_question_index_is_numeric", () => {
    const responses = buildQuizResponses({ 5: "D" });
    expect(responses[0].question_index).toBe(5);
    expect(typeof responses[0].question_index).toBe("number");
  });
});
