import { test, expect } from "@playwright/test";

test.describe("Login Flow", () => {
  test.describe("Teacher App", () => {
    test("teacher logs in with email/password → lands on /teacher/dashboard", async ({
      page,
    }) => {
      await page.goto("http://localhost:3001/login");

      // Fill in login form
      await page.getByLabel(/email/i).fill("teacher@school.edu");
      await page.getByLabel(/password/i).fill("password123");
      await page.getByRole("button", { name: /sign in/i }).click();

      // Should redirect to teacher dashboard
      await expect(page).toHaveURL(/\/teacher\/dashboard/);
      await expect(page.getByText(/teacher dashboard/i)).toBeVisible();
    });

    test("invalid credentials shows inline error message", async ({ page }) => {
      await page.goto("http://localhost:3001/login");

      // Fill in wrong credentials
      await page.getByLabel(/email/i).fill("wrong@school.edu");
      await page.getByLabel(/password/i).fill("wrongpassword");
      await page.getByRole("button", { name: /sign in/i }).click();

      // Should show error message
      await expect(page.getByText(/invalid email or password/i)).toBeVisible();
    });

    test("magic link form submits → shows Check your inbox confirmation", async ({
      page,
    }) => {
      await page.goto("http://localhost:3001/login");

      // Switch to magic link mode
      await page.getByRole("button", { name: /magic link/i }).click();

      // Fill in email
      await page.getByLabel(/email/i).fill("teacher@school.edu");
      await page.getByRole("button", { name: /send login link/i }).click();

      // Should show confirmation
      await expect(page.getByText(/check your inbox/i)).toBeVisible();
      await expect(
        page.getByText(/we sent a login link to your email/i),
      ).toBeVisible();
    });

    test("form shows validation error when email field is empty on submit", async ({
      page,
    }) => {
      await page.goto("http://localhost:3001/login");

      // Click sign in without filling email
      await page.getByRole("button", { name: /sign in/i }).click();

      // Should show validation error
      await expect(
        page.getByText(/enter a valid email address/i),
      ).toBeVisible();
    });
  });

  test.describe("Student App", () => {
    test("student logs in → redirected to /student/onboarding", async ({
      page,
    }) => {
      await page.goto("http://localhost:3002/login");

      // Fill in login form
      await page.getByLabel(/email/i).fill("student@school.edu");
      await page.getByLabel(/password/i).fill("password123");
      await page.getByRole("button", { name: /sign in/i }).click();

      // Should redirect to onboarding (because onboarding is not complete)
      await expect(page).toHaveURL(/\/student\/onboarding/);
      await expect(page.getByText(/student onboarding/i)).toBeVisible();
    });
  });

  test.describe("Parent App", () => {
    test("parent logs in → lands on /parent/dashboard", async ({ page }) => {
      await page.goto("http://localhost:3003/login");

      // Fill in login form
      await page.getByLabel(/email/i).fill("parent@example.com");
      await page.getByLabel(/password/i).fill("password123");
      await page.getByRole("button", { name: /sign in/i }).click();

      // Should redirect to parent dashboard
      await expect(page).toHaveURL(/\/parent\/dashboard/);
      await expect(page.getByText(/parent dashboard/i)).toBeVisible();
    });
  });

  test.describe("Accessibility", () => {
    test("all inputs have visible labels", async ({ page }) => {
      await page.goto("http://localhost:3001/login");

      const emailLabel = page.locator('label[for="email"]');
      const passwordLabel = page.locator('label[for="password"]');

      await expect(emailLabel).toBeVisible();
      await expect(passwordLabel).toBeVisible();
    });

    test("form is keyboard-navigable", async ({ page }) => {
      await page.goto("http://localhost:3001/login");

      // Press Tab to navigate to email field
      await page.keyboard.press("Tab");
      await expect(page.getByLabel(/email/i)).toBeFocused();

      // Press Tab to navigate to password field
      await page.keyboard.press("Tab");
      await expect(page.getByLabel(/password/i)).toBeFocused();

      // Press Tab to navigate to sign in button
      await page.keyboard.press("Tab");
      await expect(
        page.getByRole("button", { name: /sign in/i }),
      ).toBeFocused();
    });
  });

  test.describe("Responsive", () => {
    test("correct layout at 375px (mobile) viewport", async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto("http://localhost:3001/login");

      // Form should be visible and usable
      await expect(page.getByLabel(/email/i)).toBeVisible();
      await expect(page.getByLabel(/password/i)).toBeVisible();
      await expect(
        page.getByRole("button", { name: /sign in/i }),
      ).toBeVisible();

      // Card should fit within viewport width
      const card = page.locator(".bg-white.rounded-2xl");
      const box = await card.boundingBox();
      expect(box?.width).toBeLessThanOrEqual(375);
    });

    test("correct layout at 768px (tablet) viewport", async ({ page }) => {
      await page.setViewportSize({ width: 768, height: 1024 });
      await page.goto("http://localhost:3001/login");

      await expect(page.getByLabel(/email/i)).toBeVisible();
      await expect(page.getByLabel(/password/i)).toBeVisible();
    });

    test("correct layout at 1280px (desktop) viewport", async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 720 });
      await page.goto("http://localhost:3001/login");

      await expect(page.getByLabel(/email/i)).toBeVisible();
      await expect(page.getByLabel(/password/i)).toBeVisible();
    });
  });
});
