# M0-1-T1 — Initialise Monorepo
**Milestone:** M0 — Foundations
**Epic:** M0-1 — Repository & Project Setup
**Task ID:** M0-1-T1
**Mode:** Code (MiniMax)
**Estimated effort:** 2–3 hours

---

## Context

This is the first task in the project. You are setting up the monorepo from scratch. There is no existing code. The output of this task is the skeleton that every subsequent task builds on.

Read CONSTITUTION.md before starting. Pay particular attention to §2 (locked tech stack) and §3 (repository structure).

---

## User Story

As a developer, I want a clean monorepo structure with consistent tooling so I can start writing features without fighting configuration.

---

## What To Build

### Root Structure
Create a root directory `/kaihle` with the following layout:

```
/kaihle
  /backend
  /frontend
  /docs
  .gitignore
  .env.example
  README.md
  docker-compose.yml          ← placeholder, fully implemented in M0-1-T2
```

---

### Backend Setup (`/backend`)

Package manager: `uv` (preferred) or `pip`.

**`/backend/pyproject.toml`** — define all dependencies:
```toml
[project]
name = "kaihle-backend"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "sqlalchemy[asyncio]>=2.0.0",
  "alembic>=1.13.0",
  "asyncpg>=0.29.0",
  "pydantic>=2.0.0",
  "pydantic-settings>=2.0.0",
  "python-jose[cryptography]>=3.3.0",
  "passlib[bcrypt]>=1.7.4",
  "httpx>=0.27.0",
  "celery[redis]>=5.3.0",
  "redis>=5.0.0",
  "structlog>=24.0.0",
  "resend>=0.8.0",
  "pgvector>=0.3.0",
  "tiktoken>=0.7.0",
  "pdfplumber>=0.11.0",
  "google-generativeai>=0.7.0",
  "openai>=1.40.0",
  "anthropic>=0.34.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0.0",
  "pytest-asyncio>=0.23.0",
  "pytest-cov>=5.0.0",
  "ruff>=0.5.0",
  "mypy>=1.10.0",
]
```

**`/backend/app/__init__.py`** — empty

**`/backend/app/main.py`** — minimal FastAPI app:
```python
from fastapi import FastAPI

app = FastAPI(title="Kaihle API", version="0.1.0")

@app.get("/health")
async def health():
    return {"status": "ok"}
```

**`/backend/app/core/__init__.py`** — empty

**`/backend/app/core/config.py`** — Pydantic Settings:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    resend_api_key: str
    from_email: str = "no-reply@kaihle.ai"
    google_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    youtube_data_api_key: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_s3_bucket: str = "kaihle-assets"
    aws_region: str = "ap-southeast-1"
    celery_broker_url: str
    celery_result_backend: str
    environment: str = "development"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"

settings = Settings()
```

**Create empty `__init__.py` files** in:
- `/backend/app/api/`
- `/backend/app/api/v1/`
- `/backend/app/api/v1/routes/`
- `/backend/app/models/`
- `/backend/app/schemas/`
- `/backend/app/services/`
- `/backend/app/ai/`
- `/backend/app/ai/providers/`
- `/backend/app/ai/rag/`
- `/backend/app/ai/prompts/`
- `/backend/app/tasks/`
- `/backend/app/tests/`
- `/backend/app/tests/unit/`
- `/backend/app/tests/integration/`
- `/backend/app/tests/e2e/`

**`/backend/pytest.ini`**:
```ini
[pytest]
asyncio_mode = auto
testpaths = app/tests
```

**`/backend/.ruff.toml`**:
```toml
line-length = 100
target-version = "py312"

[lint]
select = ["E", "F", "I", "UP"]
```

**`/backend/mypy.ini`**:
```ini
[mypy]
python_version = 3.12
strict = true
ignore_missing_imports = true
```

---

### Frontend Setup (`/frontend`)

Package manager: `pnpm` with workspaces.

**`/frontend/package.json`** — root workspace:
```json
{
  "name": "kaihle-frontend",
  "private": true,
  "workspaces": [
    "apps/*",
    "packages/*"
  ],
  "scripts": {
    "dev:teacher": "pnpm --filter teacher dev",
    "dev:student": "pnpm --filter student dev",
    "dev:parent": "pnpm --filter parent dev",
    "build": "pnpm --filter './apps/*' build",
    "lint": "pnpm --filter './apps/*' --filter './packages/*' lint",
    "test": "pnpm --filter './apps/*' test"
  },
  "devDependencies": {
    "prettier": "^3.3.0",
    "eslint": "^9.0.0",
    "typescript": "^5.5.0"
  }
}
```

**Create Vite + React + TypeScript app for each of the three apps:**

For `/frontend/apps/teacher/`, `/frontend/apps/student/`, `/frontend/apps/parent/`:

Each app's `package.json`:
```json
{
  "name": "teacher",
  "private": true,
  "version": "0.1.0",
  "scripts": {
    "dev": "vite --port 3001",
    "build": "tsc && vite build",
    "lint": "eslint src",
    "test": "jest"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.26.0",
    "@tanstack/react-query": "^5.0.0",
    "zustand": "^4.5.0",
    "axios": "^1.7.0",
    "react-hook-form": "^7.52.0",
    "zod": "^3.23.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.4.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "jest": "^29.0.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.0.0"
  }
}
```
(Adjust port: teacher=3001, student=3002, parent=3003)

Each app's `vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 3001 }  // 3002 for student, 3003 for parent
})
```

Each app's `src/main.tsx`:
```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```

Each app's `src/App.tsx` (minimal placeholder):
```typescript
export default function App() {
  return <div className="p-4">Kaihle — Teacher App</div>
  // Change label per app
}
```

Each app's `tailwind.config.js`:
```javascript
export default {
  content: ['./src/**/*.{ts,tsx}'],
  theme: { extend: {} },
  plugins: [],
}
```

Each app's `tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true
  },
  "include": ["src"]
}
```

**Create empty package stubs** for:
- `/frontend/packages/ui/`
- `/frontend/packages/api-client/`
- `/frontend/packages/auth/`
- `/frontend/packages/types/`

Each with a minimal `package.json`:
```json
{
  "name": "@kaihle/ui",
  "version": "0.1.0",
  "main": "src/index.ts"
}
```

---

### Root Files

**`.gitignore`:**
```
# Python
__pycache__/
*.pyc
.venv/
.env
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Node
node_modules/
dist/
.cache/

