# Kaihle — Deployment Readiness + Unified Login Page Plan
**Executor:** Coding agent  
**Author:** Kramer  
**Date:** 2026-04-22  
**Branch strategy:** All tasks are independent — each branches from `main`. Execute sequentially. Never merge — open PR and wait for human review.

### Review Sign-Off

| Reviewer | Scope | Status | Issues found |
|---|---|---|---|
| Kramer | T1–T6 architecture, backend, CI/CD | ✅ Reviewed | CORS already had all 5 ports (corrected from initial draft); dev-server-in-prod Dockerfiles confirmed; alembic missing from deploy pipeline |
| Pixel | T5 login pages, T6 role-picker UI | ✅ Reviewed | 5 issues found and patched: `buttonClassName` prop missing; `as const` type conflict; env var fallback missing; `font-display` token assumption; banned `hover:shadow-sm` |
| Vidhya | — | n/a — no curriculum content in this plan | — |

---

## Context & Constraints

- Five React/Vite/TypeScript frontend apps in a pnpm monorepo (`frontend/`)
- FastAPI/Python 3.12 backend (`backend/`)
- Each frontend app has `Dockerfile` (CI/production) and `Dockerfile.dev` (local dev, mounts host node_modules)
- `docker-compose.yml` references plain `Dockerfile` for all frontend services
- All five frontend `Dockerfile` variants currently end with `CMD ["pnpm", "dev:*"]` — Vite dev server
- `docker-compose.yml` is used for **local development only** — production runs on Render.com
- Each app already has a `build` script in `package.json`: `"build": "tsc && vite build"`
- CORS in `backend/app/main.py` already includes all five localhost ports (3001–3005) — **do not remove any existing origins**
- Production CORS origins are missing — they need to be added from environment config
- Design system lives in `docs/design/DESIGN_SYSTEM.md` — load it before touching any UI component
- `LoginForm` component lives in `packages/ui/src/LoginForm.tsx` — this is what all five apps currently use

---

## Pre-Flight Dependency Graph

```
Task 1 (Dockerfile prod builds)     ← no dependencies
Task 2 (CORS prod origins)          ← no dependencies
Task 3 (backend Dockerfile)         ← no dependencies
Task 4 (alembic in deploy.yml)      ← no dependencies
Task 5 (unified login page)         ← no dependencies
Task 6 (kaihle.com integration)     ← depends on Task 5 (login URLs must exist first)
```

All tasks except Task 6 are independent. Execute Tasks 1–5 in parallel branches, then Task 6 after Task 5 is merged.

**Migration flags:** Task 2 touches `main.py`. Task 3 touches `backend/Dockerfile`. Tasks 1 touches five Dockerfiles. Task 4 touches `.github/workflows/deploy.yml`. Task 5 touches `packages/ui/src/LoginForm.tsx` and all five `LoginPage.tsx` files.

**Conflict risk:** Low. Files are distinct per task. Only `packages/ui/src/LoginForm.tsx` (Task 5) is a shared file — no other task touches it.

---

## Task 1 — Fix Frontend Dockerfiles: Dev Server → Production Builds

**Branch:** `deploy/T1-frontend-prod-dockerfiles`  
**Files touched:**
- `frontend/apps/teacher/Dockerfile`
- `frontend/apps/student/Dockerfile`
- `frontend/apps/parent/Dockerfile`
- `frontend/apps/school-admin/Dockerfile`
- `frontend/apps/kaihle-admin/Dockerfile`

**Do NOT touch:** The five `Dockerfile.dev` files. They are correct as-is for local dev.

### Problem

All five production `Dockerfile` files install dependencies then run `CMD ["pnpm", "dev:*"]`. This ships Vite's dev server — with HMR, unminified JS, file watchers, and hot reload — into production. The plain `Dockerfile` is meant for CI/production; the `Dockerfile.dev` is for local Docker dev.

### Fix

Replace each `Dockerfile` with a two-stage build: (1) Node builder compiles the static bundle via `tsc && vite build`, (2) nginx serves the dist directory.

