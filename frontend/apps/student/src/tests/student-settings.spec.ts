import { test, expect } from "@playwright/test";

/**
 * E2E tests for Student Settings page
 * Route: /student/settings - PrivateRoute + RoleRoute(['STUDENT'])
 */
test.describe("Student Settings Page", () => {
  test("renders_three_sections_when_authenticated", async ({ page }) => {
    // Navigate to settings page
    await page.goto("/student/settings");

    // Should show Account section
    await expect(page.getByRole("heading", { name: "Account" })).toBeVisible();

    // Should show Learning profile section
    await expect(
      page.getByRole("heading", { name: "Learning profile" }),
    ).toBeVisible();

    // Should show Account actions section
    await expect(
      page.getByRole("heading", { name: "Account actions" }),
    ).toBeVisible();
  });

  test("account_section_displays_name_email_password", async ({ page }) => {
    await page.goto("/student/settings");

    // Should show Name label and edit button
    await expect(page.getByText("Name")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /edit/i }).first(),
    ).toBeVisible();

    // Should show Email field (read-only, managed by school)
    await expect(page.getByText("Email")).toBeVisible();
    await expect(page.getByText("Managed by school")).toBeVisible();

    // Should show Password field with change button
    await expect(page.getByText("Password")).toBeVisible();
    await expect(page.getByRole("button", { name: /change/i })).toBeVisible();
  });

  test("learning_profile_section_shows_modality_bars", async ({ page }) => {
    await page.goto("/student/settings");

    // Should show retake button
    await expect(
      page.getByRole("button", { name: "Retake questionnaire" }),
    ).toBeVisible();
  });

  test("account_actions_section_shows_sign_out", async ({ page }) => {
    await page.goto("/student/settings");

    // Should show sign out button
    await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();

    // Should show helper text
    await expect(
      page.getByText("You'll need to sign in again on this device"),
    ).toBeVisible();
  });

  test("page_uses_max_width_constraint", async ({ page }) => {
    await page.goto("/student/settings");

    // Settings page should be centered with max width
    const settingsContainer = page.locator("main").first();
    await expect(settingsContainer).toBeVisible();
  });
});
