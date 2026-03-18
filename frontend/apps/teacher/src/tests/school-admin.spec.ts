import { test, expect, type Page } from "@playwright/test";

const mockAnalytics = {
  teacher_count: 8,
  student_count: 147,
  parent_count: 45,
  onboarding_percentage: 73,
  onboarded_students: 107,
  total_students: 147,
};

const mockClasses = [
  {
    id: "cls-1",
    name: "Maths 9B",
    subject: "MATH",
    grade: 9,
    teacher_id: "teacher-1",
    teacher_name: "Ms. Ravi",
    student_count: 28,
    curriculum_id: "cur-1",
    curriculum_name: "Cambridge IGCSE",
    status: "ACTIVE",
  },
  {
    id: "cls-2",
    name: "Science 8A",
    subject: "SCI",
    grade: 8,
    teacher_id: "teacher-2",
    teacher_name: "Mr. Tan",
    student_count: 24,
    curriculum_id: "cur-1",
    curriculum_name: "Cambridge Lower Secondary",
    status: "ACTIVE",
  },
  {
    id: "cls-3",
    name: "English 10",
    subject: "ENG",
    grade: 10,
    teacher_id: "teacher-3",
    teacher_name: "Ms. Wu",
    student_count: 31,
    curriculum_id: "cur-2",
    curriculum_name: "Cambridge IGCSE",
    status: "ACTIVE",
  },
];

const mockTeachers = [
  {
    id: "teacher-1",
    first_name: "Ravi",
    last_name: "Sharma",
    email: "ravi@school.com",
    role: "TEACHER",
    status: "ACTIVE",
    created_at: "2024-01-01",
  },
  {
    id: "teacher-2",
    first_name: "Tan",
    last_name: "Kumar",
    email: "tan@school.com",
    role: "TEACHER",
    status: "ACTIVE",
    created_at: "2024-01-02",
  },
  {
    id: "teacher-3",
    first_name: "Wu",
    last_name: "Ling",
    email: "wu@school.com",
    role: "TEACHER",
    status: "INVITED",
    created_at: "2024-01-03",
  },
];

const mockStudents = [
  {
    id: "student-1",
    first_name: "Alice",
    last_name: "Brown",
    email: "alice@school.com",
    role: "STUDENT",
    status: "ACTIVE",
    created_at: "2024-01-01",
  },
  {
    id: "student-2",
    first_name: "Bob",
    last_name: "Smith",
    email: "bob@school.com",
    role: "STUDENT",
    status: "ACTIVE",
    created_at: "2024-01-02",
  },
];

const mockCurricula = [
  { id: "cur-1", name: "Cambridge Lower Secondary", level: "lower" },
  { id: "cur-2", name: "Cambridge IGCSE", level: "igcse" },
  { id: "cur-3", name: "Cambridge A-Level", level: "alevel" },
];

const mockGrades = [
  { id: "g-6", level: 6, label: "Grade 6" },
  { id: "g-7", level: 7, label: "Grade 7" },
  { id: "g-8", level: 8, label: "Grade 8" },
  { id: "g-9", level: 9, label: "Grade 9" },
  { id: "g-10", level: 10, label: "Grade 10" },
  { id: "g-11", level: 11, label: "Grade 11" },
  { id: "g-12", level: 12, label: "Grade 12" },
];

async function setupMocks(page: Page) {
  await page.route("**/api/v1/schools/*/analytics", async (route) => {
    await route.fulfill({ status: 200, body: JSON.stringify(mockAnalytics) });
  });

  await page.route("**/api/v1/schools/*/classes", async (route) => {
    await route.fulfill({ status: 200, body: JSON.stringify(mockClasses) });
  });

  await page.route("**/api/v1/schools/*/users**", async (route) => {
    const url = route.request().url();
    if (url.includes("role=teacher")) {
      await route.fulfill({ status: 200, body: JSON.stringify(mockTeachers) });
    } else if (url.includes("role=student")) {
      await route.fulfill({ status: 200, body: JSON.stringify(mockStudents) });
    } else {
      await route.fulfill({ status: 200, body: JSON.stringify([]) });
    }
  });

  await page.route("**/api/v1/curricula", async (route) => {
    await route.fulfill({ status: 200, body: JSON.stringify(mockCurricula) });
  });

  await page.route("**/api/v1/grades", async (route) => {
    await route.fulfill({ status: 200, body: JSON.stringify(mockGrades) });
  });

  await page.route("**/api/v1/schools/*/users", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON();
      await route.fulfill({
        status: 201,
        body: JSON.stringify({
          id: "new-user-id",
          ...body,
          status: "INVITED",
          created_at: new Date().toISOString(),
        }),
      });
    }
  });

  await page.route("**/api/v1/schools/*/classes", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON();
      await route.fulfill({
        status: 201,
        body: JSON.stringify({
          id: "new-class-id",
          ...body,
          student_count: 0,
          status: "ACTIVE",
          teacher_name: "",
        }),
      });
    }
  });
}

