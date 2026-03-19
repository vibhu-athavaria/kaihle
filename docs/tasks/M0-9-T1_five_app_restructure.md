# M0-9-T1 — Five-App Frontend Restructure
**Milestone:** M0 — Foundations
**Epic:** M0-9 — Architecture Corrections and Spec Alignment
**Task ID:** M0-9-T1
**Depends on:** M0-8-T4 (shared UI components must exist before new apps can import them)
**Blocks:** M0-9-T2, M0-9-T3 (migration tasks need the new app scaffolds to exist first)
**Estimated effort:** 3–4 hours

---

## Context

The v1.0 architecture used three Vite apps (`apps/student`, `apps/teacher`, `apps/parent`)
and placed School Admin and Kaihle Admin pages inside `apps/teacher` as subdirectories.
This violated role isolation, weakened security boundaries, and caused design drift because
admin pages inherited teacher-specific Tailwind tokens and layout components.

This task creates two new fully scaffolded Vite apps — `apps/school-admin` and
`apps/kaihle-admin` — so that M0-9-T2 and M0-9-T3 can migrate the existing pages into
their correct homes. It also updates Docker Compose, CI/CD, and the pnpm workspace to
recognise all five apps.

Read `CONSTITUTION.md` §3 (Repository Structure), §6 (Role → App → Route Mapping),
and `docs/design/DESIGN_SYSTEM.md` §5.1 (Kaihle Admin) and §5.2 (School Admin) before
writing any code.

---

## User Story

As a developer, I want two fully configured frontend apps — one for School Admin and one
for Kaihle Admin — so that role-specific pages can live in isolated, independently
deployable apps with the correct design tokens and layout shells.

---

## Files to Create

```
frontend/apps/school-admin/
  index.html
  package.json
  vite.config.ts
  tsconfig.json
  tsconfig.node.json
  tailwind.config.js
  src/
    main.tsx
    App.tsx
    index.css
    pages/
      LoginPage.tsx        ← placeholder, replaced by M0-9-T2
    tests/
      .gitkeep

frontend/apps/kaihle-admin/
  index.html
  package.json
  vite.config.ts
  tsconfig.json
  tsconfig.node.json
  tailwind.config.js
  src/
    main.tsx
    App.tsx
    index.css
    pages/
      LoginPage.tsx        ← placeholder, replaced by M0-9-T3
    tests/
      .gitkeep
```

## Files to Modify

```
frontend/pnpm-workspace.yaml         ← add apps/school-admin and apps/kaihle-admin
docker-compose.yml                   ← add frontend-school-admin and frontend-kaihle-admin services
.github/workflows/ci.yml             ← add lint-frontend-school-admin and lint-frontend-kaihle-admin jobs
.github/workflows/deploy.yml         ← add deploy-school-admin and deploy-kaihle-admin jobs
```

---

## What To Build

### `apps/school-admin/package.json`

```json
{
  "name": "@kaihle/school-admin",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "vite --port 3004",
    "build": "tsc && vite build",
    "preview": "vite preview --port 3004",
    "test": "jest",
    "lint": "eslint src --ext ts,tsx"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.0",
    "@tanstack/react-query": "^5.0.0",
    "zustand": "^4.4.0",
    "axios": "^1.6.0",
    "react-hook-form": "^7.49.0",
    "zod": "^3.22.0",
    "@kaihle/ui": "workspace:*",
    "@kaihle/auth": "workspace:*",
    "@kaihle/api-client": "workspace:*",
    "@kaihle/types": "workspace:*"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.0",
    "vite": "^5.0.0",
    "typescript": "^5.3.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0"
  }
}
```

Use the identical structure for `apps/kaihle-admin/package.json`, changing only `name`
to `@kaihle/kaihle-admin`.

### `apps/school-admin/tailwind.config.js`

```js
// Extends the shared base config from packages/ui so all brand-* and
// role-school-admin-* tokens are available without duplication.
import baseConfig from '@kaihle/ui/tailwind.config.js'

export default {
  ...baseConfig,
  content: [
    './src/**/*.{ts,tsx}',
    '../../packages/ui/src/**/*.{ts,tsx}',
  ],
}
```

Use the identical pattern for `apps/kaihle-admin/tailwind.config.js`.

### `apps/school-admin/src/index.css`

```css
/* Design system: docs/design/DESIGN_SYSTEM.md */
@import url('https://fonts.googleapis.com/css2?family=Nunito:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,400&family=Fraunces:ital,opsz,wght@0,9..144,600;0,9..144,700;1,9..144,400;1,9..144,600&family=Inter:wght@400;500;600;700&family=Lora:ital,wght@0,600;1,400&display=swap');

@tailwind base;
@tailwind components;
@tailwind utilities;
```

Use the identical CSS for `apps/kaihle-admin/src/index.css`. Kaihle Admin only uses
Inter, but importing all fonts here is harmless and keeps the pattern consistent across
all five apps.

### `apps/school-admin/src/App.tsx`

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { PrivateRoute, RoleRoute, PasswordSetupRoute } from '@kaihle/auth'
import { LoginPage } from './pages/LoginPage'

