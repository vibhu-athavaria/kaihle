import { defineConfig, devices } from "@playwright/test";

const teacherPort = process.env.TEACHER_PORT || "3001";
const studentPort = process.env.STUDENT_PORT || "3002";
const parentPort = process.env.PARENT_PORT || "3003";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["html"], ["list"]],
  use: {
    baseURL: `http://localhost:${teacherPort}`,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "pnpm dev:teacher",
      url: `http://localhost:${teacherPort}`,
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
    {
      command: "pnpm dev:student",
      url: `http://localhost:${studentPort}`,
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
    {
      command: "pnpm dev:parent",
      url: `http://localhost:${parentPort}`,
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
  ],
});