# IDE
.vscode/
.idea/

# Misc
*.DS_Store
```

**`.env.example`:**
```bash
# Database
DATABASE_URL=postgresql+asyncpg://kaihle:kaihle@localhost:5432/kaihle
REDIS_URL=redis://localhost:6379/0

# Auth
JWT_SECRET_KEY=changeme-replace-with-64-char-hex-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Email
RESEND_API_KEY=re_xxxxxxxxxxxx
FROM_EMAIL=no-reply@kaihle.ai

# LLM Providers
GOOGLE_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
YOUTUBE_DATA_API_KEY=

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Storage
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_S3_BUCKET=kaihle-assets
AWS_REGION=ap-southeast-1

# App
ENVIRONMENT=development
LOG_LEVEL=INFO
```

**Pre-commit hooks** — `/.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        args: [--ignore-missing-imports]
  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v4.0.0
    hooks:
      - id: prettier
        types_or: [ts, tsx, json, css]
```

---

## Files To Create (Summary)

```
/kaihle/.gitignore
/kaihle/.env.example
/kaihle/.pre-commit-config.yaml
/kaihle/README.md
/kaihle/backend/pyproject.toml
/kaihle/backend/pytest.ini
/kaihle/backend/.ruff.toml
/kaihle/backend/mypy.ini
/kaihle/backend/app/__init__.py
/kaihle/backend/app/main.py
/kaihle/backend/app/core/__init__.py
/kaihle/backend/app/core/config.py
/kaihle/backend/app/api/__init__.py
/kaihle/backend/app/api/v1/__init__.py
/kaihle/backend/app/api/v1/routes/__init__.py
/kaihle/backend/app/models/__init__.py
/kaihle/backend/app/schemas/__init__.py
/kaihle/backend/app/services/__init__.py
/kaihle/backend/app/ai/__init__.py
/kaihle/backend/app/ai/providers/__init__.py
/kaihle/backend/app/ai/rag/__init__.py
/kaihle/backend/app/tasks/__init__.py
/kaihle/backend/app/tests/__init__.py
/kaihle/backend/app/tests/unit/__init__.py
/kaihle/backend/app/tests/integration/__init__.py
/kaihle/backend/app/tests/e2e/__init__.py
/kaihle/frontend/package.json
/kaihle/frontend/apps/teacher/package.json + vite.config.ts + tsconfig.json + tailwind.config.js + src/main.tsx + src/App.tsx + src/index.css
/kaihle/frontend/apps/student/  (same structure, port 3002)
/kaihle/frontend/apps/parent/   (same structure, port 3003)
/kaihle/frontend/packages/ui/package.json
/kaihle/frontend/packages/api-client/package.json
/kaihle/frontend/packages/auth/package.json
/kaihle/frontend/packages/types/package.json
```

---

## Acceptance Criteria

- [ ] `cd backend && uvicorn app.main:app --reload` starts without errors
- [ ] `GET http://localhost:8000/health` returns `{"status": "ok"}`
- [ ] `cd frontend && pnpm install` completes without errors
- [ ] `pnpm dev:teacher` starts the teacher app at `http://localhost:3001` with no console errors
- [ ] `ruff check .` passes with zero errors on the backend
- [ ] `mypy .` passes with zero errors on the backend
- [ ] `prettier --check .` passes on the frontend
- [ ] No `.env` file committed — only `.env.example`

---

## Dependencies

- None — this is the first task

## Output (What Next Tasks Can Use)

- Full monorepo skeleton at `/kaihle/`
- `app/core/config.py` — all subsequent backend tasks import `settings` from here
- Three frontend apps bootable with `pnpm dev:*`
- All package directories exist for M0-3-T4 (auth package) and later tasks
