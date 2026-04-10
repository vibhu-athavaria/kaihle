/**
 * Unit tests for ScoreDistributionChart component.
 * Tests reteach banner visibility based on the 30% threshold.
 */
import "@testing-library/jest-dom";
import React from "react";
import { render, screen } from "@testing-library/react";
import { ScoreDistributionChart } from "../components/results/ScoreDistributionChart";
import type { StudentAttemptSummary } from "../hooks/useAssessmentResults";

function makeAttempt(
  overrides: Partial<StudentAttemptSummary> = {},
): StudentAttemptSummary {
  return {
    attemptId: `attempt-${Math.random()}`,
    studentId: `student-${Math.random()}`,
    studentName: "Test Student",
    score: 0.75,
    submittedAt: new Date().toISOString(),
    status: "SUBMITTED",
    ...overrides,
  };
}

describe("ScoreDistributionChart", () => {
  test("test_reteach_banner_when_over_30pct_needs_work_then_banner_visible", () => {
    // 4 submitted, 2 score < 0.4 → 50% needs work > 30% threshold
    const attempts: StudentAttemptSummary[] = [
      makeAttempt({ score: 0.2, status: "SUBMITTED" }), // needs work
      makeAttempt({ score: 0.3, status: "SUBMITTED" }), // needs work
      makeAttempt({ score: 0.75, status: "SUBMITTED" }), // strong
      makeAttempt({ score: 0.6, status: "SUBMITTED" }), // developing
    ];

    render(<ScoreDistributionChart attempts={attempts} />);

    expect(
      screen.getByText(/More than 30% of students scored below 40%/),
    ).toBeInTheDocument();
  });

  test("test_reteach_banner_when_exactly_30pct_needs_work_then_banner_hidden", () => {
    // 10 submitted, 3 score < 0.4 → exactly 30% — NOT > 30%, banner hidden
    const attempts: StudentAttemptSummary[] = [
      ...Array.from({ length: 3 }, () =>
        makeAttempt({ score: 0.2, status: "SUBMITTED" }),
      ), // needs work
      ...Array.from({ length: 7 }, () =>
        makeAttempt({ score: 0.8, status: "SUBMITTED" }),
      ), // strong
    ];

    render(<ScoreDistributionChart attempts={attempts} />);

    expect(
      screen.queryByText(/More than 30% of students scored below 40%/),
    ).not.toBeInTheDocument();
  });

  test("test_reteach_banner_when_under_30pct_needs_work_then_banner_hidden", () => {
    // 4 submitted, 1 scores < 0.4 → 25% needs work < 30% threshold
    const attempts: StudentAttemptSummary[] = [
      makeAttempt({ score: 0.3, status: "SUBMITTED" }), // needs work
      makeAttempt({ score: 0.75, status: "SUBMITTED" }), // strong
      makeAttempt({ score: 0.8, status: "SUBMITTED" }), // strong
      makeAttempt({ score: 0.6, status: "SUBMITTED" }), // developing
    ];

    render(<ScoreDistributionChart attempts={attempts} />);

    expect(
      screen.queryByText(/More than 30% of students scored below 40%/),
    ).not.toBeInTheDocument();
  });

  test("test_reteach_banner_when_no_submissions_then_banner_hidden", () => {
    // 0 submitted — banner must not show even if 100% theoretical
    const attempts: StudentAttemptSummary[] = [
      makeAttempt({ score: null, status: "NOT_STARTED" }),
      makeAttempt({ score: null, status: "NOT_STARTED" }),
    ];

    render(<ScoreDistributionChart attempts={attempts} />);

    expect(
      screen.queryByText(/More than 30% of students scored below 40%/),
    ).not.toBeInTheDocument();
  });

  test("test_reteach_banner_when_all_submitted_need_work_then_banner_visible", () => {
    // All 5 submitted score < 0.4 → 100% needs work
    const attempts: StudentAttemptSummary[] = Array.from({ length: 5 }, () =>
      makeAttempt({ score: 0.15, status: "SUBMITTED" }),
    );

    render(<ScoreDistributionChart attempts={attempts} />);

    expect(
      screen.getByText(/More than 30% of students scored below 40%/),
    ).toBeInTheDocument();
  });

  test("test_chart_when_rendered_then_has_role_img_and_aria_label", () => {
    const attempts = [
      makeAttempt({ score: 0.8, status: "SUBMITTED" }),
      makeAttempt({ score: 0.5, status: "SUBMITTED" }),
    ];

    render(<ScoreDistributionChart attempts={attempts} />);

    const chart = screen.getByRole("img");
    const ariaLabel = chart.getAttribute("aria-label");
    expect(ariaLabel).toMatch(/Score distribution:/);
  });

  test("test_chart_when_rendered_then_shows_all_four_legend_labels", () => {
    const attempts = [makeAttempt()];
    render(<ScoreDistributionChart attempts={attempts} />);

    expect(screen.getByText("Strong (≥70%)")).toBeInTheDocument();
    expect(screen.getByText("Developing (40–69%)")).toBeInTheDocument();
    expect(screen.getByText("Needs Work (<40%)")).toBeInTheDocument();
    expect(screen.getByText("Not submitted")).toBeInTheDocument();
  });
});
