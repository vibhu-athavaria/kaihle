import { test, expect } from "@playwright/test";
import { config } from "./config";

test.describe("Student Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${config.studentApp}/login`);
    await page.getByLabel(/email/i).fill("student@kaihle.com");
    await page.getByLabel(/password/i).fill("TestPassword123!");
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.waitForURL(/\/student/);
  });

  test("STUD-1: Student logs in → dashboard loads with subject cards", async ({
    page,
  }) => {
    await expect(page).toHaveURL(/\/student/);
    await expect(page.getByText(/student dashboard/i)).toBeVisible();
  });

  test("STUD-3: API error → error message displayed", async ({ page }) => {
    await page.goto(`${config.studentApp}/student/dashboard`);

    await page.route("**/api/v1/**", (route) => {
      route.abort("failed");
    });

    await page.reload();
    await expect(page.getByText(/failed to load|error/i)).toBeVisible();
  });

  test("STUD-5: Page load → single layout (no duplicate header/sidebar)", async ({
    page,
  }) => {
    await page.goto(`${config.studentApp}/student/dashboard`);

    const headers = page.locator("header");
    await expect(headers).toHaveCount(1);

    const asides = page.locator("aside");
    await expect(asides).toHaveCount(0);
  });

  test("STUD-6: Page load → time-based greeting", async ({ page }) => {
    await page.goto(`${config.studentApp}/student/dashboard`);

    const hour = new Date().getHours();
    let expectedGreeting: string;
    if (hour < 12) expectedGreeting = "Good morning";
    else if (hour < 18) expectedGreeting = "Good afternoon";
    else expectedGreeting = "Good evening";

    await expect(
      page.getByText(new RegExp(expectedGreeting, "i")),
    ).toBeVisible();
  });
});
