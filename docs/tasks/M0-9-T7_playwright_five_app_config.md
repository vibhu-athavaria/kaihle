# M0-9-T7 — Playwright Five-App Configuration
**Milestone:** M0 — Foundations
**Epic:** M0-9 — Architecture Corrections and Spec Alignment
**Task ID:** M0-9-T7
**Depends on:** M0-9-T1 (school-admin and kaihle-admin apps scaffolded and running)
**Blocks:** All E2E tests for apps/parent, apps/school-admin, apps/kaihle-admin
**Estimated effort:** 1–2 hours
**Design sprint:** Kramer (configuration) with Pixel (test infrastructure verification)

> **Why this task exists:**
> `frontend/playwright.config.ts` currently only specifies `webServer` entries for
> `http://localhost:3001` (teacher) and `http://localhost:3002` (student). The three
> remaining apps — parent (3003), school-admin (3004), kaihle-admin (3005) — have no
> E2E infrastructure.
>
> Every E2E spec file written for these three apps will either:
> (a) Run against the wrong base URL (teacher app), testing the wrong thing entirely, or
> (b) Fail to start because the web server isn't registered
>
> This one-file fix needs a task because it also requires adding CI/CD workflow entries
> for the new test jobs.

---

## Files to Modify

```
frontend/playwright.config.ts                   ← MODIFY: add 3 new webServer entries + projects
.github/workflows/ci.yml                        ← MODIFY: add E2E jobs for 3 new apps
```

---

## `frontend/playwright.config.ts` — Full Updated File

Replace the existing file with:

```typescript
import { defineConfig, devices } from '@playwright/test'

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
  testDir: './apps',
  testMatch: '**/*.spec.ts',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['list'],
    ...(process.env.CI ? [['github'] as any] : []),
  ],

  use: {
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
  },

  projects: [
    {
      name: 'teacher',
      testMatch: 'teacher/**/*.spec.ts',
      use: {
        ...devices['Desktop Chrome'],
        baseURL: 'http://localhost:3001',
      },
    },
    {
      name: 'student',
      testMatch: 'student/**/*.spec.ts',
      use: {
        ...devices['Desktop Chrome'],
        baseURL: 'http://localhost:3002',
      },
    },
    {
      name: 'parent',
      testMatch: 'parent/**/*.spec.ts',
      use: {
        ...devices['Desktop Chrome'],
        baseURL: 'http://localhost:3003',
      },
      // Parent app is mobile-first — run tests at 375px as well
    },
    {
      name: 'parent-mobile',
      testMatch: 'parent/**/*.spec.ts',
      use: {
        ...devices['iPhone 13'],
        baseURL: 'http://localhost:3003',
      },
    },
    {
      name: 'school-admin',
      testMatch: 'school-admin/**/*.spec.ts',
      use: {
        ...devices['Desktop Chrome'],
        baseURL: 'http://localhost:3004',
      },
    },
    {
      name: 'kaihle-admin',
      testMatch: 'kaihle-admin/**/*.spec.ts',
      use: {
        ...devices['Desktop Chrome'],
        baseURL: 'http://localhost:3005',
      },
    },
  ],

  webServer: [
    {
      name: 'teacher-app',
      command: 'pnpm dev:teacher',
      url: 'http://localhost:3001',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      name: 'student-app',
      command: 'pnpm dev:student',
      url: 'http://localhost:3002',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      name: 'parent-app',
      command: 'pnpm dev:parent',
      url: 'http://localhost:3003',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      name: 'school-admin-app',
      command: 'pnpm dev:school-admin',
      url: 'http://localhost:3004',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      name: 'kaihle-admin-app',
      command: 'pnpm dev:kaihle-admin',
      url: 'http://localhost:3005',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
})
```

---

## `.github/workflows/ci.yml` — E2E Job Update

In the existing CI workflow, the E2E job currently runs all tests in one job. Update
to run each app's tests as a separate matrix job so failures are isolated:

Find the existing `test-e2e` job and replace with:

```yaml
  test-e2e:
    name: E2E Tests (${{ matrix.app }})
    runs-on: ubuntu-latest
    needs: [test-backend, lint-frontend-teacher, lint-frontend-student]
    strategy:
      fail-fast: false    # don't cancel all apps if one fails
      matrix:
        app: [teacher, student, parent, school-admin, kaihle-admin]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install pnpm
        uses: pnpm/action-setup@v3
        with:
          version: 9

      - name: Install dependencies
        working-directory: frontend
        run: pnpm install --frozen-lockfile

      - name: Install Playwright browsers
        working-directory: frontend
        run: pnpm exec playwright install --with-deps chromium

      - name: Run E2E tests for ${{ matrix.app }}
        working-directory: frontend
        run: pnpm exec playwright test --project=${{ matrix.app }}
        env:
          CI: true

      - name: Upload test results
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report-${{ matrix.app }}
          path: frontend/playwright-report/
          retention-days: 7
```

---

## Pixel — Test Infrastructure Verification Checklist

After this task is complete, Pixel verifies the E2E test infrastructure is correctly
connected to each app's design spec:

**For each app, verify:**

```
apps/teacher/src/tests/   → runs against localhost:3001 (teacher app — gold actions)
apps/student/src/tests/   → runs against localhost:3002 (student app — green actions, no sidebar)
apps/parent/src/tests/    → runs against localhost:3003 (parent app — Lora, cream bg)
                            ALSO runs with iPhone 13 viewport (parent-mobile project)
apps/school-admin/src/tests/ → runs against localhost:3004 (school admin — green actions, left stripe)
apps/kaihle-admin/src/tests/ → runs against localhost:3005 (kaihle admin — Inter only)
```

**Design-aware E2E smoke test** — add this test to each app's spec to verify it loaded the correct app:

```typescript
// Add to each app's main spec file:

// apps/teacher/src/tests/teacher-app.spec.ts
test('loaded_correct_app_teacher_uses_gold_actions', async ({ page }) => {
  await page.goto('/login')
  await expect(page).toHaveURL(/localhost:3001/)
  // Verify the login page has the Teacher Portal label
  await expect(page.locator('text=Teacher Portal')).toBeVisible()
})

// apps/student/src/tests/student-app.spec.ts
test('loaded_correct_app_student_uses_green_actions', async ({ page }) => {
  await page.goto('/login')
  await expect(page).toHaveURL(/localhost:3002/)
  await expect(page.locator('text=Student Portal')).toBeVisible()
})

// apps/parent/src/tests/parent-app.spec.ts
test('loaded_correct_app_parent_has_lora_font', async ({ page }) => {
  await page.goto('/login')
  await expect(page).toHaveURL(/localhost:3003/)
})

// apps/school-admin/src/tests/school-admin-app.spec.ts
test('loaded_correct_app_school_admin', async ({ page }) => {
  await page.goto('/login')
  await expect(page).toHaveURL(/localhost:3004/)
})

// apps/kaihle-admin/src/tests/kaihle-admin-app.spec.ts
test('loaded_correct_app_kaihle_admin', async ({ page }) => {
  await page.goto('/login')
  await expect(page).toHaveURL(/localhost:3005/)
})
```

---

## Acceptance Criteria

- [ ] `pnpm exec playwright test --project=teacher` runs teacher tests against localhost:3001
- [ ] `pnpm exec playwright test --project=student` runs student tests against localhost:3002
- [ ] `pnpm exec playwright test --project=parent` runs parent tests against localhost:3003
- [ ] `pnpm exec playwright test --project=school-admin` runs against localhost:3004
- [ ] `pnpm exec playwright test --project=kaihle-admin` runs against localhost:3005
- [ ] CI matrix runs 5 parallel E2E jobs (teacher, student, parent, school-admin, kaihle-admin)
- [ ] A failure in school-admin tests does not cancel teacher tests (`fail-fast: false`)
- [ ] Test artifacts are uploaded on failure per app
- [ ] `playwright.config.ts` TypeScript compiles without errors

---

## Do NOT Touch

- Existing test specs — only the config changes
- Any application code
- The `.github/workflows/deploy.yml` — deployment is separate from testing