**Replace ALL FIVE Dockerfiles with the following pattern.** Substitute app name, port, and filter name per app. The table below maps each:

| App | Port | pnpm filter name | Build output dir |
|---|---|---|---|
| teacher | 3001 | `teacher` | `apps/teacher/dist` |
| student | 3002 | `student` | `apps/student/dist` |
| parent | 3003 | `parent` | `apps/parent/dist` |
| school-admin | 3004 | `@kaihle/school-admin` | `apps/school-admin/dist` |
| kaihle-admin | 3005 | `@kaihle/kaihle-admin` | `apps/kaihle-admin/dist` |

**Template (apply to each, substituting `APP_NAME`, `APP_PORT`, `PNPM_FILTER`, `DIST_PATH`):**

```dockerfile
# ============================================================================
# PRODUCTION BUILD
# Stage 1: build the static bundle
# Stage 2: serve with nginx
# For local Docker dev, use Dockerfile.dev instead
# ============================================================================

# ── Stage 1: Build ──────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

RUN npm install -g pnpm

# Copy workspace manifest files first (layer caching)
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/APP_NAME/package.json ./apps/APP_NAME/package.json
COPY packages ./packages

# Install dependencies from lockfile (frozen — no version drift)
RUN pnpm install --frozen-lockfile

# Copy application source
COPY apps/APP_NAME ./apps/APP_NAME

# Build the static bundle
RUN pnpm --filter PNPM_FILTER build

# ── Stage 2: Serve ──────────────────────────────────────────────────────────
FROM nginx:stable-alpine

# Copy built assets
COPY --from=builder /app/DIST_PATH /usr/share/nginx/html

# nginx config: serve on APP_PORT, route all paths to index.html (SPA)
RUN printf 'server {\n\
    listen APP_PORT;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE APP_PORT

CMD ["nginx", "-g", "daemon off;"]
```

**Critical:** The `try_files $uri $uri/ /index.html` line is required. Without it, refreshing any deep route (e.g. `/teacher/classes/123`) returns nginx 404 instead of letting React Router handle it.

**Also required — add `build` config to each `vite.config.ts`:**

Each app's `vite.config.ts` currently only has `server` config. Add an `outDir` to keep builds explicit:

```ts
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    // ... existing server config unchanged
  },
});
```

### Acceptance Criteria

- [ ] `docker build -f apps/teacher/Dockerfile .` succeeds from `frontend/` directory
- [ ] The built image runs nginx, not a node process
- [ ] `curl http://localhost:3001/` returns the teacher app HTML
- [ ] `curl http://localhost:3001/teacher/classes/abc` returns `index.html` (not 404)
- [ ] All five apps build without TypeScript errors (`tsc` step passes)
- [ ] `Dockerfile.dev` files are untouched

---

## Task 2 — Add Production CORS Origins via Environment Config

**Branch:** `deploy/T2-cors-prod-origins`  
**Files touched:**
- `backend/app/main.py`
- `backend/app/core/config.py`

### Problem

`main.py` hardcodes only `localhost` CORS origins. When deployed to Render, requests from `https://teacher.kaihle.com` (or whatever subdomain/URL Render assigns) will be rejected by CORS with no meaningful error on the client side.

### Fix

**Step 1 — Read `backend/app/core/config.py` in full before touching it.** Then add a `cors_origins` setting that reads from the environment:

```python
# In Settings class — add alongside existing fields
cors_origins: list[str] = Field(
    default=[
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:3004",
        "http://localhost:3005",
    ],
    description="Comma-separated list of allowed CORS origins. "
                "In production, set CORS_ORIGINS env var.",
)

model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore",
    # Allow CORS_ORIGINS to be set as a comma-separated string
    # e.g. CORS_ORIGINS=https://teacher.kaihle.com,https://student.kaihle.com
)
```

If `config.py` already uses `SettingsConfigDict` — do not duplicate it, just add the field. Read the file first.

**Step 2 — Update `main.py`** to use the config value instead of the hardcoded list:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # replaces the hardcoded list
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Step 3 — Add to `.env.example`:**

