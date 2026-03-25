import { defineConfig, devices } from "@playwright/test";

/**
 * Kaihle Playwright E2E Configuration
 * Five apps: teacher (3001), student (3002), parent (3003),
 *             school-admin (3004), kaihle-admin (3005)
 *
 * Each app has its own project in this config so:
 *  1. Tests from each app only run against their own base URL
 *  2. CI can run each app's tests independently (for faster feedback)
 *  3. baseURL is per-project, not global
 *
 * See docs/design/DESIGN_SYSTEM.md for role-to-port mapping.
 */
export default defineConfig({
  testDir: "./apps",
  testMatch: "**/*.spec.ts",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [
    ["html", { outputFolder: "playwright-report", open: "never" }],
    ["list"],
    ...(process.env.CI ? [["github"] as any] : []),
  ],

  use: {
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "on-first-retry",
  },

  projects: [
    {
      name: "teacher",
      testMatch: "teacher/**/*.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: "http://localhost:3001",
      },
    },
    {
      name: "student",
      testMatch: "student/**/*.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: "http://localhost:3002",
      },
    },
    {
      name: "parent",
      testMatch: "parent/**/*.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: "http://localhost:3003",
      },
    },
    {
      name: "school-admin",
      testMatch: "school-admin/**/*.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: "http://localhost:3004",
      },
    },
    {
      name: "kaihle-admin",
      testMatch: "kaihle-admin/**/*.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: "http://localhost:3005",
      },
    },
  ],

  webServer: [
    {
      name: "teacher-app",
      command: "pnpm dev:teacher",
      url: "http://localhost:3001",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      name: "student-app",
      command: "pnpm dev:student",
      url: "http://localhost:3002",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      name: "parent-app",
      command: "pnpm dev:parent",
      url: "http://localhost:3003",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      name: "school-admin-app",
      command: "pnpm dev:school-admin",
      url: "http://localhost:3004",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      name: "kaihle-admin-app",
      command: "pnpm dev:kaihle-admin",
      url: "http://localhost:3005",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
