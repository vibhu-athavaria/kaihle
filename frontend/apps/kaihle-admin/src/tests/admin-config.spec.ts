import { test, expect } from "@playwright/test";

/**
 * E2E tests for KaihleAdmin Config page (Page 6)
 * Route: /kaihle-admin/config
 *
 * Acceptance criteria from task file:
 * - Three sections: LLM Provider, Trial Settings, Rate Limits
 * - RunPod row has red "Blocked" badge with data-testid
 * - NO save buttons or edit controls (no false affordance)
 * - All values sourced from GET /platform/stats
 * - Inter font only (Pixel)
 */

test.describe("KaihleAdmin Config Page", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to config page - assumes auth is handled
    await page.goto("/kaihle-admin/config");
  });

  test("config_three_sections_visible_then_displays_llm_trial_rate_limit", async ({
    page,
  }) => {
    // Verify three sections are visible
    await expect(page.getByText("LLM Provider")).toBeVisible();
    await expect(page.getByText("Trial Settings")).toBeVisible();
    await expect(page.getByText("Rate Limits")).toBeVisible();
  });

  test("config_runpod_status_has_red_badge_then_shows_blocked", async ({
    page,
  }) => {
    // RunPod row should have red "Blocked" badge with data-testid
    const runpodRow = page.locator("[data-testid='runpod-status']");
    await expect(runpodRow).toBeVisible();

    // Badge should show "Blocked" text
    await expect(runpodRow.getByText("Blocked")).toBeVisible();

    // Badge should have red styling (bg-red-50 text-red-600)
    const badge = runpodRow
      .locator("span.rounded-full")
      .filter({ hasText: "Blocked" });
    await expect(badge).toHaveClass(/bg-red-50/);
    await expect(badge).toHaveClass(/text-red-600/);
  });

  test("config_no_save_or_edit_buttons_then_page_is_read_only", async ({
    page,
  }) => {
    // No save buttons should exist
    const saveButtons = page.getByRole("button", { name: /save/i });
    await expect(saveButtons).toHaveCount(0);

    // No edit buttons should exist
    const editButtons = page.getByRole("button", { name: /edit/i });
    await expect(editButtons).toHaveCount(0);

    // No input fields that suggest editing (text inputs are for search only)
    const configSection = page.locator(".bg-white.rounded-2xl").first();
    const textInputs = configSection.locator(
      "input[type='text'], input[type='number']",
    );
    await expect(textInputs).toHaveCount(0);
  });

  test("config_all_values_from_api_then_displays_platform_stats", async ({
    page,
  }) => {
    // Verify LLM Provider section has values
    await expect(page.getByText("Active Provider")).toBeVisible();

    // Verify Trial Settings section has values
    await expect(page.getByText("Default Trial Length")).toBeVisible();
    await expect(page.getByText("Max Trial Students")).toBeVisible();

    // Verify Rate Limits section has values
    await expect(page.getByText("Requests per Minute")).toBeVisible();
    await expect(page.getByText("Concurrent Users")).toBeVisible();
  });

  test("config_inter_font_throughout_then_no_fraunces_or_lora", async ({
    page,
  }) => {
    // Check that Inter font is used by examining computed styles
    const sections = page.locator(".bg-white.rounded-2xl");
    const count = await sections.count();

    for (let i = 0; i < count; i++) {
      const fontFamily = await sections
        .nth(i)
        .evaluate((el) => window.getComputedStyle(el).fontFamily);
      // Should not contain Fraunces or Lora
      expect(fontFamily).not.toContain("Fraunces");
      expect(fontFamily).not.toContain("Lora");
    }
  });

  test("config_page_uses_admin_layout_then_has_correct_wrapper", async ({
    page,
  }) => {
    // AdminLayout should be present - look for sidebar navigation
    await expect(page.locator("nav, aside, [class*='sidebar']")).toBeVisible();
  });
});
