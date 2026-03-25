import { test, expect } from "@playwright/test";

/**
 * Smoke test for Kaihle Admin app - verifies correct app is loaded
 * Design: AdminLayout, Inter font only (no Fraunces/Lora), gray borders
 */
test.describe("Kaihle Admin App", () => {
  test("loaded_correct_app_kaihle_admin", async ({ page }) => {
    await page.goto("/login");
    await expect(page).toHaveURL(/localhost:3005/);
    // Verify the login page has the Kaihle Admin label
    await expect(page.locator("text=Kaihle Admin")).toBeVisible();
  });
});
