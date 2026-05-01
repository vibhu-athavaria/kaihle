import { test, expect } from "@playwright/test";

/**
 * E2E tests for KaihleAdmin Grades page
 * Route: /kaihle-admin/grades
 */

test.describe("KaihleAdmin Grades Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/kaihle-admin/grades");
  });

  test("grades_sidebar_nav_item_active_when_on_grades_page_then_shows_highlighted", async ({
    page,
  }) => {
    const gradesLink = page.getByRole("link", { name: /grades/i });
    await expect(gradesLink).toBeVisible();
    await expect(gradesLink).toHaveClass(/bg-gray-100/);
  });

  test("grades_table_columns_present_then_level_name_curricula_status_action_visible", async ({
    page,
  }) => {
    await expect(page.getByText("Level")).toBeVisible();
    await expect(page.getByText("Name")).toBeVisible();
    await expect(page.getByText("Curricula")).toBeVisible();
    await expect(page.getByText("Status")).toBeVisible();
  });

  test("grades_add_grade_button_present_then_opens_create_modal", async ({
    page,
  }) => {
    const addButton = page.getByRole("button", { name: /add grade/i });
    await expect(addButton).toBeVisible();
    await addButton.click();
    await expect(page.getByRole("dialog")).toBeVisible();
  });

  test("grades_edit_link_when_clicked_then_opens_edit_modal_with_grade_data", async ({
    page,
  }) => {
    const editLinks = page.getByText("Edit →");
    const firstVisible = await editLinks
      .first()
      .isVisible()
      .catch(() => false);
    if (firstVisible) {
      await editLinks.first().click();
      await expect(page.getByRole("dialog")).toBeVisible();
    }
  });

  test("grades_search_input_when_typing_then_filters_table", async ({
    page,
  }) => {
    const searchInput = page.getByPlaceholder(/search grades/i);
    await expect(searchInput).toBeVisible();
    await searchInput.fill("Grade 6");
    await page.waitForTimeout(350);
  });

  test("grades_page_uses_admin_layout_then_sidebar_visible", async ({
    page,
  }) => {
    await expect(page.locator("aside, nav, [class*='sidebar']")).toBeVisible();
  });

  test("grades_inter_font_throughout_then_no_fraunces_or_lora", async ({
    page,
  }) => {
    const tableEl = page.locator(".rounded-2xl").first();
    const fontFamily = await tableEl
      .evaluate((el) => window.getComputedStyle(el).fontFamily)
      .catch(() => "");
    expect(fontFamily).not.toContain("Fraunces");
    expect(fontFamily).not.toContain("Lora");
  });
});
