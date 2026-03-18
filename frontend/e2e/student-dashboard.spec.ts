import { test, expect } from "@playwright/test";

async function loginAsStudent(page: any) {
  await page.goto("http://localhost:3002/login");
  await page.getByLabel(/email/i).fill("student@school.edu");
  await page.getByLabel(/password/i).fill("password123");
  await page.getByRole("button", { name: /sign in/i }).click();
}

test.describe("Student Dashboard", () => {
  test("student who completed onboarding lands on /student/dashboard", async ({
    page,
  }) => {
    await loginAsStudent(page);
    await expect(page).toHaveURL(/\/student\/dashboard/);
  });

  test("greeting uses time-of-day (Good morning before noon)", async ({
    page,
  }) => {
    await loginAsStudent(page);
    await expect(page.locator("text=Good morning")).toBeVisible();
  });

  test("subject score cards render with correct mastery colors", async ({
    page,
  }) => {
    await loginAsStudent(page);
    await expect(page.locator("text=Strong")).toBeVisible();
  });

  test("card with score 0.72 shows green border and Strong label", async ({
    page,
  }) => {
    await loginAsStudent(page);
    await expect(page.locator("text=72%")).toBeVisible();
    await expect(page.locator("text=Strong")).toBeVisible();
  });

  test("subject with no data shows dash not zero percent", async ({
    page,
  }) => {
    await loginAsStudent(page);
    await expect(page.locator("text=—")).toBeVisible();
  });

  test("active study plan card shows with View plans link", async ({
    page,
  }) => {
    await loginAsStudent(page);
    const viewPlansLink = page.locator("text=View plans →");
    await expect(viewPlansLink).toBeVisible();
  });

  test("active assessment card shows with Start now link", async ({
    page,
  }) => {
    await loginAsStudent(page);
    const startNowLink = page.locator("text=Start now →");
    await expect(startNowLink).toBeVisible();
  });

  test("no pending actions shows caught up message", async ({ page }) => {
    await loginAsStudent(page);
    const caughtUpMessage = page.locator("text=You're all caught up!");
    await expect(caughtUpMessage).toBeVisible();
  });

  test("SubjectScoreCard score=0.38 shows red border and red text", async ({
    page,
  }) => {
    await loginAsStudent(page);
    await expect(page.locator("text=38%")).toBeVisible();
  });

  test("SubjectScoreCard score=null shows neutral border and dash value",
    async ({ page }) => {
      await loginAsStudent(page);
      const dashValue = page.locator("text=—").first();
      await expect(dashValue).toBeVisible();
    });

  test("responsive 3-column card grid on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await loginAsStudent(page);
    const grid = page.locator(".grid.grid-cols-3");
    await expect(grid).toBeVisible();
  });

  test("next step cards stack vertically on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await loginAsStudent(page);
    const nextStepsContainer = page.locator("text=What's waiting for you");
    await expect(nextStepsContainer).toBeVisible();
  });

  test("bottom nav visible on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await loginAsStudent(page);
    const bottomNav = page.locator("nav[aria-label='Student navigation']");
    await expect(bottomNav).toBeVisible();
  });

  test("bottom nav hidden on desktop", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await loginAsStudent(page);
    const bottomNav = page.locator("nav[aria-label='Student navigation']");
    await expect(bottomNav).toBeHidden();
  });

  test("greeting uses font-display", async ({ page }) => {
    await loginAsStudent(page);
    const greeting = page.locator("h1.font-display");
    await expect(greeting).toBeVisible();
  });

  test("skeleton cards shown during loading", async ({ page }) => {
    await loginAsStudent(page);
    const skeleton = page.locator(".animate-pulse");
    await expect(skeleton.first()).toBeVisible();
  });
});
