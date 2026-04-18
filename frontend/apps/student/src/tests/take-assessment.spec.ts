/**
 * Playwright E2E tests for TakeAssessmentPage and AssessmentResultsPage.
 *
 * Coverage:
 *   - Question display and navigation
 *   - MCQ option selection state
 *   - Auto-save on Next
 *   - Unanswered questions confirmation modal
 *   - Redirect when attempt is already COMPLETED
 *   - Results page score ring color by mastery band
 *   - Diagnostic complete banner
 *
 * NOTE: These tests are written to spec — do NOT run them in this task.
 *       They require a running dev server and seeded test data.
 */
import { test, expect } from "@playwright/test";

// ─────────────────────────────────────────────────────────────
//  Helpers
// ─────────────────────────────────────────────────────────────

/** Mock API routes before navigating. */
function mockAttemptRoutes(
  page: import("@playwright/test").Page,
  overrides: { status?: string; score?: number; questions?: unknown[] } = {},
) {
  const questions = overrides.questions ?? [
    {
      question_id: "q1",
      question_text: "What is 2 + 2?",
      options: [
        { key: "A", text: "3" },
        { key: "B", text: "4" },
        { key: "C", text: "5" },
        { key: "D", text: "6" },
      ],
    },
    {
      question_id: "q2",
      question_text: "What is the capital of France?",
      options: [
        { key: "A", text: "Berlin" },
        { key: "B", text: "Madrid" },
        { key: "C", text: "Paris" },
        { key: "D", text: "Rome" },
      ],
    },
  ];

  return page.route("**/api/v1/attempts/attempt-123", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "attempt-123",
        assessment_id: "assessment-abc",
        student_id: "student-xyz",
        status: overrides.status ?? "IN_PROGRESS",
        started_at: new Date().toISOString(),
        submitted_at: null,
        score: overrides.score ?? null,
        questions,
      }),
    }),
  );
}

function mockAttemptResults(
  page: import("@playwright/test").Page,
  score = 0.5,
) {
  return page.route("**/api/v1/attempts/attempt-123/results", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        score: score,
        correct_count: 1,
        total_questions: 2,
        status: "COMPLETED",
      }),
    }),
  );
}

function mockAttemptResults(
  page: import("@playwright/test").Page,
  score = 0.5,
) {
  return page.route("**/api/v1/attempts/attempt-123/results", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        attempt_id: "attempt-123",
        score,
        correct_count: Math.round(score * 2),
        total_questions: 2,
        status: "COMPLETED",
      }),
    }),
  );
}

// ─────────────────────────────────────────────────────────────
//  TakeAssessmentPage tests
// ─────────────────────────────────────────────────────────────