```bash
# CORS — add production frontend URLs here
# Comma-separated. Localhost origins are included by default in development.
CORS_ORIGINS=https://teacher.kaihle.com,https://student.kaihle.com,https://parent.kaihle.com,https://admin.kaihle.com,https://app.kaihle.com
```

**Note:** The actual production URLs are placeholders. Vibhu sets real values in Render's environment dashboard after services are provisioned. The agent must not hardcode real URLs — only the localhost defaults in the Settings class default value.

### Acceptance Criteria

- [ ] `CORS_ORIGINS` env var unset → behaviour identical to current (localhost origins only)
- [ ] `CORS_ORIGINS=https://teacher.kaihle.com` → that origin is accepted, localhost origins still work
- [ ] `settings.cors_origins` returns a `list[str]` in all cases
- [ ] `.env.example` updated with the new variable and comment
- [ ] Existing unit tests for config still pass

---

## Task 3 — Fix Backend Dockerfile: Remove Dev Dependencies from Production Image

**Branch:** `deploy/T3-backend-dockerfile`  
**Files touched:**
- `backend/Dockerfile`

### Problem

The production backend `Dockerfile` installs `.[dev]` which includes pytest, ruff, mypy, and other dev tools. These bloat the image (~80MB extra) and have no place in a production container.

### Fix

Replace with a two-stage build that separates dependency installation from the runtime image, and installs only production dependencies:

```dockerfile
# ── Stage 1: Dependencies ────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .

# Install only production dependencies (no [dev] extras)
RUN uv pip install --system -e "."

# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

**Note on `--workers 2`:** Render's starter tier gives 512MB RAM. Two uvicorn workers is appropriate for a pilot-scale load. Do not set higher without profiling.

**Do NOT touch:** `backend/Dockerfile.dev` does not exist (only the plain Dockerfile exists for backend). Confirm this before writing.

### Acceptance Criteria

- [ ] `docker build -f backend/Dockerfile .` succeeds from `backend/` directory
- [ ] The built image does not contain `pytest`, `ruff`, or `mypy` binaries
- [ ] `docker run` starts uvicorn and the `/health` endpoint responds 200
- [ ] Image size is smaller than the current single-stage build

---

## Task 4 — Add Alembic Migration Step to Deploy Pipeline

**Branch:** `deploy/T4-alembic-deploy-hook`  
**Files touched:**
- `.github/workflows/deploy.yml`

### Problem

`deploy.yml` triggers a Render redeploy via the API but never runs `alembic upgrade head`. If a merged PR contains a migration, the new backend binary starts against the old schema — silent 500s until someone manually runs the migration from a shell.

### Fix

Render supports a **pre-deploy command** that runs before traffic is routed to the new instance. This is the right place for migrations — not a separate job.

**Update `deploy.yml` to add the migration explanation as a comment**, because the actual pre-deploy command is configured in Render's dashboard, not in the GitHub Actions workflow. The deploy hook just triggers the deploy; Render handles the pre-deploy command internally.

Add the following to `deploy.yml` as an explicit comment block at the top of the `deploy-backend` job:

```yaml
deploy-backend:
  name: Deploy Backend to Render
  if: ${{ github.event.workflow_run.conclusion == 'success' }}
  runs-on: ubuntu-latest
  # ─────────────────────────────────────────────────────────────────────────
  # RENDER PRE-DEPLOY COMMAND (set in Render dashboard, not here):
  #   alembic upgrade head
  #
  # This must be configured under:
  #   Render Dashboard → kaihle-backend service → Settings → Pre-Deploy Command
  #
  # The deploy trigger below starts the deploy. Render runs the pre-deploy
  # command before routing traffic to the new instance — so migrations always
  # run before new code goes live.
  # ─────────────────────────────────────────────────────────────────────────
  steps:
    - name: Trigger Render deploy (backend)
      run: |
        curl --fail -X POST \
          -H "Authorization: Bearer ${{ secrets.RENDER_API_KEY }}" \
          "https://api.render.com/v1/services/${{ secrets.RENDER_BACKEND_SERVICE_ID }}/deploys" \
          -H "Content-Type: application/json" \
          -d '{}'
