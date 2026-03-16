import { test, expect } from "@playwright/test";

test.describe("Student Onboarding", () => {
  test("first_login_redirects_to_onboarding_profile", async ({ page }) => {
    await page.goto("http://localhost:3002/login");

    await page.getByLabel(/email/i).fill("student@school.edu");
    await page.getByLabel(/password/i).fill("password123");
    await page.getByRole("button", { name: /sign in/i }).click();

    await expect(page).toHaveURL(/\/student\/onboarding\/profile/);
    await expect(
      page.getByText(/How do you prefer to learn new concepts/i),
    ).toBeVisible();
  });

  test("questionnaire_submit_navigates_to_diagnostic_hub", async ({ page }) => {
    await page.goto("http://localhost:3002/login");

    await page.getByLabel(/email/i).fill("student@school.edu");
    await page.getByLabel(/password/i).fill("password123");
    await page.getByRole("button", { name: /sign in/i }).click();

    await expect(page).toHaveURL(/\/student\/onboarding\/profile/);

    await page.getByRole("button", { name: /video tutorials/i }).click();
    await page.getByRole("button", { name: /next/i }).click();

    await page
      .getByRole("button", { name: /i like to go at my own speed/i })
      .click();
    await page.getByRole("button", { name: /next/i }).click();

    await page.getByRole("button", { name: /immediate feedback/i }).click();
    await page.getByRole("button", { name: /next/i }).click();

    await page.getByRole("button", { name: /quiet space alone/i }).click();
    await page.getByRole("button", { name: /next/i }).click();

    await page.getByRole("button", { name: /master subjects deeply/i }).click();
    await page.getByRole("button", { name: /next/i }).click();

    await page.getByRole("button", { name: /submit/i }).click();

    await expect(page).toHaveURL(/\/student\/onboarding\/diagnostics/);
  });

  test("back_navigation_preserves_answers", async ({ page }) => {
    await page.goto("http://localhost:3002/onboarding/profile");

    await page.getByRole("button", { name: /video tutorials/i }).click();
    await page.getByRole("button", { name: /next/i }).click();

    await page
      .getByRole("button", { name: /i like to go at my own speed/i })
      .click();
    await page.getByRole("button", { name: /next/i }).click();

    await page.getByRole("button", { name: /back/i }).click();

    await expect(
      page.getByRole("button", { name: /i like to go at my own speed/i }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  test("interest_tile_multi_select_toggles", async ({ page }) => {
    await page.goto("http://localhost:3002/onboarding/profile");

    for (let i = 0; i < 5; i++) {
      await page.getByRole("button", { name: /next/i }).click();
    }

    const sportsButton = page.getByRole("button", { name: /sports selected/i });

    await page.getByRole("button", { name: /sports/i }).click();
    await expect(sportsButton).toBeVisible();

    await page.getByRole("button", { name: /sports/i }).click();
    await expect(
      page.getByRole("button", { name: /sports not selected/i }),
    ).toBeVisible();
  });

  test("diagnostic_hub_shows_not_started_badges", async ({ page }) => {
    await page.goto("http://localhost:3002/onboarding/diagnostics");

    await expect(
      page.getByText(/complete your subject diagnostics/i),
    ).toBeVisible();
  });

  test("completing_all_diagnostics_redirects_to_dashboard", async () => {
    test.skip(true, "Requires mock backend to complete assessments");
  });

  test("completed_student_not_redirected_to_onboarding", async () => {
    test.skip(true, "Requires mock backend for completed student");
  });
});

test.describe("Onboarding Responsive", () => {
  test("questionnaire_renders_correctly_at_375px", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto("http://localhost:3002/onboarding/profile");

    await expect(
      page.getByText(/How do you prefer to learn new concepts/i),
    ).toBeVisible();

    const cards = page.locator("button.rounded-2xl");
    await expect(cards.first()).toBeVisible();
  });
});