test.describe("School Admin UI", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem(
        "auth_user",
        JSON.stringify({
          id: "user-1",
          role: "SCHOOL_ADMIN",
          school_id: "school-1",
        }),
      );
      window.localStorage.setItem("auth_token", "mock-token");
    });
    await setupMocks(page);
  });

  test("School Admin lands on overview page after login", async ({ page }) => {
    await page.goto("/school/overview");
    await expect(page).toHaveURL("/school/overview");
    await expect(page.locator("h1, h2").first()).toContainText("Overview");
  });

  test("Overview shows correct KPIs", async ({ page }) => {
    await page.goto("/school/overview");
    await expect(page.locator("text=Teachers")).toBeVisible();
    await expect(page.locator("text=8")).toBeVisible();
    await expect(page.locator("text=Students")).toBeVisible();
    await expect(page.locator("text=147")).toBeVisible();
    await expect(page.locator("text=Onboarding")).toBeVisible();
    await expect(page.locator("text=73%")).toBeVisible();
  });

  test("Invite user modal opens from users page", async ({ page }) => {
    await page.goto("/school/users");
    await page.click("text=Invite user");
    await expect(page.locator("text=Invite a teacher")).toBeVisible();
  });

  test("Role tabs switch between Teachers/Students/Parents", async ({
    page,
  }) => {
    await page.goto("/school/users");
    await expect(page.locator("text=Teachers")).toBeVisible();
    await expect(page.locator("text=RSavi Sharma")).toBeVisible();

    await page.click("text=Students");
    await expect(page.locator("text=Alice Brown")).toBeVisible();
  });

  test("Create class modal opens", async ({ page }) => {
    await page.goto("/school/classes");
    await page.click("text=Create class");
    await expect(page.locator("text=Create a new class")).toBeVisible();
  });

  test("Clicking class row opens side panel", async ({ page }) => {
    await page.goto("/school/classes");
    await page.click("text=Maths 9B");
    await expect(page.locator("text=Class Details")).toBeVisible();
  });

  test("Teacher role accessing school routes redirects to teacher dashboard", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem(
        "auth_user",
        JSON.stringify({
          id: "user-1",
          role: "TEACHER",
          school_id: "school-1",
        }),
      );
    });
    await page.goto("/school/overview");
    await expect(page).toHaveURL(/\/teacher\/dashboard/);
  });
});

test.describe("InviteUserModal validation", () => {
  test("shows validation error for invalid email", async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem(
        "auth_user",
        JSON.stringify({
          id: "user-1",
          role: "SCHOOL_ADMIN",
          school_id: "school-1",
        }),
      );
      window.localStorage.setItem("auth_token", "mock-token");
    });
    await setupMocks(page);

    await page.goto("/school/users");
    await page.click("text=Invite user");

    await page.fill('input[id="email"]', "invalid-email");
    await page.click('button[type="submit"]');

    await expect(
      page.locator("text=Enter a valid email address"),
    ).toBeVisible();
  });
});

test.describe("CreateClassModal curriculum suggestions", () => {
  test("Grade 9 suggests Cambridge IGCSE", async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem(
        "auth_user",
        JSON.stringify({
          id: "user-1",
          role: "SCHOOL_ADMIN",
          school_id: "school-1",
        }),
      );
      window.localStorage.setItem("auth_token", "mock-token");
    });
    await setupMocks(page);

    await page.goto("/school/classes");
    await page.click("text=Create class");

    await page.selectOption('select[id="grade"]', "9");

    await expect(page.locator("text=Suggested: Cambridge IGCSE")).toBeVisible();
  });

  test("Grade 7 suggests Cambridge Lower Secondary", async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem(
        "auth_user",
        JSON.stringify({
          id: "user-1",
          role: "SCHOOL_ADMIN",
          school_id: "school-1",
        }),
      );
      window.localStorage.setItem("auth_token", "mock-token");
    });
    await setupMocks(page);

    await page.goto("/school/classes");
    await page.click("text=Create class");

    await page.selectOption('select[id="grade"]', "7");

    await expect(
      page.locator("text=Suggested: Cambridge Lower Secondary"),
    ).toBeVisible();
  });
});