```

**Also add to the repository `README.md`** a "Render Setup Checklist" section that includes:

```markdown
## Render Setup Checklist

Before the first production deploy, configure the following in the Render dashboard:

### Backend Web Service
- **Pre-Deploy Command:** `alembic upgrade head`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2`
- **Always On:** enabled
- **Environment Variables:** copy all from `.env.example`, set real values

### Environment Variables to set in Render
- `DATABASE_URL` — Render managed Postgres connection string
- `REDIS_URL` — Render managed Redis connection string
- `JWT_SECRET_KEY` — 64-char random hex (generate with: `openssl rand -hex 32`)
- `RESEND_API_KEY` — from Resend dashboard
- `GOOGLE_API_KEY`, `OPENAI_API_KEY` — from respective dashboards
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET` — from AWS
- `CORS_ORIGINS` — comma-separated list of your Render frontend service URLs
- `ENVIRONMENT` — `production`
```

### Acceptance Criteria

- [ ] `deploy.yml` has the comment block documenting the pre-deploy command location
- [ ] `README.md` has a Render Setup Checklist section
- [ ] The curl command in deploy.yml is unchanged (still triggers Render API)
- [ ] No new GitHub Actions secrets are required by this task

---


## Task 5 — Clean Up Login Pages: One Role Per App

**Branch:** `deploy/T5-login-cleanup`  
**Files touched:**
- `packages/ui/src/LoginForm.tsx` — one prop addition only (see below)
- `frontend/apps/teacher/src/pages/LoginPage.tsx`
- `frontend/apps/student/src/pages/LoginPage.tsx`
- `frontend/apps/parent/src/pages/LoginPage.tsx`
- `frontend/apps/school-admin/src/pages/LoginPage.tsx`
- `frontend/apps/kaihle-admin/src/pages/LoginPage.tsx`

**Do NOT touch:**
- Any `App.tsx` file — routing is already correct
- `packages/ui/src/index.ts` — no changes needed
- Any other part of `LoginForm.tsx` beyond the single prop addition described below

**Read before writing:**
- `docs/design/DESIGN_SYSTEM.md` — full read required. Pay specific attention to role-specific button colors. Teacher = gold only (never green). School Admin and Student = brand-primary green. Parent = gold.
- `packages/ui/src/LoginForm.tsx` — read the full file before touching it. Understand the existing props interface and where the submit button is rendered.
- All five `LoginPage.tsx` files — read before touching any of them.

### Architecture Decision (locked — Option B)

Each app serves exactly one role. Each role has its own production domain. Users arrive at their domain directly — from a bookmark, from the school's welcome email, or via the role-picker on `kaihle.com/login` (Task 6). No cross-app tabs.

| App | Production domain | Post-login URL | logoLabel | buttonClassName |
|---|---|---|---|---|
| `teacher` | `teacher.kaihle.com` | `/teacher/dashboard` | `Teacher Portal` | `bg-brand-gold hover:bg-brand-gold-dark text-white` |
| `school-admin` | `admin.kaihle.com` | `/school-admin/dashboard` | `School Admin Portal` | `bg-brand-primary hover:bg-brand-primary-dark text-white` |
| `student` | `student.kaihle.com` | `/student/dashboard` | `Student Portal` | `bg-brand-primary hover:bg-brand-primary-dark text-white` |
| `parent` | `parent.kaihle.com` | `/parent/dashboard` | `Parent Portal` | `bg-brand-gold hover:bg-brand-gold-dark text-white` |
| `kaihle-admin` | `internal.kaihle.com` | `/kaihle-admin/dashboard` | `Kaihle Admin` | omit — default teal is acceptable for internal tool |

### Step 1 — Add `buttonClassName` prop to `LoginForm.tsx`

The existing submit button in `LoginForm.tsx` is hardcoded to `bg-teal-600 hover:bg-teal-700`. This conflicts with the design system — each role has a specific action color. Add a single optional prop to allow the caller to override the button class.

**Exact change to `LoginForm.tsx`:**

1. Add `buttonClassName?: string` to the `LoginFormProps` interface.
2. In the password form submit button, replace the hardcoded color classes with the prop, falling back to the current default:

```tsx
// Before:
className="w-full bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white font-medium py-2.5 px-4 rounded-lg text-sm transition-colors"

