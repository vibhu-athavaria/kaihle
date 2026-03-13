import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["html"], ["list"]],
  use: {
    baseURL: "http://localhost:3001",
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
      url: "http://localhost:3001",
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
    {
      command: "pnpm dev:student",
      url: "http://localhost:3002",
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
    {
      command: "pnpm dev:parent",
      url: "http://localhost:3003",
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
  ],
});
