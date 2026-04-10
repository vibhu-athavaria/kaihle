import { test, expect, type Page } from "@playwright/test";

/**
 * E2E tests for the Assessment Creation Wizard and Assessment List page.
 *
 * These tests are written but not run as part of CI — they require a running
 * backend and test data seed.
 *
 * Test naming convention: test_<what>_when_<condition>_then_<expected>
 */

const BASE_URL = "http://localhost:3001";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function loginAsTeacher(page: Page) {
  await page.goto(`${BASE_URL}/login`);
  await page.getByLabel(/email/i).fill("teacher@test.kaihle.com");
  await page.getByLabel(/password/i).fill("testPassword123");
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL(/\/teacher\/dashboard/);
}

async function navigateToNewAssessment(page: Page) {
  await page.goto(`${BASE_URL}/teacher/assessments/new`);
  await page.waitForLoadState("networkidle");
}

// ---------------------------------------------------------------------------
// Step 1 — Class and Assessment Type
// ---------------------------------------------------------------------------

test.describe("Assessment Wizard — Step 1", () => {
  test("test_wizard_step1_when_class_selected_and_type_chosen_then_next_enabled", async ({
    page,
  }) => {
    await loginAsTeacher(page);
    await navigateToNewAssessment(page);

    // Initially Next button is disabled
    const nextBtn = page.getByRole("button", { name: /next/i });
    await expect(nextBtn).toBeDisabled();

    // Select a class
    await page.getByLabel(/select class/i).selectOption({ index: 1 });

    // Next still disabled — type not chosen
    await expect(nextBtn).toBeDisabled();

    // Choose TOPIC_SPECIFIC type card
    await page.getByRole("button", { name: /topic specific/i }).click();

    // Now Next should be enabled
    await expect(nextBtn).toBeEnabled();
  });

  test("test_wizard_step1_when_diagnostic_selected_then_step2_skipped", async ({
    page,
  }) => {
    await loginAsTeacher(page);
    await navigateToNewAssessment(page);

    // Select class and diagnostic type
    await page.getByLabel(/select class/i).selectOption({ index: 1 });
    await page.getByRole("button", { name: /diagnostic/i }).click();

    // Verify hint text about no topics required
    await expect(
      page.getByText(/topic selection is not required/i),
    ).toBeVisible();

    // Click Next
    await page.getByRole("button", { name: /next/i }).click();

    // Should land on Step 3 (Configure) — not Step 2 (Topics)
    await expect(
      page.getByRole("heading", { name: /configure assessment/i }),
    ).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Step 2 — Topics
// ---------------------------------------------------------------------------

test.describe("Assessment Wizard — Step 2", () => {
  async function goToStep2(page: Page) {
    await loginAsTeacher(page);
    await navigateToNewAssessment(page);
    await page.getByLabel(/select class/i).selectOption({ index: 1 });
    await page.getByRole("button", { name: /topic specific/i }).click();
    await page.getByRole("button", { name: /next/i }).click();
    await expect(
      page.getByRole("heading", { name: /select topics/i }),
    ).toBeVisible();
  }

  test("test_wizard_step2_when_no_topics_selected_then_next_disabled", async ({
    page,
  }) => {
    await goToStep2(page);

    // Ensure no topics are checked by default
    const checkboxes = page.getByRole("checkbox");
    const count = await checkboxes.count();
    if (count > 0) {
      // Uncheck all if any are pre-checked
      for (let i = 0; i < count; i++) {
        const cb = checkboxes.nth(i);
        if (await cb.isChecked()) {
          await cb.uncheck();
        }
      }
    }

    const nextBtn = page.getByRole("button", { name: /next/i });
    await expect(nextBtn).toBeDisabled();
  });
});

// ---------------------------------------------------------------------------
// Step 4 — Preview
// ---------------------------------------------------------------------------

test.describe("Assessment Wizard — Step 4", () => {
  async function goToStep4WithMockedAPI(page: Page) {
    // Mock the assessment creation endpoint
    await page.route("**/api/v1/classes/*/assessments", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            id: "draft-assessment-123",
            title: "Test Assessment",
            status: "DRAFT",
            questions: [
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
                  { key: "A", text: "London" },
                  { key: "B", text: "Berlin" },
                  { key: "C", text: "Paris" },
                  { key: "D", text: "Madrid" },
                ],
              },
            ],
          }),
        });
      } else {
        await route.continue();
      }
    });

    await loginAsTeacher(page);
    await navigateToNewAssessment(page);
    await page.getByLabel(/select class/i).selectOption({ index: 1 });
    await page.getByRole("button", { name: /diagnostic/i }).click();
    await page.getByRole("button", { name: /next/i }).click(); // -> Step 3
    await page.getByRole("button", { name: /preview questions/i }).click(); // -> Step 4
  }

  test("test_wizard_step4_when_api_returns_questions_then_question_list_rendered", async ({
    page,
  }) => {
    await goToStep4WithMockedAPI(page);

    // Wait for questions to load
    await expect(page.getByText("What is 2 + 2?")).toBeVisible();
    await expect(
      page.getByText("What is the capital of France?"),
    ).toBeVisible();

    // MCQ badges should be visible
    const mcqBadges = page.getByText("MCQ");
    await expect(mcqBadges.first()).toBeVisible();
  });

  test("test_wizard_step4_when_insufficient_questions_then_error_message_shown", async ({
    page,
  }) => {
    // Mock insufficient questions (422)
    await page.route("**/api/v1/classes/*/assessments", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 422,
          contentType: "application/json",
          body: JSON.stringify({
            detail: "Insufficient questions in the question bank.",
          }),
        });
      } else {
        await route.continue();
      }
    });

    await loginAsTeacher(page);
    await navigateToNewAssessment(page);
    await page.getByLabel(/select class/i).selectOption({ index: 1 });
    await page.getByRole("button", { name: /diagnostic/i }).click();
    await page.getByRole("button", { name: /next/i }).click(); // -> Step 3
    await page.getByRole("button", { name: /preview questions/i }).click(); // -> Step 4

    // Error message should appear
    await expect(
      page.getByText(
        /not enough questions in the bank for this configuration/i,
      ),
    ).toBeVisible();

    // Back to Configuration button should be visible
    await expect(
      page.getByRole("button", { name: /back to configuration/i }),
    ).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Step 5 — Review and Publish