// After:
className={`w-full ${buttonClassName ?? 'bg-teal-600 hover:bg-teal-700'} disabled:opacity-50 text-white font-medium py-2.5 px-4 rounded-lg text-sm transition-colors`}
```

3. Apply the same change to the magic-link submit button (same file — find the "Send login link" button and apply the same pattern).

**No other changes to `LoginForm.tsx`.** Do not touch the form logic, the magic-link flow, the error display, the password toggle, or anything else.

### Step 2 — Update each app's `LoginPage.tsx`

**`apps/teacher/src/pages/LoginPage.tsx` — final form:**
```tsx
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@kaihle/auth';
import { LoginForm } from '@kaihle/ui';

export function LoginPage() {
  const { login, sendMagicLink } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (email: string, password: string) => {
    await login({ email, password });
    navigate('/teacher/dashboard');
  };

  return (
    <LoginForm
      onLogin={handleLogin}
      onMagicLink={sendMagicLink}
      logoLabel="Teacher Portal"
      buttonClassName="bg-brand-gold hover:bg-brand-gold-dark text-white"
    />
  );
}
```

**`apps/school-admin/src/pages/LoginPage.tsx` — final form:**
```tsx
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@kaihle/auth';
import { LoginForm } from '@kaihle/ui';

export function LoginPage() {
  const { login, sendMagicLink } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (email: string, password: string) => {
    await login({ email, password });
    navigate('/school-admin/dashboard');
  };

  return (
    <LoginForm
      onLogin={handleLogin}
      onMagicLink={sendMagicLink}
      logoLabel="School Admin Portal"
      buttonClassName="bg-brand-primary hover:bg-brand-primary-dark text-white"
    />
  );
}
```

**`apps/student/src/pages/LoginPage.tsx` — final form:**
```tsx
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@kaihle/auth';
import { LoginForm } from '@kaihle/ui';

export function LoginPage() {
  const { login, sendMagicLink } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (email: string, password: string) => {
    await login({ email, password });
    navigate('/student/dashboard');
  };

  return (
    <LoginForm
      onLogin={handleLogin}
      onMagicLink={sendMagicLink}
      logoLabel="Student Portal"
      buttonClassName="bg-brand-primary hover:bg-brand-primary-dark text-white"
    />
  );
}
```

**`apps/parent/src/pages/LoginPage.tsx` — final form:**
```tsx
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@kaihle/auth';
import { LoginForm } from '@kaihle/ui';

export function LoginPage() {
  const { login, sendMagicLink } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (email: string, password: string) => {
    await login({ email, password });
    navigate('/parent/dashboard');
  };

  return (
    <LoginForm
      onLogin={handleLogin}
      onMagicLink={sendMagicLink}
      logoLabel="Parent Portal"
      buttonClassName="bg-brand-gold hover:bg-brand-gold-dark text-white"
    />
  );
}
```

**`apps/kaihle-admin/src/pages/LoginPage.tsx`:** Verify `logoLabel="Kaihle Admin"` and post-login navigates to `/kaihle-admin/dashboard`. Do not pass `buttonClassName` — the default teal is acceptable for an internal tool.

### Acceptance Criteria

- [ ] `LoginForm.tsx` has `buttonClassName?: string` prop — no other changes
- [ ] Password submit button uses `buttonClassName` with fallback to `bg-teal-600 hover:bg-teal-700`
- [ ] Magic-link submit button uses the same `buttonClassName` with the same fallback
- [ ] Teacher login page has gold submit button (`bg-brand-gold`)
- [ ] School Admin login page has green submit button (`bg-brand-primary`)
- [ ] Student login page has green submit button (`bg-brand-primary`)
- [ ] Parent login page has gold submit button (`bg-brand-gold`)
- [ ] Kaihle Admin login page unchanged — default teal button
- [ ] Each app navigates only to its own role's dashboard path after login
- [ ] No cross-role navigation in any `LoginPage.tsx`
- [ ] TypeScript compiles without errors (`tsc --noEmit` passes)
- [ ] Existing `LoginForm` tests still pass — `buttonClassName` is additive, no behaviour change

---

## Task 6 — Role-Picker Page on kaihle.com + Navbar Sign In Link

**Branch:** `www/T6-signin-and-role-picker`  
**Executor:** Coding agent  
**Prerequisite:** Render production URLs provisioned and confirmed by Vibhu. Task 5 merged.  
**Repo:** `kaihle-www` — SEPARATE repository (`https://github.com/vibhu-athavaria/kaihle-www`)  
**Stack:** Next.js 14 App Router · TypeScript · Tailwind CSS · Vercel (do NOT move to Render)

