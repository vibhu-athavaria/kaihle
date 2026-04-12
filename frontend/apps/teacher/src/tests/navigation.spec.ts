import { test, expect } from "@playwright/test";

/**
 * E2E smoke tests for Teacher app new routes.
 * Verifies that newly added pages render without crashing.
 */
test.describe("Teacher App — New Routes", () => {
  test("classes_page_renders_classes_list", async ({ page }) => {
    await page.goto("/teacher/classes");
    await expect(page.locator("text=Classes")).toBeVisible();
  });

  test("students_page_renders_students_list", async ({ page }) => {
    await page.goto("/teacher/students");
    await expect(page.locator("text=Students")).toBeVisible();
  });

  test("assessments_page_renders_assessments_list", async ({ page }) => {
    await page.goto("/teacher/assessments");
    await expect(page.locator("text=Assessments")).toBeVisible();
  });

  test("clicking_gap_map_quick_link_navigates_to_correct_url", async ({
    page,
  }) => {
    await page.goto("/teacher/classes");
    const gapMapLink = page.locator("text=Gap Map").first();
    const href = await gapMapLink.getAttribute("href");
    expect(href).toContain("/gap-map");
  });

  test("back_link_from_gap_map_goes_to_class_detail", async ({ page }) => {
    await page.goto("/teacher/classes/cls-1/gap-map");
    const backLink = page.locator('a[href*="/teacher/classes/cls-1"]');
    await expect(backLink.first()).toBeVisible();
  });
});
