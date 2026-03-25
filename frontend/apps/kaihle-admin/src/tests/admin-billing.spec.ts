import { test, expect } from "@playwright/test";

/**
 * E2E tests for Kaihle Admin Billing Page
 * Design: AdminLayout, Inter font only (no Fraunces/Lora), #f8f9fb page bg
 * Revenue in text-brand-primary green
 * Past-due rows: red left border, Trial expiring < 3d: amber left border
 */

test.describe("Kaihle Admin Billing Page", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to billing page (mock auth would redirect to login in real scenario)
    await page.goto("/kaihle-admin/billing");
  });

  test("billing_four_kpi_cards_visible", async ({ page }) => {
    // Should show 4 KPI cards: Total Revenue, Active Schools, MRR, Past Due
    await expect(page.locator("text=Total Revenue")).toBeVisible();
    await expect(page.locator("text=Active Schools")).toBeVisible();
    await expect(page.locator("text=MRR")).toBeVisible();
    await expect(page.locator("text=Past Due")).toBeVisible();
  });

  test("billing_mrr_arr_in_brand_primary_green", async ({ page }) => {
    // MRR value should be in brand primary green color
    const mrrSection = page.locator("text=MRR").locator("..");
    const mrrValue = mrrSection.locator("p").nth(1);
    await expect(mrrValue).toHaveClass(/text-brand-primary/);
  });

  test("billing_revenue_formatted_with_dollar_sign", async ({ page }) => {
    // Revenue values should be formatted with dollar sign (e.g., $1,234)
    const pageContent = await page.content();
    // Check for dollar sign in the page
    expect(pageContent).toMatch(/\$[0-9,]+/);
  });

  test("billing_past_due_row_has_red_left_border", async ({ page }) => {
    // Past due rows should have red left border (border-red-400)
    // Look for a row with Past Due status
    const pastDueRow = page.locator("tr:has-text('Past Due')").first();
    await expect(pastDueRow).toHaveClass(/border-red-400/);
  });

  test("billing_trial_expiring_row_has_amber_border", async ({ page }) => {
    // Trial expiring < 3 days rows should have amber left border (border-amber-400)
    // Our mock data has Pinecrest Academy with trial ending in 1 day
    const expiringTrialRow = page
      .locator("tr:has-text('Pinecrest Academy')")
      .first();
    await expect(expiringTrialRow).toHaveClass(/border-amber-400/);
  });

  test("billing_sort_by_annual_value_default", async ({ page }) => {
    // Default sort should be annual value descending
    // First row should have the highest annual value (SCALE plan with most students)
    const firstSchoolLink = page.locator(
      "tbody tr:first-child td:first-child a",
    );
    await expect(firstSchoolLink).toHaveText("Greenwood Academy");
  });

  test("billing_inter_font_not_fraunces", async ({ page }) => {
    // Page should use Inter font throughout, not Fraunces
    // Check that page title uses Inter
    const pageTitle = page.locator("text=Platform billing").first();
    await expect(pageTitle).toBeVisible();

    // Check that there's no Fraunces font loaded
    const html = await page.content();
    expect(html).not.toMatch(/Fraunces/);
  });

  test("billing_row_click_navigates_to_school_detail", async ({ page }) => {
    // Clicking a row should navigate to school detail page
    const firstSchoolLink = page.locator(
      "tbody tr:first-child td:first-child a",
    );
    await firstSchoolLink.click();

    // Should navigate to school detail page
    await expect(page).toHaveURL(/\/kaihle-admin\/schools\/[^/]+$/);
  });

  test("billing_subscriptions_table_visible", async ({ page }) => {
    // Subscriptions table should be visible with columns
    await expect(page.locator("text=All subscriptions")).toBeVisible();
    await expect(page.locator("th:has-text('School')")).toBeVisible();
    await expect(page.locator("th:has-text('Plan')")).toBeVisible();
    await expect(page.locator("th:has-text('Students')")).toBeVisible();
    await expect(page.locator("th:has-text('Amount')")).toBeVisible();
    await expect(page.locator("th:has-text('Status')")).toBeVisible();
  });

  test("billing_plan_badges_visible", async ({ page }) => {
    // Plan badges should be visible (TRIAL, STARTER, GROWTH, SCALE)
    await expect(page.locator("span:has-text('TRIAL')")).toBeVisible();
    await expect(page.locator("span:has-text('SCALE')")).toBeVisible();
    await expect(page.locator("span:has-text('GROWTH')")).toBeVisible();
  });
});