**Note to agent:** This task operates on a DIFFERENT repository (`kaihle-www`). Do not touch any files in the `kaihle/` monorepo.

### Confirmed Facts (read from live site and repo)

- Current Navbar: `For Schools` · `How It Works` · `Why Kaihle` · `Pricing` · `About` · **`Apply for Pilot`** (green button, primary CTA)
- **No "Sign In" link exists anywhere on the site** — needs to be added
- `.env.local.example` already has `NEXT_PUBLIC_APP_URL=https://app.kaihle.com`
- `Apply for Pilot` → `/demo` is the primary CTA and must not be touched

### Locked URL Architecture (Option B)

| Role | Production domain | Login URL |
|---|---|---|
| Teacher | `teacher.kaihle.com` | `https://teacher.kaihle.com/login` |
| School Admin | `admin.kaihle.com` | `https://admin.kaihle.com/login` |
| Student | `student.kaihle.com` | `https://student.kaihle.com/login` |
| Parent | `parent.kaihle.com` | `https://parent.kaihle.com/login` |
| Kaihle Admin | `internal.kaihle.com` | private — no website link |

### What to Implement

**Read `components/layout/Navbar.tsx` and `app/layout.tsx` in full before touching anything.**

#### Change 1 — Add env vars to `.env.local.example`

```bash
# Role app URLs — used by the /login role-picker page
NEXT_PUBLIC_TEACHER_URL=https://teacher.kaihle.com
NEXT_PUBLIC_ADMIN_URL=https://admin.kaihle.com
NEXT_PUBLIC_STUDENT_URL=https://student.kaihle.com
NEXT_PUBLIC_PARENT_URL=https://parent.kaihle.com
```

Also update the existing `NEXT_PUBLIC_APP_URL` comment to clarify it is no longer used for Sign In:
```bash
# Legacy — kept for backwards compat. Use role-specific URLs above for Sign In links.
NEXT_PUBLIC_APP_URL=https://teacher.kaihle.com
```

#### Change 2 — Add "Sign In" link to Navbar

In `components/layout/Navbar.tsx`, add a plain text link between "About" and the "Apply for Pilot" button:

```tsx
<Link
  href="/login"
  className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
>
  Sign in
</Link>
```

This links to `/login` on kaihle.com itself — the role-picker page (Change 3 below). It is a Next.js internal link, not an external URL.

On mobile nav (hamburger menu): add "Sign In" as the last nav item before "Apply for Pilot".

#### Change 3 — Create `app/login/page.tsx` (role-picker page)

Create a new page at `app/login/page.tsx`. This is a simple static page — no API calls, no auth logic. It presents four role cards that link out to the correct app domain.

**Before writing any JSX, read `tailwind.config.ts` in full.** Identify the exact token name used for the Fraunces heading font — it may be `font-display`, `font-heading`, `font-fraunces`, or something else. Use whatever token name is actually configured. Do not assume `font-display`.

