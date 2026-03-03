# M0-1-T3 — CI/CD Pipeline (GitHub Actions)
**Milestone:** M0 — Foundations
**Epic:** M0-1 — Repository & Project Setup
**Task ID:** M0-1-T3
**Mode:** Code (MiniMax)
**Estimated effort:** 2–3 hours

---

## Context

This task sets up automated CI (on every PR) and CD (on merge to `main`). The CI pipeline enforces code quality and test coverage before any code reaches `main`. The CD pipeline deploys to Render.com automatically on merge.

**Depends on:** M0-1-T1 (monorepo structure), M0-1-T2 (Docker Compose for service tests)

---

## User Story

As a developer, I want every pull request automatically tested and every merge to `main` automatically deployed so that broken code never reaches production.

---

## What To Build

### `/.github/workflows/ci.yml`

```yaml
name: CI

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [develop]

jobs:

  lint-backend:
    name: Backend Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install uv
        run: pip install uv
      - name: Install dependencies
        run: uv pip install --system -e ".[dev]"
        working-directory: backend
      - name: Run ruff
        run: ruff check .
        working-directory: backend
      - name: Run mypy
        run: mypy app/
        working-directory: backend

  test-backend:
    name: Backend Tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: kaihle
          POSTGRES_PASSWORD: kaihle
          POSTGRES_DB: kaihle_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5
    env:
      DATABASE_URL: postgresql+asyncpg://kaihle:kaihle@localhost:5432/kaihle_test
      REDIS_URL: redis://localhost:6379/0
      CELERY_BROKER_URL: redis://localhost:6379/1
      CELERY_RESULT_BACKEND: redis://localhost:6379/2
      JWT_SECRET_KEY: test-secret-key-for-ci-only-not-production
      JWT_ALGORITHM: HS256
      RESEND_API_KEY: test-key
      ENVIRONMENT: test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install uv
        run: pip install uv
      - name: Install dependencies
        run: uv pip install --system -e ".[dev]"
        working-directory: backend
      - name: Enable pgvector extension
        run: |
          PGPASSWORD=kaihle psql -h localhost -U kaihle -d kaihle_test \
            -c "CREATE EXTENSION IF NOT EXISTS vector;"
      - name: Run migrations
        run: alembic upgrade head
        working-directory: backend
        env:
          DATABASE_URL: postgresql+asyncpg://kaihle:kaihle@localhost:5432/kaihle_test
      - name: Run pytest with coverage
        run: |
          pytest app/tests/ \
            --cov=app/services \
            --cov-report=xml \
            --cov-report=term-missing \
            --cov-fail-under=90 \
            -v
        working-directory: backend
      - name: Post coverage comment
        uses: py-cov-action/python-coverage-comment-action@v3
        if: github.event_name == 'pull_request'
        with:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          COVERAGE_DATA_FILE: backend/coverage.xml

  lint-frontend:
    name: Frontend Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - uses: pnpm/action-setup@v4
        with:
          version: 9
      - name: Install dependencies
        run: pnpm install
        working-directory: frontend
      - name: Run prettier check
        run: pnpm exec prettier --check "**/*.{ts,tsx,json,css}"
        working-directory: frontend
      - name: Run eslint
        run: pnpm lint
        working-directory: frontend

  test-frontend-unit:
    name: Frontend Unit Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - uses: pnpm/action-setup@v4
        with:
          version: 9
      - name: Install dependencies
        run: pnpm install
        working-directory: frontend
      - name: Run Jest tests
        run: pnpm test -- --coverage --passWithNoTests
        working-directory: frontend

  test-e2e:
    name: E2E Tests (Playwright)
    runs-on: ubuntu-latest
    needs: [test-backend, test-frontend-unit]
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: kaihle
          POSTGRES_PASSWORD: kaihle
          POSTGRES_DB: kaihle_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
    env:
      DATABASE_URL: postgresql+asyncpg://kaihle:kaihle@localhost:5432/kaihle_test
      REDIS_URL: redis://localhost:6379/0
      CELERY_BROKER_URL: redis://localhost:6379/1
      CELERY_RESULT_BACKEND: redis://localhost:6379/2
      JWT_SECRET_KEY: test-secret-key-for-ci-only-not-production
      RESEND_API_KEY: test-key
      ENVIRONMENT: test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - uses: pnpm/action-setup@v4
        with:
          version: 9
      - name: Install backend dependencies
        run: pip install uv && uv pip install --system -e ".[dev]"
        working-directory: backend
      - name: Run migrations
        run: alembic upgrade head
        working-directory: backend
      - name: Start backend
        run: uvicorn app.main:app --host 0.0.0.0 --port 8000 &
        working-directory: backend
      - name: Install frontend dependencies
        run: pnpm install
        working-directory: frontend
      - name: Build frontend apps
        run: pnpm build
        working-directory: frontend
      - name: Install Playwright browsers
        run: pnpm exec playwright install --with-deps chromium
        working-directory: frontend
      - name: Wait for backend to be ready
        run: |
          for i in {1..30}; do
            curl -sf http://localhost:8000/health && break
            sleep 2
          done
      - name: Run Playwright tests
        run: pnpm exec playwright test
        working-directory: frontend
      - name: Upload Playwright report on failure
        uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-report
          path: frontend/playwright-report/
```

