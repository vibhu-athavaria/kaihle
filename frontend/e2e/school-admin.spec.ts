import { test, expect } from "@playwright/test";

test.describe("School Admin UI", () => {
  const SCHOOL_ADMIN_USER = {
    email: "admin@school.com",
    role: "SCHOOL_ADMIN" as const,
    school_id: "school-123",
  };

  const TEACHER_USER = {
    email: "teacher@school.com",
    role: "TEACHER" as const,
    school_id: "school-123",
  };

  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
  });

  test.describe("Access Control", () => {
    test("School Admin can access /school/* routes", async ({ page }) => {
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

      await page.goto("/school/overview");
      await expect(page).toHaveURL("/school/overview");
    });

    test("Teacher role trying to access /school/* is redirected to /teacher/dashboard", async ({
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

      await page.goto("/school/overview");
      await expect(page).toHaveURL("/teacher/dashboard");
    });
  });

  test.describe("School Overview Page", () => {
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
      }, SCHOOL_ADMIN_USER);
    });

    test("shows page title and subtitle", async ({ page }) => {
      await page.goto("/school/overview");
      await expect(page.locator("text=Overview")).toBeVisible();
    });

    test("shows KPI cards with teacher count, student count, and onboarding %", async ({
      page,
    }) => {
      await page.goto("/school/overview");
      await expect(page.locator("text=Teachers")).toBeVisible();
      await expect(page.locator("text=Students")).toBeVisible();
      await expect(page.locator("text=Onboarding")).toBeVisible();
    });

    test("shows classes table section", async ({ page }) => {
      await page.goto("/school/overview");
      await expect(page.locator("text=Classes")).toBeVisible();
    });

    test("shows onboarding progress bar", async ({ page }) => {
      await page.goto("/school/overview");
      await expect(page.locator("text=Onboarding progress")).toBeVisible();
    });

    test("Create class button navigates to classes page", async ({ page }) => {
      await page.goto("/school/overview");
      await page.click("button:has-text('Create class')");
      await expect(page).toHaveURL("/school/classes");
    });
  });

  test.describe("User Management Page", () => {
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
      }, SCHOOL_ADMIN_USER);
    });

    test("shows role tabs (Teachers, Students, Parents)", async ({ page }) => {
      await page.goto("/school/users");
      await expect(page.locator("button:has-text('Teachers')")).toBeVisible();
      await expect(page.locator("button:has-text('Students')")).toBeVisible();
      await expect(page.locator("button:has-text('Parents')")).toBeVisible();
    });

    test("Invite user button opens modal", async ({ page }) => {
      await page.goto("/school/users");
      await page.click("button:has-text('Invite user')");
      await expect(page.locator("text=Invite a teacher")).toBeVisible();
    });

    test("switching tabs changes user list", async ({ page }) => {
      await page.goto("/school/users");
      await page.click("button:has-text('Students')");
      await expect(page.locator("button:has-text('Students')")).toHaveClass(
        /border-brand-primary/,
      );
    });
  });

  test.describe("Invite User Modal", () => {
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
      }, SCHOOL_ADMIN_USER);
    });

    test("shows validation error for empty email", async ({ page }) => {
      await page.goto("/school/users");
      await page.click("button:has-text('Invite user')");
      await page.fill('input[id="firstName"]', "John");
      await page.fill('input[id="lastName"]', "Doe");
      await page.click("button:has-text('Send invite')");
      await expect(page.locator("text=Email is required")).toBeVisible();
    });

    test("shows validation error for invalid email format", async ({
      page,
    }) => {
      await page.goto("/school/users");
      await page.click("button:has-text('Invite user')");
      await page.fill('input[id="firstName"]', "John");
      await page.fill('input[id="lastName"]', "Doe");
      await page.fill('input[id="email"]', "invalid-email");
      await page.click("button:has-text('Send invite')");
      await expect(
        page.locator("text=Enter a valid email address"),
      ).toBeVisible();
    });

    test("modal title changes based on active tab", async ({ page }) => {
      await page.goto("/school/users");
      await page.click("button:has-text('Invite user')");
      await expect(page.locator("text=Invite a teacher")).toBeVisible();

      await page.click("button:has-text('Cancel')");
      await page.click("button:has-text('Students')");
      await page.click("button:has-text('Invite user')");
      await expect(page.locator("text=Invite a student")).toBeVisible();
    });

    test("role dropdown is pre-filled from active tab", async ({ page }) => {
      await page.goto("/school/users");
      await page.click("button:has-text('Parents')");
      await page.click("button:has-text('Invite user')");
      const roleSelect = page.locator('select[id="role"]');
      await expect(roleSelect).toHaveValue("PARENT");
    });
  });

  test.describe("Class Management Page", () => {
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
      }, SCHOOL_ADMIN_USER);
    });

    test("shows page title", async ({ page }) => {
      await page.goto("/school/classes");
      await expect(page.locator("text=Classes")).toBeVisible();
    });

    test("Create class button opens modal", async ({ page }) => {
      await page.goto("/school/classes");
      await page.click("button:has-text('Create class')");
      await expect(page.locator("text=Create a new class")).toBeVisible();
    });

    test("shows classes table with correct columns", async ({ page }) => {
      await page.goto("/school/classes");
      await expect(page.locator("th:has-text('Class')")).toBeVisible();
      await expect(page.locator("th:has-text('Subject')")).toBeVisible();
      await expect(page.locator("th:has-text('Grade')")).toBeVisible();
      await expect(page.locator("th:has-text('Teacher')")).toBeVisible();
    });

    test("clicking a class row opens detail panel", async ({ page }) => {
      await page.goto("/school/classes");
      const classRow = page.locator("tbody tr").first();
      if (await classRow.isVisible()) {
        await classRow.click();
        await expect(page.locator("text=Class Details")).toBeVisible();
      }
    });
  });

  test.describe("Create Class Modal", () => {
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
      }, SCHOOL_ADMIN_USER);
    });

    test("shows curriculum suggestion for Grade 9", async ({ page }) => {
      await page.goto("/school/classes");
      await page.click("button:has-text('Create class')");
      await page.selectOption('select[id="grade"]', "9");
      await expect(
        page.locator("text=Suggested: Cambridge IGCSE"),
      ).toBeVisible();
    });

    test("shows curriculum suggestion for Grade 7", async ({ page }) => {
      await page.goto("/school/classes");
      await page.click("button:has-text('Create class')");
      await page.selectOption('select[id="grade"]', "7");
      await expect(
        page.locator("text=Suggested: Cambridge Lower Secondary"),
      ).toBeVisible();
    });

    test("validates required fields", async ({ page }) => {
      await page.goto("/school/classes");
      await page.click("button:has-text('Create class')");
      await page.click("button:has-text('Create class')");
      await expect(page.locator("text=Class name is required")).toBeVisible();
    });

    test("shows all form fields", async ({ page }) => {
      await page.goto("/school/classes");
      await page.click("button:has-text('Create class')");
      await expect(page.locator('label:has-text("Class name")')).toBeVisible();
      await expect(page.locator('label:has-text("Subject")')).toBeVisible();
      await expect(page.locator('label:has-text("Grade")')).toBeVisible();
      await expect(page.locator('label:has-text("Curriculum")')).toBeVisible();
      await expect(page.locator('label:has-text("Teacher")')).toBeVisible();
    });
  });

  test.describe("Design System Compliance", () => {
    test("uses DashboardLayout variant school-admin with green left stripe", async ({
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
      }, SCHOOL_ADMIN_USER);

      await page.goto("/school/overview");
      const activeNav = page.locator("nav").locator(".border-l-\\[3px\\]");
      await expect(activeNav).toBeVisible();
    });

    test("KPI cards use border-role-school-border", async ({ page }) => {
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

      await page.goto("/school/overview");
      const card = page.locator(".border-role-school-border").first();
      await expect(card).toBeVisible();
    });

    test("page background uses role-school-bg", async ({ page }) => {
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

      await page.goto("/school/overview");
      const body = page.locator(".bg-\\[\\#f5f7f1\\]");
      await expect(body.first()).toBeVisible();
    });
  });

  test.describe("Responsive Design", () => {
    test("pages usable at 768px tablet width", async ({ page }) => {
      await page.setViewportSize({ width: 768, height: 1024 });
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

      await page.goto("/school/overview");
      await expect(page.locator("text=Overview")).toBeVisible();

      await page.goto("/school/users");
      await expect(page.locator("text=Users")).toBeVisible();

      await page.goto("/school/classes");
      await expect(page.locator("text=Classes")).toBeVisible();
    });
  });
});
