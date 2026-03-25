import { test, expect } from "@playwright/test";
import { UserRole } from "@kaihle/types";

/**
 * E2E tests for Teacher Settings page
 * Route: /teacher/settings
 * Design: DashboardLayout variant="teacher", gold primary buttons
 */

const mockTeacherUser = {
  id: "teacher-1",
  email: "ravi.tan@school.edu",
  first_name: "Ravi",
  last_name: "Tan",
  role: UserRole.TEACHER,
  school_id: "school-1",
  updated_at: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString(), // 3 months ago
};

test.describe("Teacher Settings Page", () => {
  test.beforeEach(async ({ page }) => {
    // Set auth state for teacher
    await page.evaluate((user) => {
      localStorage.setItem(
        "kaihle-auth",
        JSON.stringify({
          state: {
            accessToken: "mock-token",
            refreshToken: "mock-refresh",
            user: user,
            isAuthenticated: true,
          },
          version: 0,
        }),
      );
    }, mockTeacherUser);
  });

  test("settings_page_when_loaded_then_name_email_password_rows_visible", async ({
    page,
  }) => {
    await page.goto("/teacher/settings");

    // Wait for the page to load
    await expect(page.locator("h1:has-text('Settings')")).toBeVisible();

    // Assert three rows are visible: Name, Email, Password
    await expect(page.locator("text=Name")).toBeVisible();
    await expect(page.locator("text=Email")).toBeVisible();
    await expect(page.locator("text=Password")).toBeVisible();

    // Verify email value
    await expect(page.locator(`text=${mockTeacherUser.email}`)).toBeVisible();

    // Verify "Managed by school" label for email
    await expect(page.locator("text=Managed by school")).toBeVisible();
  });

  test("settings_page_when_edit_name_clicked_then_form_expands", async ({
    page,
  }) => {
    await page.goto("/teacher/settings");

    // Wait for page to load
    await expect(page.locator("h1:has-text('Settings')")).toBeVisible();

    // Click Edit on Name row
    await page.click("button:has-text('Edit')");

    // Assert two input fields (first name, last name) become visible
    await expect(page.locator("label:has-text('First name')")).toBeVisible();
    await expect(page.locator("label:has-text('Last name')")).toBeVisible();
    await expect(page.locator("#firstName")).toBeVisible();
    await expect(page.locator("#lastName")).toBeVisible();
  });

  test("settings_page_when_name_saved_then_form_collapses", async ({
    page,
  }) => {
    // Mock the PATCH /api/v1/users/me endpoint
    await page.route("**/api/v1/users/me", async (route) => {
      if (route.request().method() === "PATCH") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ...mockTeacherUser,
            first_name: "Ravi",
            last_name: "Updated",
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(mockTeacherUser),
        });
      }
    });

    await page.goto("/teacher/settings");
    await expect(page.locator("h1:has-text('Settings')")).toBeVisible();

    // Click Edit on Name row
    await page.click("button:has-text('Edit')");

    // Fill in new name
    await page.fill("#firstName", "Ravi");
    await page.fill("#lastName", "Updated");

    // Click Save
    await page.click("button:has-text('Save')");

    // Wait for form to collapse
    await expect(page.locator("#firstName")).not.toBeVisible();
    await expect(page.locator("#lastName")).not.toBeVisible();

    // Verify the new name appears in the row
    await expect(page.locator("text=Ravi Updated")).toBeVisible();
  });

  test("settings_page_when_change_password_clicked_then_form_expands", async ({
    page,
  }) => {
    await page.goto("/teacher/settings");

    // Wait for page to load
    await expect(page.locator("h1:has-text('Settings')")).toBeVisible();

    // Click Change on Password row
    await page.click("button:has-text('Change')");

    // Assert three password input fields are visible
    await expect(
      page.locator("label:has-text('Current password')"),
    ).toBeVisible();
    await expect(page.locator("label:has-text('New password')")).toBeVisible();
    await expect(
      page.locator("label:has-text('Confirm new password')"),
    ).toBeVisible();
    await expect(page.locator("#currentPassword")).toBeVisible();
    await expect(page.locator("#newPassword")).toBeVisible();
    await expect(page.locator("#confirmPassword")).toBeVisible();
  });

  test("settings_page_when_new_passwords_dont_match_then_error_shown", async ({
    page,
  }) => {
    await page.goto("/teacher/settings");

    // Wait for page to load
    await expect(page.locator("h1:has-text('Settings')")).toBeVisible();

    // Click Change on Password row
    await page.click("button:has-text('Change')");

    // Fill mismatched passwords
    await page.fill("#currentPassword", "oldpassword123");
    await page.fill("#newPassword", "newpassword123");
    await page.fill("#confirmPassword", "differentpassword");

    // Assert client-side validation error is visible
    await expect(page.locator("text=Passwords do not match")).toBeVisible();

    // Assert Update password button should be disabled
    const updateButton = page.locator("button:has-text('Update password')");
    await expect(updateButton).toBeDisabled();
  });

  test("settings_page_when_wrong_current_password_then_api_error_shown", async ({
    page,
  }) => {
    // Mock POST /api/v1/auth/change-password to return 400
    await page.route("**/api/v1/auth/change-password", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 400,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Current password is incorrect" }),
        });
      }
    });

    await page.goto("/teacher/settings");

    // Wait for page to load
    await expect(page.locator("h1:has-text('Settings')")).toBeVisible();

    // Click Change on Password row
    await page.click("button:has-text('Change')");

    // Fill passwords
    await page.fill("#currentPassword", "wrongpassword");
    await page.fill("#newPassword", "newpassword123");
    await page.fill("#confirmPassword", "newpassword123");

    // Click Update password
    await page.click("button:has-text('Update password')");

    // Assert inline error "Current password is incorrect" is visible
    await expect(
      page.locator("text=Current password is incorrect"),
    ).toBeVisible();
  });

  test("settings_page_when_sign_out_clicked_then_redirects_to_login", async ({
    page,
  }) => {
    // Mock POST /api/v1/auth/logout
    await page.route("**/api/v1/auth/logout", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({}),
        });
      }
    });

    await page.goto("/teacher/settings");

    // Wait for page to load
    await expect(page.locator("h1:has-text('Settings')")).toBeVisible();

    // Click Sign out button
    await page.click("button:has-text('Sign out')");

    // Assert URL changes to /login
    await expect(page).toHaveURL(/\/login/);
  });

  test("settings_page_when_name_form_open_and_password_clicked_then_name_form_closes", async ({
    page,
  }) => {
    await page.goto("/teacher/settings");

    // Wait for page to load
    await expect(page.locator("h1:has-text('Settings')")).toBeVisible();

    // Open the name edit form
    await page.click("button:has-text('Edit')");
    await expect(page.locator("#firstName")).toBeVisible();
    await expect(page.locator("#lastName")).toBeVisible();

    // Click Change on password row
    await page.click("button:has-text('Change')");

    // Assert name form is no longer visible
    await expect(page.locator("#firstName")).not.toBeVisible();
    await expect(page.locator("#lastName")).not.toBeVisible();

    // Assert password form is visible
    await expect(page.locator("#currentPassword")).toBeVisible();
  });
});