// ---------------------------------------------------------------------------

test.describe("Assessment Wizard — Step 5", () => {
  async function goToStep5WithMockedAPI(page: Page) {
    await page.route("**/api/v1/classes/*/assessments", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            id: "draft-assessment-456",
            title: "Mocked Assessment",
            status: "DRAFT",
            questions: [
              {
                question_id: "q1",
                question_text: "Sample question?",
                options: [
                  { key: "A", text: "Option A" },
                  { key: "B", text: "Option B" },
                ],
              },
            ],
          }),
        });
      } else {
        await route.continue();
      }
    });

    await loginAsTeacher(page);
    await navigateToNewAssessment(page);
    await page.getByLabel(/select class/i).selectOption({ index: 1 });
    await page.getByRole("button", { name: /diagnostic/i }).click();
    await page.getByRole("button", { name: /next/i }).click(); // -> Step 3
    await page.getByRole("button", { name: /preview questions/i }).click(); // -> Step 4
    await expect(page.getByText("Sample question?")).toBeVisible();
    await page.getByRole("button", { name: /review & publish/i }).click(); // -> Step 5
  }

  test("test_wizard_step5_publish_when_success_then_navigates_to_list", async ({
    page,
  }) => {
    await goToStep5WithMockedAPI(page);

    // Mock publish endpoint
    await page.route(
      "**/api/v1/assessments/draft-assessment-456/publish",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "draft-assessment-456",
            status: "ACTIVE",
          }),
        });
      },
    );

    // Mock assessments list
    await page.route("**/api/v1/classes/*/assessments", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        });
      } else {
        await route.continue();
      }
    });

    await page.getByRole("button", { name: /publish now/i }).click();

    // Should navigate to assessments list
    await page.waitForURL(/\/teacher\/classes\/.*\/assessments/);

    // Success toast
    await expect(
      page.getByText(/assessment published and visible to students/i),
    ).toBeVisible();
  });

  test("test_wizard_step5_publish_when_api_error_then_stays_on_step5", async ({
    page,
  }) => {
    await goToStep5WithMockedAPI(page);

    // Mock publish endpoint with error
    await page.route(
      "**/api/v1/assessments/draft-assessment-456/publish",
      async (route) => {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Internal server error." }),
        });
      },
    );

    await page.getByRole("button", { name: /publish now/i }).click();

    // Should stay on step 5 and show error
    await expect(
      page.getByRole("heading", { name: /review & publish/i }),
    ).toBeVisible();
    await expect(page.getByText(/internal server error/i)).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Assessment List Page
// ---------------------------------------------------------------------------

test.describe("Assessment List Page", () => {
  test("test_assessment_list_when_empty_then_shows_empty_state", async ({
    page,
  }) => {
    await page.route(
      "**/api/v1/classes/test-class-id/assessments",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        });
      },
    );

    await loginAsTeacher(page);
    await page.goto(`${BASE_URL}/teacher/classes/test-class-id/assessments`);

    await expect(page.getByText(/no assessments yet/i)).toBeVisible();
    await expect(
      page.getByText(/create your first assessment to see student progress/i),
    ).toBeVisible();
  });

  test("test_assessment_list_when_draft_assessment_then_no_view_results_action", async ({
    page,
  }) => {
    await page.route(
      "**/api/v1/classes/test-class-id/assessments",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: "assess-draft",
              title: "Draft Assessment",
              assessment_type: "PROGRESS_CHECK",
              status: "DRAFT",
              question_count: 10,
              deadline: null,
              created_at: new Date().toISOString(),
            },
          ]),
        });
      },
    );

    await loginAsTeacher(page);
    await page.goto(`${BASE_URL}/teacher/classes/test-class-id/assessments`);

    // "View Results" should NOT appear for a DRAFT assessment
    await expect(page.getByText(/view results/i)).not.toBeVisible();

    // "Delete" action should be present for DRAFT
    await expect(page.getByRole("button", { name: /delete/i })).toBeVisible();
  });

  test("test_assessment_list_when_active_assessment_then_close_action_present", async ({
    page,
  }) => {
    await page.route(
      "**/api/v1/classes/test-class-id/assessments",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: "assess-active",
              title: "Active Assessment",
              assessment_type: "DIAGNOSTIC",
              status: "ACTIVE",
              question_count: 15,
              deadline: "2026-05-01",
              created_at: new Date().toISOString(),
            },
          ]),
        });
      },
    );

    await loginAsTeacher(page);
    await page.goto(`${BASE_URL}/teacher/classes/test-class-id/assessments`);

    // "View Results" should appear for ACTIVE
    await expect(page.getByText(/view results/i)).toBeVisible();

    // "Close" action should appear for ACTIVE
    await expect(page.getByRole("button", { name: /close/i })).toBeVisible();

    // "Delete" should NOT appear for ACTIVE
    await expect(
      page.getByRole("button", { name: /delete/i }),
    ).not.toBeVisible();
  });
});
