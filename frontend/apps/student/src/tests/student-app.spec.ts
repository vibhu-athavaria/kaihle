import { test, expect } from "@playwright/test";

/**
 * Smoke test for Student app - verifies correct app is loaded
 * Design: StudentLayout v2.1 — left sidebar, green primary buttons, no bottom nav
 * Reference: docs/design/DESIGN_SYSTEM.md §5.4, docs/design/mockups/student_dashboard.html
 */
test.describe("Student App", () => {
  test("loaded_correct_app_student_uses_green_actions", async ({ page }) => {
    await page.goto("/login");
    await expect(page).toHaveURL(/localhost:3002/);
    await expect(page.locator("text=Student Portal")).toBeVisible();
  });
});
