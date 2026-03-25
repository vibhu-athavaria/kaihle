import { test, expect } from "@playwright/test";

/**
 * E2E tests for School Admin Settings page
 * Route: /school-admin/settings
 * Tests the three sections: My Account, School Profile, Account Actions
 */
test.describe("School Admin Settings", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate directly to settings page
    // Note: In a real scenario, would need to be authenticated first
    await page.goto("/school-admin/settings");
  });

  test("settings_when_loaded_then_three_sections_visible", async ({ page }) => {
    // Assert My Account section is visible
    await expect(page.locator("text=MY ACCOUNT")).toBeVisible();

    // Assert School Profile section is visible
    await expect(page.locator("text=SCHOOL PROFILE")).toBeVisible();

    // Assert Account Actions section is visible
    await expect(page.locator("text=ACCOUNT ACTIONS")).toBeVisible();
  });

  test("settings_when_edit_name_clicked_then_two_inputs_visible", async ({
    page,
  }) => {
    // Wait for the page to load
    await page.waitForLoadState("networkidle");

    // Click the Edit button in the name row
    const editButton = page.locator("button:has-text('Edit')").first();
    await editButton.click();

    // Assert first name and last name inputs appear
    await expect(page.locator("#firstName")).toBeVisible();
    await expect(page.locator("#lastName")).toBeVisible();
  });

  test("settings_when_name_saved_then_row_updates", async ({ page }) => {
    // Wait for the page to load
    await page.waitForLoadState("networkidle");

    // Mock the PATCH /users/me endpoint
    await page.route("**/api/v1/users/me", async (route) => {
      if (route.request().method() === "PATCH") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "1",
            email: "admin@test.com",
            first_name: "New",
            last_name: "Name",
            role: "SCHOOL_ADMIN",
            school_id: "1",
          }),
        });
      }
    });

    // Click the Edit button in the name row
    const editButton = page.locator("button:has-text('Edit')").first();
    await editButton.click();

    // Fill in the new name
    await page.locator("#firstName").fill("New");
    await page.locator("#lastName").fill("Name");

    // Click Save
    await page.locator("button:has-text('Save')").click();

    // Assert the row shows new name
    await expect(page.locator("text=New Name")).toBeVisible();
  });

  test("settings_when_school_profile_then_no_edit_links", async ({ page }) => {
    // Wait for the page to load
    await page.waitForLoadState("networkidle");

    // Find the School Profile section
    const schoolProfileSection = page
      .locator("text=SCHOOL PROFILE")
      .locator("..");

    // Assert no "Edit" link or input field is present in the School Profile section
    const editLinksInSchoolProfile = schoolProfileSection.locator(
      "button:has-text('Edit')",
    );
    await expect(editLinksInSchoolProfile).toHaveCount(0);

    // Also check that there are no input fields
    const inputsInSchoolProfile = schoolProfileSection.locator("input");
    await expect(inputsInSchoolProfile).toHaveCount(0);
  });

  test("settings_when_password_mismatch_then_error_before_api", async ({
    page,
  }) => {
    // Wait for the page to load
    await page.waitForLoadState("networkidle");

    // Click the Change button in the password row
    const changeButton = page.locator("button:has-text('Change')");
    await changeButton.click();

    // Fill in the password fields with mismatching values
    await page.locator("#currentPassword").fill("currentpass");
    await page.locator("#newPassword").fill("newpassword123");
    await page.locator("#confirmPassword").fill("differentpassword");

    // Try to submit - the error should appear before API call
    await page.locator("button:has-text('Update password')").click();

    // Assert validation error is shown
    await expect(page.locator("text=Passwords do not match")).toBeVisible();
  });

  test("settings_when_wrong_current_password_then_error_shown", async ({
    page,
  }) => {
    // Wait for the page to load
    await page.waitForLoadState("networkidle");

    // Mock the POST /auth/change-password endpoint to return 400
    await page.route("**/api/v1/auth/change-password", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 400,
          contentType: "application/json",
          body: JSON.stringify({ message: "Current password is incorrect" }),
        });
      }
    });

    // Click the Change button in the password row
    const changeButton = page.locator("button:has-text('Change')");
    await changeButton.click();

    // Fill in the password fields
    await page.locator("#currentPassword").fill("wrongpassword");
    await page.locator("#newPassword").fill("newpassword123");
    await page.locator("#confirmPassword").fill("newpassword123");

    // Submit
    await page.locator("button:has-text('Update password')").click();

    // Assert error message is shown
    await expect(
      page.locator("text=Current password is incorrect"),
    ).toBeVisible();
  });

  test("settings_when_sign_out_then_redirects_to_login", async ({ page }) => {
    // Wait for the page to load
    await page.waitForLoadState("networkidle");

    // Mock the POST /auth/logout endpoint
    await page.route("**/api/v1/auth/logout", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({}),
        });
      }
    });

    // Click sign out button
    const signOutButton = page.locator("button:has-text('Sign out')");
    await signOutButton.click();

    // Assert URL becomes /login
    await expect(page).toHaveURL(/\/login/);
  });
});