```tsx
import Link from 'next/link';

// Note: no 'as const' — env var interpolation produces string | undefined,
// which conflicts with TypeScript literal type inference from 'as const'.
// The '?? "#"' fallback prevents href="undefined/login" in local dev
// before .env.local is configured.
const roles = [
  {
    id: 'teacher',
    label: 'Teacher',
    description: 'Access your classes, gap maps, and lesson planner.',
    href: process.env.NEXT_PUBLIC_TEACHER_URL
      ? `${process.env.NEXT_PUBLIC_TEACHER_URL}/login`
      : '#',
    dot: '#c9932a',  // brand-gold — Teacher action color per DESIGN_SYSTEM.md §5.3
  },
  {
    id: 'school-admin',
    label: 'School Admin',
    description: 'Manage your school, users, classes, and analytics.',
    href: process.env.NEXT_PUBLIC_ADMIN_URL
      ? `${process.env.NEXT_PUBLIC_ADMIN_URL}/login`
      : '#',
    dot: '#1a5c38',  // brand-primary — School Admin action color per DESIGN_SYSTEM.md §5.2
  },
  {
    id: 'student',
    label: 'Student',
    description: 'View your study plans, progress, and assessments.',
    href: process.env.NEXT_PUBLIC_STUDENT_URL
      ? `${process.env.NEXT_PUBLIC_STUDENT_URL}/login`
      : '#',
    dot: '#1a5c38',  // brand-primary — Student action color per DESIGN_SYSTEM.md §5.4
  },
  {
    id: 'parent',
    label: 'Parent',
    description: "See your child's progress and learning reports.",
    href: process.env.NEXT_PUBLIC_PARENT_URL
      ? `${process.env.NEXT_PUBLIC_PARENT_URL}/login`
      : '#',
    dot: '#c9932a',  // brand-gold — Parent action color per DESIGN_SYSTEM.md §5.5
  },
];

export default function LoginPage() {
  return (
    <main className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-16">
      <div className="max-w-md w-full">
        <div className="text-center mb-10">
          {/* Reuse the existing Kaihle logo mark component from the site — do not invent a new one.
              Read app/layout.tsx and components/layout/Navbar.tsx to find how the logo is rendered,
              then reuse the same pattern here. */}
          <h1 className="[USE_HEADING_FONT_TOKEN_FROM_TAILWIND_CONFIG] text-2xl font-bold text-gray-900 mt-4">
            Sign in to Kaihle
          </h1>
          <p className="text-sm text-gray-500 mt-2">Choose your role to continue.</p>
        </div>

        <div className="flex flex-col gap-3">
          {roles.map((role) => (
            <a
              key={role.id}
              href={role.href}
              className="flex items-center gap-4 bg-white border border-gray-200 rounded-xl px-5 py-4 hover:border-gray-400 transition-colors group"
            >
              <span
                className="w-3 h-3 rounded-full flex-shrink-0"
                style={{ background: role.dot }}
              />
              <div className="flex-1">
                <div className="text-sm font-semibold text-gray-900 group-hover:text-gray-700">
                  {role.label}
                </div>
                <div className="text-xs text-gray-500 mt-0.5">{role.description}</div>
              </div>
              <span className="text-gray-300 group-hover:text-gray-500 text-lg" aria-hidden="true">→</span>
            </a>
          ))}
        </div>

        <p className="text-center text-xs text-gray-400 mt-8">
          Don't have an account?{' '}
          <Link href="/demo" className="text-gray-600 hover:text-gray-900 underline">
            Apply for Pilot
          </Link>
        </p>
      </div>
    </main>
  );
}
```

**Replace `[USE_HEADING_FONT_TOKEN_FROM_TAILWIND_CONFIG]`** with the actual Tailwind font token for Fraunces that you find in `tailwind.config.ts`. Do not leave the placeholder in the final code.

**Note on `<a href>` vs `<Link>`:** Each role card uses a plain `<a href>` — not Next.js `<Link>` — because the destination is an external domain. Next.js `<Link>` is for internal routes within kaihle.com only.

**Note on hover state:** No `hover:shadow-sm` or any drop shadow on hover. The design system bans shadows (`DESIGN_SYSTEM.md §11: ❌ No drop shadows`). Border color change on hover (`hover:border-gray-400`) is sufficient affordance.

