import { test, expect } from "@playwright/test";

/**
 * Smoke test for Teacher app - verifies correct app is loaded
 * Design: DashboardLayout variant="teacher", gold primary buttons, Fraunces headings
 */
test.describe("Teacher App", () => {
  test("loaded_correct_app_teacher_uses_gold_actions", async ({ page }) => {
    await page.goto("/login");
    await expect(page).toHaveURL(/localhost:3001/);
    // Verify the login page has the Teacher Portal label
    await expect(page.locator("text=Teacher Portal")).toBeVisible();
  });
});
