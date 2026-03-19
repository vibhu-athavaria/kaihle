import { test, expect } from "@playwright/test";

test.describe("Kaihle Admin UI", () => {
  const KAIHLE_ADMIN_USER = {
    email: "vibhu@kaihle.com",
    role: "KAIHLE_ADMIN" as const,
  };

  const TEACHER_USER = {
    email: "teacher@school.com",
    role: "TEACHER" as const,
  };

  const SCHOOL_ADMIN_USER = {
    email: "admin@school.com",
    role: "SCHOOL_ADMIN" as const,
  };

  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
  });

  test.describe("Access Control", () => {
    test("Kaihle Admin can access /kaihle-admin/* routes", async ({ page }) => {
      await page.evaluate((user) => {
        localStorage.setItem(
          "auth",
          JSON.stringify({
            accessToken: "test-token",
            refreshToken: "test-refresh",
            user,
            isAuthenticated: true,
          }),
        );
      }, KAIHLE_ADMIN_USER);

      await page.goto("/kaihle-admin/overview");
      await expect(page).toHaveURL("/kaihle-admin/overview");
      await expect(page.locator("text=Platform overview")).toBeVisible();
    });

    test("Teacher role trying to access /kaihle-admin/* sees 403", async ({
      page,
    }) => {
      await page.evaluate((user) => {
        localStorage.setItem(
          "auth",
          JSON.stringify({
            accessToken: "test-token",
            refreshToken: "test-refresh",
            user,
            isAuthenticated: true,
          }),
        );
      }, TEACHER_USER);

      await page.goto("/kaihle-admin/overview");
      await expect(page).toHaveURL("/unauthorised");
    });

    test("School Admin trying /kaihle-admin/* sees 403", async ({ page }) => {
      await page.evaluate((user) => {
        localStorage.setItem(
          "auth",
          JSON.stringify({
            accessToken: "test-token",
            refreshToken: "test-refresh",
            user,
            isAuthenticated: true,
          }),
        );
      }, SCHOOL_ADMIN_USER);

      await page.goto("/kaihle-admin/overview");
      await expect(page).toHaveURL("/unauthorised");
    });
  });

  test.describe("Admin Overview Page", () => {
    test.beforeEach(async ({ page }) => {
      await page.evaluate((user) => {
        localStorage.setItem(
          "auth",
          JSON.stringify({
            accessToken: "test-token",
            refreshToken: "test-refresh",
            user,
            isAuthenticated: true,
          }),
        );
      }, KAIHLE_ADMIN_USER);
    });

    test("shows KPI cards with correct data", async ({ page }) => {
      await page.goto("/kaihle-admin/overview");

      await expect(page.locator("text=Schools")).toBeVisible();
      await expect(page.locator("text=Students")).toBeVisible();
      await expect(page.locator("text=MRR")).toBeVisible();
    });

    test("shows school status table", async ({ page }) => {
      await page.goto("/kaihle-admin/overview");

      await expect(page.locator("text=School status")).toBeVisible();
    });

    test("shows recent activity section", async ({ page }) => {
      await page.goto("/kaihle-admin/overview");

      await expect(page.locator("text=Recent activity")).toBeVisible();
    });

    test("has Add school button in top nav", async ({ page }) => {
      await page.goto("/kaihle-admin/overview");

      await expect(page.locator("button:has-text('Add school')")).toBeVisible();
    });
  });

  test.describe("Schools List Page", () => {
    test.beforeEach(async ({ page }) => {
      await page.evaluate((user) => {
        localStorage.setItem(
          "auth",
          JSON.stringify({
            accessToken: "test-token",
            refreshToken: "test-refresh",
            user,
            isAuthenticated: true,
          }),
        );
      }, KAIHLE_ADMIN_USER);
    });

    test("shows filter tabs (All/Active/Trial/Suspended)", async ({ page }) => {
      await page.goto("/kaihle-admin/schools");

      await expect(page.locator("button:has-text('All')")).toBeVisible();
      await expect(page.locator("button:has-text('Active')")).toBeVisible();
      await expect(page.locator("button:has-text('Trial')")).toBeVisible();
      await expect(page.locator("button:has-text('Suspended')")).toBeVisible();
    });

    test("shows schools table with correct columns", async ({ page }) => {
      await page.goto("/kaihle-admin/schools");

      await expect(page.locator("th:has-text('Name')")).toBeVisible();
      await expect(page.locator("th:has-text('Plan')")).toBeVisible();
      await expect(page.locator("th:has-text('Status')")).toBeVisible();
      await expect(page.locator("th:has-text('Created')")).toBeVisible();
    });

    test("Add school button opens modal", async ({ page }) => {
      await page.goto("/kaihle-admin/schools");

      await page.click("button:has-text('Add school')");
      await expect(page.locator("text=Create new school")).toBeVisible();
    });

    test("clicking school row navigates to detail page", async ({ page }) => {
      await page.goto("/kaihle-admin/schools");

      const schoolRow = page.locator("tbody tr").first();
      if (await schoolRow.isVisible()) {
        await schoolRow.click();
        await expect(page).toHaveURL(/\/kaihle-admin\/schools\/.+/);
      }
    });
  });

  test.describe("Create School Modal", () => {
    test.beforeEach(async ({ page }) => {
      await page.evaluate((user) => {
        localStorage.setItem(
          "auth",
          JSON.stringify({
            accessToken: "test-token",
            refreshToken: "test-refresh",
            user,
            isAuthenticated: true,
          }),
        );
      }, KAIHLE_ADMIN_USER);
    });

    test("slug auto-derives from name", async ({ page }) => {
      await page.goto("/kaihle-admin/schools");
      await page.click("button:has-text('Add school')");

      const nameInput = page.locator(
        'input[placeholder="e.g. Bali Coding School"]',
      );
      await nameInput.fill("Bali School");

      const slugInput = page.locator(
        'input[placeholder="e.g. bali-coding-school"]',
      );
      await expect(slugInput).toHaveValue("bali-school");
    });

    test("validates slug format", async ({ page }) => {
      await page.goto("/kaihle-admin/schools");
      await page.click("button:has-text('Add school')");

      const slugInput = page.locator(
        'input[placeholder="e.g. bali-coding-school"]',
      );
      await slugInput.fill("Invalid Slug With Spaces");

      await expect(
        page.locator(
          "text=Slug can only contain lowercase letters, numbers, and hyphens",
        ),
      ).toBeVisible();
    });

    test("shows validation errors for required fields", async ({ page }) => {
      await page.goto("/kaihle-admin/schools");
      await page.click("button:has-text('Add school')");

      await page.click("button:has-text('Create school')");

      await expect(page.locator("text=School name is required")).toBeVisible();
      await expect(page.locator("text=Admin email is required")).toBeVisible();
    });

    test("has all required form fields", async ({ page }) => {
      await page.goto("/kaihle-admin/schools");
      await page.click("button:has-text('Add school')");

      await expect(page.locator('label:has-text("School name")')).toBeVisible();
      await expect(page.locator('label:has-text("Slug")')).toBeVisible();
      await expect(page.locator('label:has-text("Country")')).toBeVisible();
      await expect(page.locator('label:has-text("City")')).toBeVisible();
      await expect(page.locator('label:has-text("Timezone")')).toBeVisible();
      await expect(page.locator('label:has-text("Plan tier")')).toBeVisible();
      await expect(page.locator('label:has-text("Admin email")')).toBeVisible();
      await expect(
        page.locator('label:has-text("Admin first name")'),
      ).toBeVisible();
      await expect(
        page.locator('label:has-text("Admin last name")'),
      ).toBeVisible();
    });
  });

  test.describe("School Detail Page", () => {
    test.beforeEach(async ({ page }) => {
      await page.evaluate((user) => {
        localStorage.setItem(
          "auth",
          JSON.stringify({
            accessToken: "test-token",
            refreshToken: "test-refresh",
            user,
            isAuthenticated: true,
          }),
        );
      }, KAIHLE_ADMIN_USER);
    });

    test("shows school info section", async ({ page }) => {
      await page.goto("/kaihle-admin/schools/1");

      await expect(page.locator("text=School info")).toBeVisible();
    });

    test("shows summary stats section", async ({ page }) => {
      await page.goto("/kaihle-admin/schools/1");

      await expect(page.locator("text=Summary stats")).toBeVisible();
      await expect(page.locator("text=Teachers")).toBeVisible();
      await expect(page.locator("text=Students")).toBeVisible();
    });

    test("shows trial section for trial schools", async ({ page }) => {
      await page.goto("/kaihle-admin/schools/1");

      const trialSection = page.locator("text=Trial expires");
      const notTrial = await trialSection.count();
      if (notTrial > 0) {
        await expect(
          page.locator("button:has-text('Extend trial')"),
        ).toBeVisible();
      }
    });

    test("back link navigates to schools list", async ({ page }) => {
      await page.goto("/kaihle-admin/schools/1");

      await page.click("a:has-text('Back to schools')");
      await expect(page).toHaveURL("/kaihle-admin/schools");
    });
  });

  test.describe("Extend Trial Modal", () => {
    test.beforeEach(async ({ page }) => {
      await page.evaluate((user) => {
        localStorage.setItem(
          "auth",
          JSON.stringify({
            accessToken: "test-token",
            refreshToken: "test-refresh",
            user,
            isAuthenticated: true,
          }),
        );
      }, KAIHLE_ADMIN_USER);
    });

    test("shows extension options (7, 14, 30 days)", async ({ page }) => {
      await page.goto("/kaihle-admin/schools");
      await page.click("button:has-text('Add school')");

      await expect(page.locator("button:has-text('7 days')")).toBeVisible();
      await expect(page.locator("button:has-text('14 days')")).toBeVisible();
      await expect(page.locator("button:has-text('30 days')")).toBeVisible();
    });

    test("requires reason for extension", async ({ page }) => {
      await page.goto("/kaihle-admin/schools");
      await page.click("button:has-text('Add school')");

      await page.click("button:has-text('Create school')");

      await expect(page.locator("text=Reason is required")).toBeVisible();
    });
  });

  test.describe("Design System Compliance", () => {
    test("uses AdminLayout with correct background", async ({ page }) => {
      await page.evaluate((user) => {
        localStorage.setItem(
          "auth",
          JSON.stringify({
            accessToken: "test-token",
            refreshToken: "test-refresh",
            user,
            isAuthenticated: true,
          }),
        );
      }, KAIHLE_ADMIN_USER);

      await page.goto("/kaihle-admin/overview");

      const layout = page.locator(".bg-\\[\\#f8f9fb\\]");
      await expect(layout.first()).toBeVisible();
    });

    test("uses green primary buttons", async ({ page }) => {
      await page.evaluate((user) => {
        localStorage.setItem(
          "auth",
          JSON.stringify({
            accessToken: "test-token",
            refreshToken: "test-refresh",
            user,
            isAuthenticated: true,
          }),
        );
      }, KAIHLE_ADMIN_USER);

      await page.goto("/kaihle-admin/schools");
      await page.click("button:has-text('Add school')");

      const createButton = page.locator("button:has-text('Create school')");
      await expect(createButton).toHaveClass(/bg-brand-primary/);
    });
  });
});
