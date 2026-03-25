import { test, expect } from "@playwright/test";

/**
 * Smoke test for School Admin app - verifies correct app is loaded
 * Design: DashboardLayout variant="school-admin", green actions, left stripe, Fraunces headings
 */
test.describe("School Admin App", () => {
  test("loaded_correct_app_school_admin", async ({ page }) => {
    await page.goto("/login");
    await expect(page).toHaveURL(/localhost:3004/);
    // Verify the login page has the School Admin Portal label
    await expect(page.locator("text=School Admin Portal")).toBeVisible();
  });
});
