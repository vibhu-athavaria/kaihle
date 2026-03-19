import { test, expect } from "@playwright/test";
import { config } from "./config";

test.describe("Cross-App Role Restrictions", () => {
  test("CROSS-1: Teacher accesses /student/* → redirected to unauthorized", async ({
    page,
  }) => {
    await page.goto(`${config.teacherApp}/login`);
    await page.getByLabel(/email/i).fill("teacher@kaihle.com");
    await page.getByLabel(/password/i).fill("TestPassword123!");
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.waitForURL(/\/teacher/);

    await page.goto(`${config.studentApp}/student/dashboard`);

    await expect(page).toHaveURL(/unauthorised|unauthorized/);
  });

  test("CROSS-2: Student accesses /teacher/* → redirected to unauthorized", async ({
    page,
  }) => {
    await page.goto(`${config.studentApp}/login`);
    await page.getByLabel(/email/i).fill("student@kaihle.com");
    await page.getByLabel(/password/i).fill("TestPassword123!");
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.waitForURL(/\/student/);

    await page.goto(`${config.teacherApp}/teacher/dashboard`);

    await expect(page).toHaveURL(/unauthorised|unauthorized/);
  });

  test("CROSS-5: Login, close browser, reopen → session persists", async ({
    page,
    browser,
  }) => {
    await page.goto(`${config.teacherApp}/login`);
    await page.getByLabel(/email/i).fill("teacher@kaihle.com");
    await page.getByLabel(/password/i).fill("TestPassword123!");
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.waitForURL(/\/teacher/);

    expect(page.url()).toContain("/teacher");

    const storageState = await page.context().storageState();

    const newContext = await browser.newContext({
      storageState,
    });
    const newPage = await newContext.newPage();
    await newPage.goto(`${config.teacherApp}/teacher/dashboard`);
    await expect(newPage).toHaveURL(/\/teacher\/dashboard/);
    await newPage.close();
    await newContext.close();
  });
});