// School Admin app — SCHOOL_ADMIN role only.
// All role-specific pages are added here by M0-9-T2.
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/school-admin/setup-password"
          element={
            <PrivateRoute>
              {/* PasswordSetupPage added by M0-9-T4 */}
              <div className="p-8 text-gray-500">Password setup — coming in M0-9-T4</div>
            </PrivateRoute>
          }
        />
        <Route
          path="/school-admin/*"
          element={
            <PrivateRoute>
              <PasswordSetupRoute>
                <RoleRoute roles={['SCHOOL_ADMIN']}>
                  {/* School admin pages added by M0-9-T2 */}
                  <div className="p-8 text-gray-500">School admin dashboard — coming in M0-9-T2</div>
                </RoleRoute>
              </PasswordSetupRoute>
            </PrivateRoute>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
```

Use the same structure for `apps/kaihle-admin/src/App.tsx`, changing the path prefix
to `/kaihle-admin`, the role to `KAIHLE_ADMIN`, and the placeholder text accordingly.

### `apps/school-admin/src/pages/LoginPage.tsx`

This is a thin wrapper around the shared `LoginForm` from `packages/ui`. After
successful login, redirect to `/school-admin/setup-password` (if first login) or
`/school-admin/dashboard`. The routing logic is handled by `PasswordSetupRoute` and
`OnboardingRoute` guards in `packages/auth` — this page just calls `login()` and
navigates to the role root.

```tsx
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@kaihle/auth'
import { LoginForm } from '@kaihle/ui'

export function LoginPage() {
  const { login, sendMagicLink } = useAuth()
  const navigate = useNavigate()

  const handleLogin = async (email: string, password: string) => {
    await login({ email, password })
    navigate('/school-admin/dashboard')
    // PasswordSetupRoute guard will intercept and redirect to setup-password
    // if the JWT has scope: "password_setup"
  }

  return (
    <LoginForm
      onLogin={handleLogin}
      onMagicLink={sendMagicLink}
      logoLabel="School Admin Portal"
    />
  )
}
```

Apply the same pattern for `apps/kaihle-admin/src/pages/LoginPage.tsx` with
`logoLabel="Kaihle Admin"` and navigation to `/kaihle-admin/dashboard`.

### Docker Compose additions

Add these two services to `docker-compose.yml` after the existing `frontend-parent`
service:

```yaml
  frontend-school-admin:
    build:
      context: ./frontend
      dockerfile: apps/school-admin/Dockerfile.dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "3004:3004"
    environment:
      - VITE_API_URL=http://localhost:8000
    depends_on:
      - backend
    command: pnpm dev:school-admin

  frontend-kaihle-admin:
    build:
      context: ./frontend
      dockerfile: apps/kaihle-admin/Dockerfile.dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "3005:3005"
    environment:
      - VITE_API_URL=http://localhost:8000
    depends_on:
      - backend
    command: pnpm dev:kaihle-admin
```

Both services use the same Dockerfile.dev pattern as the existing three apps. Add the
corresponding `dev:school-admin` and `dev:kaihle-admin` scripts to
`frontend/package.json`.

### CI/CD additions

In `.github/workflows/ci.yml`, add lint and unit test jobs for the two new apps,
following the identical pattern of the existing `lint-frontend` job but with
`working-directory: frontend/apps/school-admin` and `frontend/apps/kaihle-admin`
respectively.

In `.github/workflows/deploy.yml`, add deploy jobs for the two new Render static
sites, following the existing deploy-frontend pattern. The Render service IDs will be
set as GitHub secrets `RENDER_SCHOOL_ADMIN_SERVICE_ID` and
`RENDER_KAIHLE_ADMIN_SERVICE_ID` in M6 when Render services are created.

### pnpm workspace addition

In `frontend/pnpm-workspace.yaml`, add:

```yaml
packages:
  - 'apps/*'          # already covers new apps via glob — verify this is present
  - 'packages/*'
```

If the workspace file uses explicit paths instead of a glob, add
`'apps/school-admin'` and `'apps/kaihle-admin'` explicitly.

---

## Acceptance Criteria

- `pnpm dev:school-admin` starts the school admin app on port 3004 with no console errors
- `pnpm dev:kaihle-admin` starts the kaihle admin app on port 3005 with no console errors
- `docker-compose up frontend-school-admin` serves the school admin app at `http://localhost:3004`
- `docker-compose up frontend-kaihle-admin` serves the kaihle admin app at `http://localhost:3005`
- `bg-brand-primary` resolves to `#1a5c38` in both new apps (confirms Tailwind config extension working)
- `font-fraunces` renders correctly in school-admin app headings; Inter renders in kaihle-admin (no Fraunces)
- Neither new app imports anything from `apps/teacher/src/` — verified by `grep -r "apps/teacher" apps/school-admin apps/kaihle-admin` returning zero results
- CI `lint-frontend-school-admin` and `lint-frontend-kaihle-admin` jobs appear in GitHub Actions workflow run
- `tsc --noEmit` passes in both new apps

---

## Dependencies

M0-8-T4 must be complete — `packages/ui` must export `LoginForm`, `AuthLayout`, and
core components before this app can import them.

## Output (What M0-9-T2 and M0-9-T3 Can Use)

- `apps/school-admin/` fully scaffolded with routing, Tailwind, TypeScript, and Docker Compose entry
- `apps/kaihle-admin/` fully scaffolded with routing, Tailwind, TypeScript, and Docker Compose entry
- `pnpm workspace` recognises both new apps
- CI/CD has placeholder jobs for both apps ready to receive real tests
