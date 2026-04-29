# AI Reality Check

AI Reality Check is an MVP accountability platform for tracking AI failures and reality-checking public claims against reported outcomes. This bootstrap task sets up the initial monorepo structure, a placeholder Next.js frontend, and a minimal FastAPI backend.

## Repository Layout

- `frontend/` - Next.js app router project with lint, test, and build commands.
- `backend/` - FastAPI service with pytest and Ruff configuration.
- `infra/` - Placeholder infrastructure docs for Supabase and scheduled jobs.
- `.env.example` - Shared environment template for local development.

## Prerequisites

- Node.js 23+
- npm 11+
- Python 3.13+
- `uv` 0.9+

## Local Setup

1. Copy environment variables:

   ```bash
   cp .env.example .env
   ```

2. Install frontend dependencies:

   ```bash
   cd frontend
   npm install
   ```

3. Install backend dependencies:

   ```bash
   cd backend
   UV_CACHE_DIR=../.uv-cache uv sync --all-groups
   ```

## Run Locally

### Frontend

```bash
cd frontend
npm run dev
```

The placeholder UI is available at `http://localhost:3000`.

### Backend

```bash
cd backend
UV_CACHE_DIR=../.uv-cache uv run uvicorn app.main:app --reload
```

The health endpoint is available at `http://127.0.0.1:8000/health`.

## Quality Checks

### Frontend

```bash
cd frontend
npm run format
npm run lint
npm test
npm run build
```

### Backend

```bash
cd backend
UV_CACHE_DIR=../.uv-cache uv run ruff format --check .
UV_CACHE_DIR=../.uv-cache uv run ruff check .
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 UV_CACHE_DIR=../.uv-cache uv run pytest -q
```

## Continuous Integration

GitHub Actions runs:

- frontend lint
- frontend tests
- frontend build
- backend Ruff format check
- backend Ruff lint
- backend pytest

Any regression in those checks will fail CI.
