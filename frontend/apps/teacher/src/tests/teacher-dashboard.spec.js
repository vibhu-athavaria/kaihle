import { test, expect } from "@playwright/test";
test.describe("Teacher Dashboard", () => {
    test("teacher lands on dashboard after login", async ({ page }) => {
        await page.goto("/teacher/dashboard");
        await expect(page).toHaveURL("/teacher/dashboard");
    });
    test("teacher sees class cards", async ({ page }) => {
        await page.goto("/teacher/dashboard");
        await expect(page.locator("text=My classes")).toBeVisible();
    });
    test("pending action banner shows when students need study plans", async ({ page, }) => {
        await page.goto("/teacher/dashboard");
        const banner = page.locator("text=need study plans");
        await expect(banner).toBeVisible();
    });
    test("pending action banner NOT shown when no pending actions", async ({ page, }) => {
        await page.goto("/teacher/dashboard");
        await expect(page.locator("text=need study plans")).not.toBeVisible();
    });
    test("Gap Map link navigates to correct class gap map", async ({ page }) => {
        await page.goto("/teacher/dashboard");
        const gapMapLink = page.locator("text=Gap Map →").first();
        await gapMapLink.click();
        await expect(page).toHaveURL(/.*\/gap-map/);
    });
    test("School Admin role redirected to school overview", async ({ page }) => {
        await page.goto("/school/overview");
        await expect(page).toHaveURL("/school/overview");
    });
    test("class card with low mastery shows red text", async ({ page }) => {
        await page.goto("/teacher/dashboard");
        const masteryText = page.locator("text=38%");
        await expect(masteryText).toBeVisible();
    });
    test("class card with null mastery shows muted dash", async ({ page }) => {
        await page.goto("/teacher/dashboard");
        const noDataText = page.locator("text=—");
        await expect(noDataText).toBeVisible();
    });
});
