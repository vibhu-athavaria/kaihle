# Kaihle

An AI-powered adaptive learning platform for Indonesian students.

## Project Structure

```
kaihle/
├── backend/           # FastAPI backend
│   └── app/          # Application code
├── frontend/         # React monorepo
│   ├── apps/        # Teacher, Student, Parent apps
│   └── packages/    # Shared UI components and utilities
└── docs/           # Documentation
```

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- pnpm
- PostgreSQL 15+
- Redis 7+

### Backend Setup

```bash
cd backend
cp .env.example .env  # Configure your environment variables
uv pip install -e .
uvicorn app.main:app --reload
```

### Frontend Setup

```bash
cd frontend
pnpm install
pnpm dev:teacher  # Start teacher app on port 3001
pnpm dev:student  # Start student app on port 3002
pnpm dev:parent   # Start parent app on port 3003
```

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, Alembic, PostgreSQL
- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS
- **Task Queue**: Celery + Redis
- **AI**: OpenAI, Anthropic, Google Generative AI

## License

Proprietary — All rights reserved.