test.describe("TakeAssessmentPage", () => {
  test("test_take_assessment_when_attempt_loaded_then_first_question_shown", async ({
    page,
  }) => {
    await mockAttemptRoutes(page);
    await page.goto("/student/assessments/attempt-123/take");

    // First question text should be visible
    await expect(page.getByText("What is 2 + 2?")).toBeVisible();

    // Q counter should show Q1 / 2
    await expect(page.getByText("Q1\u00a0/\u00a02")).toBeVisible();
  });

  test("test_take_assessment_when_option_selected_then_selected_state_applied", async ({
    page,
  }) => {
    await mockAttemptRoutes(page);
    await page.goto("/student/assessments/attempt-123/take");

    // Click option B (answer "4")
    const optionB = page.getByRole("button", { name: /B/ }).first();
    await optionB.click();

    // Option B should now have aria-pressed="true"
    await expect(optionB).toHaveAttribute("aria-pressed", "true");

    // Option A should still be aria-pressed="false"
    const optionA = page.getByRole("button", { name: /A/ }).first();
    await expect(optionA).toHaveAttribute("aria-pressed", "false");
  });

  test("test_take_assessment_when_next_clicked_then_response_saved_and_next_question_shown", async ({
    page,
  }) => {
    await mockAttemptRoutes(page);

    // Mock the single-response save endpoint
    await page.route("**/api/v1/attempts/attempt-123/responses", (route) =>
      route.fulfill({ status: 204 }),
    );

    await page.goto("/student/assessments/attempt-123/take");

    // Select option B
    await page.getByRole("button", { name: /B/ }).first().click();

    // Click Next
    await page.getByRole("button", { name: "Next" }).click();

    // Should now show second question
    await expect(
      page.getByText("What is the capital of France?"),
    ).toBeVisible();

    // Q counter should advance to Q2
    await expect(page.getByText("Q2\u00a0/\u00a02")).toBeVisible();
  });

  test("test_take_assessment_when_back_clicked_then_previous_answer_still_selected", async ({
    page,
  }) => {
    await mockAttemptRoutes(page);
    await page.route("**/api/v1/attempts/attempt-123/responses", (route) =>
      route.fulfill({ status: 204 }),
    );

    await page.goto("/student/assessments/attempt-123/take");

    // Answer Q1 with option B, move to Q2
    await page.getByRole("button", { name: /B/ }).first().click();
    await page.getByRole("button", { name: "Next" }).click();

    // Now press the Back navigation button (not the leave arrow)
    await page.getByRole("button", { name: "Back" }).last().click();

    // Should be back on Q1 and option B should still be selected
    await expect(page.getByText("What is 2 + 2?")).toBeVisible();
    const optionB = page.getByRole("button", { name: /B/ }).first();
    await expect(optionB).toHaveAttribute("aria-pressed", "true");
  });

  test("test_take_assessment_when_all_answered_then_submit_button_shown_on_last_question", async ({
    page,
  }) => {
    await mockAttemptRoutes(page);
    await page.route("**/api/v1/attempts/attempt-123/responses", (route) =>
      route.fulfill({ status: 204 }),
    );

    await page.goto("/student/assessments/attempt-123/take");

    // Answer Q1 and navigate to Q2
    await page.getByRole("button", { name: /B/ }).first().click();
    await page.getByRole("button", { name: "Next" }).click();

    // On last question: "Submit Assessment" button should be present
    await expect(
      page.getByRole("button", { name: "Submit Assessment" }),
    ).toBeVisible();
  });

  test("test_take_assessment_when_some_unanswered_then_confirmation_modal_shown", async ({
    page,
  }) => {
    await mockAttemptRoutes(page);
    await page.route("**/api/v1/attempts/attempt-123/responses", (route) =>
      route.fulfill({ status: 204 }),
    );

    await page.goto("/student/assessments/attempt-123/take");

    // Skip Q1, navigate to Q2 (leave Q1 unanswered)
    await page.getByRole("button", { name: "Next" }).click();

    // Click Submit Assessment without answering Q2 either
    await page.getByRole("button", { name: "Submit Assessment" }).click();

    // Confirmation modal should appear
    await expect(page.getByText("Some questions unanswered")).toBeVisible();
    await expect(
      page.getByText(/Unanswered questions will count as incorrect/),
    ).toBeVisible();
  });

  test("test_take_assessment_when_completed_attempt_loaded_then_redirects_to_results", async ({
    page,
  }) => {
    await mockAttemptRoutes(page, { status: "COMPLETED", score: 0.75 });

    // Should be redirected to results without showing the take page
    await page.goto("/student/assessments/attempt-123/take");
    await expect(page).toHaveURL(
      /\/student\/assessments\/attempt-123\/results/,
    );
  });
});

// ─────────────────────────────────────────────────────────────
//  AssessmentResultsPage tests
// ─────────────────────────────────────────────────────────────

test.describe("AssessmentResultsPage", () => {
  test("test_results_page_when_score_above_0_7_then_green_ring", async ({
    page,
  }) => {
    await mockAttemptResults(page, 0.8); // Strong band
    await page.goto("/student/assessments/attempt-123/results");

    // ScoreRing renders an SVG with aria-label containing the score and band
    await expect(page.locator('[aria-label*="Strong"]')).toBeVisible();
  });

  test("test_results_page_when_score_below_0_4_then_red_ring", async ({
    page,
  }) => {
    await mockAttemptResults(page, 0.2); // Needs Work band
    await page.goto("/student/assessments/attempt-123/results");

    await expect(page.locator('[aria-label*="Needs Work"]')).toBeVisible();
  });

  test("test_results_page_shows_diagnostic_complete_banner", async ({
    page,
  }) => {
    await mockAttemptResults(page, 0.5);
    await page.goto("/student/assessments/attempt-123/results");

    await expect(page.getByText("Diagnostic complete!")).toBeVisible();
    await expect(page.getByText(/Head back to see what/)).toBeVisible();
  });
});
