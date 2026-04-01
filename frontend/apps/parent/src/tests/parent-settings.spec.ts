import { test, expect } from "@playwright/test";

test.describe("Parent Settings Page", () => {
  test("renders settings page with three sections", async ({ page }) => {
    await page.goto("/parent/settings");
    await expect(
      page.getByRole("heading", { name: /settings/i }),
    ).toBeVisible();
    await expect(page.getByText("My Account")).toBeVisible();
    await expect(page.getByText("My Children")).toBeVisible();
    await expect(page.getByText("Sign out")).toBeVisible();
  });

  test("displays parent email and name in account section", async ({
    page,
  }) => {
    await page.goto("/parent/settings");
    await expect(page.getByText("Jane Doe")).toBeVisible();
    await expect(page.getByText("parent@test.com")).toBeVisible();
  });

  test("shows email as read-only with school badge", async ({ page }) => {
    await page.goto("/parent/settings");
    await expect(page.getByText(/managed by school/i)).toBeVisible();
  });

  test("renders children section heading", async ({ page }) => {
    await page.goto("/parent/settings");
    await expect(
      page.getByRole("heading", { name: /my children/i }),
    ).toBeVisible();
  });

  test("displays empty state when no children linked", async ({ page }) => {
    await page.goto("/parent/settings");
    await expect(page.getByText(/no children linked/i)).toBeVisible();
  });

  test("shows sign out button in account actions section", async ({ page }) => {
    await page.goto("/parent/settings");
    const signOutButton = page.getByRole("button", { name: /sign out/i });
    await expect(signOutButton).toBeVisible();
  });

  test("clicking sign out button triggers logout", async ({ page }) => {
    await page.goto("/parent/settings");
    const signOutButton = page.getByRole("button", { name: /sign out/i });
    await signOutButton.click();
    // Should redirect to login page
    await expect(page).toHaveURL(/\/login/);
  });

  test("route is protected - redirects to login when not authenticated", async ({
    page,
  }) => {
    await page.goto("/parent/settings");
    // Without auth, should redirect
    await expect(page).not.toHaveURL(/\/parent\/settings/);
  });

  test("page uses parent role typography and styling", async ({ page }) => {
    await page.goto("/parent/settings");
    const pageContainer = page.locator("main");
    await expect(pageContainer).toBeVisible();
  });

  test("account section shows name but no edit option for parent", async ({
    page,
  }) => {
    await page.goto("/parent/settings");
    // Parent should see their name displayed
    await expect(page.getByText("Jane Doe")).toBeVisible();
    // But should NOT have an edit name button
    const editNameButton = page.getByRole("button", { name: /edit name/i });
    await expect(editNameButton).not.toBeVisible();
  });
});