---

### `/.github/workflows/deploy.yml`

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    name: Deploy Backend to Render
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Render deploy
        run: |
          curl -X POST \
            -H "Authorization: Bearer ${{ secrets.RENDER_API_KEY }}" \
            "https://api.render.com/v1/services/${{ secrets.RENDER_BACKEND_SERVICE_ID }}/deploys" \
            -H "Content-Type: application/json" \
            -d '{}'

  deploy-frontend:
    name: Deploy Frontend to Render
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Render deploy (teacher app)
        run: |
          curl -X POST \
            -H "Authorization: Bearer ${{ secrets.RENDER_API_KEY }}" \
            "https://api.render.com/v1/services/${{ secrets.RENDER_TEACHER_SERVICE_ID }}/deploys" \
            -H "Content-Type: application/json" \
            -d '{}'
      - name: Trigger Render deploy (student app)
        run: |
          curl -X POST \
            -H "Authorization: Bearer ${{ secrets.RENDER_API_KEY }}" \
            "https://api.render.com/v1/services/${{ secrets.RENDER_STUDENT_SERVICE_ID }}/deploys" \
            -H "Content-Type: application/json" \
            -d '{}'
      - name: Trigger Render deploy (parent app)
        run: |
          curl -X POST \
            -H "Authorization: Bearer ${{ secrets.RENDER_API_KEY }}" \
            "https://api.render.com/v1/services/${{ secrets.RENDER_PARENT_SERVICE_ID }}/deploys" \
            -H "Content-Type: application/json" \
            -d '{}'
```

---

### GitHub Secrets Required

Document these in `README.md` — they must be set in GitHub repo Settings → Secrets:

| Secret | Description |
|---|---|
| `RENDER_API_KEY` | Render account API key |
| `RENDER_BACKEND_SERVICE_ID` | Render service ID for FastAPI backend |
| `RENDER_TEACHER_SERVICE_ID` | Render service ID for teacher frontend |
| `RENDER_STUDENT_SERVICE_ID` | Render service ID for student frontend |
| `RENDER_PARENT_SERVICE_ID` | Render service ID for parent frontend |

Note: These IDs are set up in M6 when Render services are created. For now, document them so they are not forgotten.

---

### Playwright Config

**`/kaihle/frontend/playwright.config.ts`:**

```typescript
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './apps',
  testMatch: '**/*.e2e.ts',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['html'], ['list']],
  use: {
    baseURL: 'http://localhost:3001',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: 'pnpm dev:teacher',
      url: 'http://localhost:3001',
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'pnpm dev:student',
      url: 'http://localhost:3002',
      reuseExistingServer: !process.env.CI,
    },
  ],
})
```

---

## Files To Create

```
/.github/workflows/ci.yml
/.github/workflows/deploy.yml
/kaihle/frontend/playwright.config.ts
```

---

## Acceptance Criteria

- [ ] Opening a PR to `main` or `develop` triggers the CI workflow within 2 minutes
- [ ] A PR with backend service coverage < 90% causes `test-backend` job to fail with clear message
- [ ] A PR with a failing Playwright test causes `test-e2e` job to fail
- [ ] A PR with `ruff` lint errors causes `lint-backend` job to fail
- [ ] Coverage report is posted as a comment on the PR
- [ ] Merging to `main` triggers `deploy.yml` (deploy jobs will fail gracefully until Render secrets are set in M6 — that is expected)
- [ ] All workflow YAML files pass GitHub Actions syntax validation (no parse errors)

---

## Dependencies

- M0-1-T1 — monorepo structure with `backend/` and `frontend/` directories
- M0-1-T2 — Dockerfile for backend build step
- M0-2-T1 — Alembic must be in place for the `alembic upgrade head` step in CI (CI will fail until M0-2-T1 is done — that is expected and acceptable)

## Output (What Next Tasks Can Use)

- Every subsequent task's code is automatically tested on PR
- Coverage gate enforced — all service files must maintain ≥ 90%
- Deployment pipeline ready for M6 when Render services are configured