#### Change 4 — Add page metadata

In `app/login/page.tsx`, export metadata:

```tsx
export const metadata = {
  title: 'Sign In — Kaihle',
  description: 'Sign in to your Kaihle portal.',
  robots: { index: false },   // role-picker doesn't need to be indexed
};
```

### Acceptance Criteria

- [ ] Navbar shows "Sign In" text link between "About" and "Apply for Pilot"
- [ ] "Sign In" links to `/login` (internal Next.js route, not hardcoded external URL)
- [ ] `kaihle.com/login` renders the role-picker page with four role cards
- [ ] Each role card `href` is env-driven — no hardcoded production URLs in source code
- [ ] When env var is unset, card `href` falls back to `'#'` — not `"undefined/login"`
- [ ] Role card hover state uses `hover:border-gray-400` only — no `hover:shadow-sm` or any drop shadow
- [ ] Heading font token matches what is configured in `tailwind.config.ts` — no placeholder left in code
- [ ] `→` arrow has `aria-hidden="true"`
- [ ] Mobile nav includes "Sign In"
- [ ] `Apply for Pilot` button and `/demo` page are untouched
- [ ] `.env.local.example` has all four role URL vars with comments
- [ ] Page is excluded from search indexing (`robots: { index: false }`)
- [ ] `next build` passes with no TypeScript errors
- [ ] Vercel preview deployment shows updated navbar and working role-picker page

---

## Render Service Naming (reference for Vibhu when provisioning)

| Service | Type | Custom domain |
|---|---|---|
| `kaihle-backend` | Web Service (Always On) | `api.kaihle.com` |
| `kaihle-celery` | Background Worker | none |
| `kaihle-teacher` | Static Site | `teacher.kaihle.com` |
| `kaihle-admin` | Static Site | `admin.kaihle.com` |
| `kaihle-student` | Static Site | `student.kaihle.com` |
| `kaihle-parent` | Static Site | `parent.kaihle.com` |
| `kaihle-internal` | Static Site | `internal.kaihle.com` |
| `kaihle-db` | Managed PostgreSQL | — |
| `kaihle-redis` | Managed Redis | — |

**CORS_ORIGINS to set on backend:**
```
https://teacher.kaihle.com,https://admin.kaihle.com,https://student.kaihle.com,https://parent.kaihle.com,https://internal.kaihle.com
```

---

## Merge Strategy (present to Vibhu after all PRs are open)

| Order | PR | Repo | Depends on | Notes |
|---|---|---|---|---|
| 1 | T3 (backend Dockerfile) | `kaihle` | nothing | Lowest risk — build only |
| 2 | T2 (CORS config) | `kaihle` | nothing | Backend only |
| 3 | T4 (deploy.yml) | `kaihle` | nothing | CI only, no runtime impact |
| 4 | T1 (frontend Dockerfiles) | `kaihle` | nothing | Verify all 5 apps build |
| 5 | T5 (login cleanup) | `kaihle` | nothing | Verify login flow per app |
| 6 | T6 (role-picker + nav) | `kaihle-www` | T5 merged + Render URLs live | External repo, Vercel deploy |

**Human actions required before T6:**
- Provision all Render services per the table above
- Set `CORS_ORIGINS` in Render dashboard
- Set `alembic upgrade head` as pre-deploy command on backend service
- Configure custom domains in Render and point DNS records
- Confirm all five app URLs are live before setting env vars in Vercel

---

## What the Agent Must NOT Do

- Do not merge any PR — merging is always a human action
- Do not run `docker compose down -v` or any command that destroys postgres_data
- Do not modify `Dockerfile.dev` files — they are correct for local dev
- Do not remove localhost origins from CORS — they are needed for local dev
- Do not hardcode production URLs anywhere — use environment variables
- Do not invent Render service IDs or API keys — they come from Vibhu's Render dashboard
- Do not touch `App.tsx` routing in any app — routing is already correct
- Do not use Next.js `<Link>` for external domain hrefs in the role-picker page
