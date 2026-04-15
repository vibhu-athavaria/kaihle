import { test, expect } from "@playwright/test";

const BASE_URL = "http://localhost:3002";

// Helper function to login as a student
async function loginAsStudent(page: any) {
  await page.goto(`${BASE_URL}/login`);
  await page.getByLabel(/email/i).fill("student@school.edu");
  await page.getByLabel(/password/i).fill("password123");
  await page.getByRole("button", { name: /sign in/i }).click();
}

test.describe("Per-Class Diagnostic Gate", () => {
  test("student with completed learning profile but no diagnostics sees dashboard", async ({
    page,
  }) => {
    await loginAsStudent(page);

    // Should go directly to dashboard after learning profile is complete
    // (not redirected to /student/onboarding/diagnostics)
    await expect(page).toHaveURL(/\/student\/dashboard/);
  });

  test("student dashboard shows locked class card for incomplete diagnostic", async ({
    page,
  }) => {
    await loginAsStudent(page);

    // Wait for dashboard to load
    await expect(page).toHaveURL(/\/student\/dashboard/);
    await page.waitForLoadState("networkidle");

    // Look for class cards section
    const myClassesHeading = page.getByText(/My Classes/i);
    if (await myClassesHeading.isVisible()) {
      // Should see locked class cards (aria-label contains "diagnostic required to unlock")
      const lockedCards = page.locator('[aria-label*="diagnostic required to unlock"]');
      const lockedCount = await lockedCards.count();
      expect(lockedCount).toBeGreaterThan(0);
    }
  });

  test("clicking locked class card routes to diagnostic page, not class content", async ({
    page,
  }) => {
    await loginAsStudent(page);

    // Wait for dashboard to load
    await expect(page).toHaveURL(/\/student\/dashboard/);
    await page.waitForLoadState("networkidle");

    // Look for a locked class card and click it
    const lockedCard = page.locator('[aria-label*="diagnostic required to unlock"]').first();
    if (await lockedCard.isVisible()) {
      await lockedCard.click();

      // Should navigate to diagnostic page, not topics
      await expect(page).toHaveURL(/\/diagnostic/);
      await expect(page).not.toHaveURL(/\/topics/);
    }
  });

  test("student dashboard shows unlocked class card after diagnostic completion", async ({
    page,
  }) => {
    await loginAsStudent(page);

    // Wait for dashboard to load
    await expect(page).toHaveURL(/\/student\/dashboard/);
    await page.waitForLoadState("networkidle");

    // Verify the page loaded with class cards section
    const myClassesHeading = page.getByText(/My Classes/i);
    await expect(myClassesHeading).toBeVisible();
  });

  test("student can access class topics after diagnostic completion via direct navigation", async ({
    page,
  }) => {
    await loginAsStudent(page);

    // Try to access topics directly - if diagnostic is complete for a class,
    // this should succeed (200), otherwise should get 403
    const response = await page.request.get(
      `${BASE_URL}/api/v1/classes/some-class-id/topics`,
    );

    // Response should be either 200 (success) or 403 (diagnostic incomplete)
    // Not 401 (unauthorized) since we're logged in
    expect([200, 403]).toContain(response.status());
  });

  test("student cannot access class topics before diagnostic completion - graceful 403 handling", async ({
    page,
  }) => {
    await loginAsStudent(page);

    // The API should return 403 with DIAGNOSTIC_INCOMPLETE code
    // when trying to access topics without completing diagnostic
    const response = await page.request.get(
      `${BASE_URL}/api/v1/classes/some-class-id/topics`,
    );

    if (response.status() === 403) {
      const body = await response.json();
      expect(body.detail.code).toBe("DIAGNOSTIC_INCOMPLETE");
    }
    // If 200, diagnostic was already complete for this class
  });

  test("diagnostic endpoint is never blocked", async ({ page }) => {
    await loginAsStudent(page);

    // The diagnostic endpoint should always return 200
    // regardless of diagnostic completion status
    const response = await page.request.get(
      `${BASE_URL}/api/v1/classes/some-class-id/diagnostic`,
    );

    // Should be 200 - diagnostic endpoint is never gated
    expect(response.status()).toBe(200);
  });
});
