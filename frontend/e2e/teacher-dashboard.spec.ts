import { test, expect } from "@playwright/test";
import { config } from "./config";

test.describe("Teacher Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${config.teacherApp}/login`);
    await page.getByLabel(/email/i).fill("teacher@kaihle.com");
    await page.getByLabel(/password/i).fill("TestPassword123!");
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.waitForURL(/\/teacher/);
  });

  test("TEACH-1: Teacher logs in → dashboard loads with class cards", async ({
    page,
  }) => {
    await expect(page).toHaveURL(/\/teacher/);
    await expect(page.getByText(/teacher dashboard/i)).toBeVisible();
  });

  test("TEACH-3: API error → error message displayed", async ({ page }) => {
    await page.goto(`${config.teacherApp}/teacher/dashboard`);

    await page.route("**/api/v1/**", (route) => {
      route.abort("failed");
    });

    await page.reload();
    await expect(page.getByText(/failed to load|error/i)).toBeVisible();
  });

  test("TEACH-4: Loading → skeleton loaders shown", async ({ page }) => {
    await page.goto(`${config.teacherApp}/teacher/dashboard`);

    const skeletonCards = page.locator(".animate-pulse, [class*='skeleton']");
    const count = await skeletonCards.count();
    expect(count).toBeGreaterThan(0);
  });

  test("TEACH-5: Page load → single sidebar", async ({ page }) => {
    await page.goto(`${config.teacherApp}/teacher/dashboard`);

    const sidebars = page.locator("aside");
    await expect(sidebars).toHaveCount(1);
  });

  test("TEACH-6: Page load → gold Assessment button in top nav", async ({
    page,
  }) => {
    await page.goto(`${config.teacherApp}/teacher/dashboard`);

    const assessmentButton = page.getByRole("button", { name: /assessment/i });
    await expect(assessmentButton).toBeVisible();
  });

  test("TEACH-7: Page load → time-based greeting", async ({ page }) => {
    await page.goto(`${config.teacherApp}/teacher/dashboard`);

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
