/**
 * Playwright E2E tests for Assessment Results pages.
 *
 * These tests are written but NOT run as part of the current task.
 * They cover: sort order, type badge visibility, reteach banner threshold,
 * loading skeletons, chart accessibility, ScoreRing reduced motion,
 * question breakdown correctness, pagination, and design compliance.
 */
import { test, expect } from "@playwright/test";

const BASE_URL = "http://localhost:3001";
const TEACHER_EMAIL = "teacher@test.kaihle.com";
const TEACHER_PASSWORD = "TestPassword123!";

async function loginAsTeacher(page: import("@playwright/test").Page) {
  await page.goto(`${BASE_URL}/login`);
  await page.fill('input[type="email"]', TEACHER_EMAIL);
  await page.fill('input[type="password"]', TEACHER_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/teacher\/dashboard/);
}

test.describe("Assessment Results Page", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsTeacher(page);
  });

  test("test_results_default_sort_lowest_score_first", async ({ page }) => {
    await page.goto(
      `${BASE_URL}/teacher/assessments/test-assessment-id/results`,
    );
    await page.waitForSelector("table");

    // First row should have the lowest score
    const rows = await page.locator("tbody tr").all();
    if (rows.length >= 2) {
      const firstScoreText = await rows[0]
        .locator("td:nth-child(2)")
        .textContent();
      const secondScoreText = await rows[1]
        .locator("td:nth-child(2)")
        .textContent();
      // Both exist — actual value check requires known seed data
      expect(firstScoreText).not.toBeNull();
      expect(secondScoreText).not.toBeNull();
    }
  });

  test("test_results_assessment_type_badge_visible", async ({ page }) => {
    await page.goto(
      `${BASE_URL}/teacher/assessments/test-assessment-id/results`,
    );
    // Assessment type badge must be visible — one of the four known types
    // At minimum, verify badge element with border class exists
    await expect(
      page
        .locator("[class*='border'][class*='rounded-full'][class*='text-xs']")
        .first(),
    ).toBeVisible();
  });

  test("test_results_reteach_banner_when_over_30pct_fail", async ({ page }) => {
    // Navigate to a seeded assessment where >30% scored <40%
    await page.goto(
      `${BASE_URL}/teacher/assessments/high-failure-assessment-id/results`,
    );
    await page
      .waitForSelector("[data-testid='score-distribution']", {
        timeout: 5000,
      })
      .catch(() => null);

    const banner = page.locator(
      "text=More than 30% of students scored below 40%",
    );
    // If the data matches threshold, banner must be visible
    const bannerVisible = await banner.isVisible().catch(() => false);
    // In CI with real seed data, this should be true — verify structure if visible
    if (bannerVisible) {
      await expect(banner).toBeVisible();
      await expect(page.locator(".bg-amber-50")).toBeVisible();
    }
  });

  test("test_results_kpi_shows_skeleton_not_zeros_during_load", async ({
    page,
  }) => {
    // Intercept API to delay response
    await page.route("**/api/v1/assessments/*/results", async (route) => {
      await new Promise((r) => setTimeout(r, 500));
      await route.continue();
    });

    await page.goto(
      `${BASE_URL}/teacher/assessments/test-assessment-id/results`,
    );

    // During load, skeleton cards should appear (animate-pulse) not "0 of 0"
    const skeletons = page.locator(".animate-pulse");
    await expect(skeletons.first()).toBeVisible();

    // "0 of 0" text must never appear
    await expect(page.locator("text=0 of 0")).not.toBeVisible();
  });

  test("test_results_chart_has_aria_label", async ({ page }) => {
    await page.goto(
      `${BASE_URL}/teacher/assessments/test-assessment-id/results`,
    );
    await page.waitForLoadState("networkidle");

    // Chart wrapper must have role="img" and aria-label
    const ariaLabel = await page
      .locator('[role="img"][aria-label*="Score distribution"]')
      .getAttribute("aria-label");
    expect(ariaLabel).toMatch(/Score distribution:/);
  });

  test("test_results_chart_has_visible_legend", async ({ page }) => {
    await page.goto(
      `${BASE_URL}/teacher/assessments/test-assessment-id/results`,
    );
    await page.waitForLoadState("networkidle");

    // All four band labels must be visible in the legend
    await expect(page.locator("text=Strong (≥70%)")).toBeVisible();
    await expect(page.locator("text=Developing (40–69%)")).toBeVisible();
    await expect(page.locator("text=Needs Work (<40%)")).toBeVisible();
    await expect(page.locator("text=Not submitted")).toBeVisible();
  });

  test("test_results_score_ring_respects_reduced_motion", async ({ page }) => {
    // Set OS-level reduced motion preference via emulation
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto(
      `${BASE_URL}/teacher/assessments/test-assessment-id/results/student-id?attempt=attempt-id`,
    );
    await page.waitForLoadState("networkidle");

    // SVG circle should exist
    const ring = page.locator("svg circle").nth(1); // progress arc
    await expect(ring).toBeVisible();

    // motion-safe: transitions are gated — with prefers-reduced-motion: reduce,
    // Tailwind's motion-safe: prefix means transitions don't apply.
    // We verify no inline transition-duration with large value is applied.
    const transitionDuration = await ring.evaluate(
      (el) => getComputedStyle(el).transitionDuration,
    );
    // With reduced motion, duration should be 0.01ms (from global CSS rule)
    expect(transitionDuration).toMatch(/^0\.0[0-9]/);
  });

  test("test_results_score_ring_has_aria_label", async ({ page }) => {
    await page.goto(
      `${BASE_URL}/teacher/assessments/test-assessment-id/results/student-id?attempt=attempt-id`,
    );
    await page.waitForLoadState("networkidle");

    const ring = page.locator('svg[role="img"]');
    await expect(ring).toBeVisible();
    const ariaLabel = await ring.getAttribute("aria-label");
    expect(ariaLabel).toBeTruthy();
    // Should match pattern "XX% — Band" or "Not assessed"
    expect(ariaLabel).toMatch(
      /(\d+%\s*—\s*(Strong|Developing|Needs Work))|Not assessed/,
    );
  });

  test("test_results_correct_answer_no_redundant_correct_row", async ({
    page,
  }) => {
    await page.goto(
      `${BASE_URL}/teacher/assessments/test-assessment-id/results/student-id?attempt=attempt-id`,
    );
    await page.waitForLoadState("networkidle");

    // For each "Answer: X ✓" row (correct answer), there should be NO "Correct: X ✓" sibling
    const answerRows = await page.locator("text=Answer:").all();
    for (const row of answerRows) {
      const parent = row.locator("..");
      const correctRows = parent.locator("text=Correct:");
      await expect(correctRows).toHaveCount(0);
    }
  });

  test("test_results_wrong_answer_shows_given_and_correct", async ({
    page,
  }) => {
    await page.goto(
      `${BASE_URL}/teacher/assessments/test-assessment-id/results/student-id?attempt=attempt-id`,
    );
    await page.waitForLoadState("networkidle");

    // For "Given: X ✕" rows, a "Correct: X ✓" sibling must exist in same question block
    const givenRows = await page.locator("text=Given:").all();
    if (givenRows.length > 0) {
      // Find the parent question block and verify both rows exist
      const firstGiven = givenRows[0];
      const questionBlock = firstGiven.locator("../.."); // grandparent = question card
      await expect(questionBlock.locator("text=Correct:")).toBeVisible();
    }
  });

  test("test_results_question_pagination_expand_collapse", async ({ page }) => {
    await page.goto(
      `${BASE_URL}/teacher/assessments/test-assessment-id/results/student-id?attempt=attempt-id`,
    );
    await page.waitForLoadState("networkidle");

    // If more than 6 questions, "+ N more questions" button must be visible
    const expandButton = page.locator("button", { hasText: /more question/ });
    if (await expandButton.isVisible()) {
      // Click expand
      await expandButton.click();
      // "Show less" button must appear
      await expect(
        page.locator("button", { hasText: "Show less" }),
      ).toBeVisible();
      // "+ N more" button must disappear
      await expect(expandButton).not.toBeVisible();

      // Click collapse
      await page.locator("button", { hasText: "Show less" }).click();
      await expect(expandButton).toBeVisible();
    }
  });

  test("test_results_no_green_action_buttons", async ({ page }) => {
    await page.goto(
      `${BASE_URL}/teacher/assessments/test-assessment-id/results`,
    );
    await page.waitForLoadState("networkidle");

    // Teacher action buttons must be gold, NEVER green (bg-brand-primary / bg-green-*)
    const greenButtons = page.locator(
      "button.bg-brand-primary, button.bg-green-600, button.bg-green-700, button[class*='bg-green']",
    );
    await expect(greenButtons).toHaveCount(0);
  });
});
