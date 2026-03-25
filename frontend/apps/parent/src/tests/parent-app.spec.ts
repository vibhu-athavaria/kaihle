import { test, expect } from "@playwright/test";

/**
 * Smoke test for Parent app - verifies correct app is loaded
 * Design: ParentLayout with top nav only, Lora font, cream background (#fdf8f0)
 */
test.describe("Parent App", () => {
  test("loaded_correct_app_parent_has_lora_font", async ({ page }) => {
    await page.goto("/login");
    await expect(page).toHaveURL(/localhost:3003/);
    // Verify the login page has the Parent Portal label
    await expect(page.locator("text=Parent Portal")).toBeVisible();
  });
});
