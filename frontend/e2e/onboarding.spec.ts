import { test, expect } from "@playwright/test";

// Helper function to login
async function loginAsStudent(page: any) {
  await page.goto("http://localhost:3002/login");
  await page.getByLabel(/email/i).fill("student@school.edu");
  await page.getByLabel(/password/i).fill("password123");
  await page.getByRole("button", { name: /sign in/i }).click();
}

test.describe("Student Onboarding", () => {
  test("first_login_redirects_to_onboarding_profile", async ({ page }) => {
    await loginAsStudent(page);

    await expect(page).toHaveURL(/\/student\/onboarding\/profile/);
    // Wait for questionnaire to load
    await expect(page.getByText(/Learning profile/i)).toBeVisible();
  });

  test("questionnaire_submit_navigates_to_dashboard", async ({ page }) => {
    await loginAsStudent(page);

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

    // After questionnaire, should go to dashboard
    await expect(page).toHaveURL(/\/student\/dashboard/);
  });

  test("back_navigation_preserves_answers", async ({ page }) => {
    await loginAsStudent(page);

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
    await loginAsStudent(page);

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

  test("completed_student_not_redirected_to_onboarding", async ({ page }) => {
    // Login as a student who has already completed onboarding
    await loginAsStudent(page);

    // Should go directly to dashboard, not onboarding
    await expect(page).toHaveURL(/\/student\/dashboard/);
  });
});
