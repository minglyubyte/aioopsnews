# AI Reality Check

AI Reality Check is an accountability product for tracking AI failures and reality-checking public claims against reported outcomes. The current codebase includes a working public feed, incident detail view, ingestion and enrichment workflows, claim matching, and a lightweight admin review surface.

## Current Product Status

The repository now supports a functional end-to-end MVP slice:

- public incident feed with category and company filters
- incident detail view with linked sources
- optional claim-vs-reality blocks
- daily RSS ingestion and historical backfill workflows
- manual review queue for approving and correcting incidents

It is not yet a full launch-ready MVP. The main remaining gaps are review audit history plus launch-readiness evaluation docs and metrics. See `docs/product/mvp-status.md` and `docs/product/mvp-launch-checklist.md`.

## Repository Layout

- `frontend/` - Vite + React + TypeScript project with lint, test, and build commands.
- `backend/` - FastAPI service with pytest and Ruff configuration.
- `infra/` - Supabase schema and scheduled-job runbooks.
- `docs/product/` - product decisions, MVP status, and launch checklist.
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

   Set `ADMIN_API_TOKEN` in `.env` before using the admin review surface.

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

The backend defaults to a local SQLite database at `backend/data/ai_reality_check.db` for the read API. If the file does not exist yet, the app bootstraps a small reviewed incident dataset automatically.

## Run Locally

### Frontend

```bash
cd frontend
npm run dev
```

The app is available at `http://localhost:5173`.

### Backend

```bash
cd backend
UV_CACHE_DIR=../.uv-cache uv run uvicorn app.main:app --reload
```

The health endpoint is available at `http://127.0.0.1:8000/health`.

Key API endpoints:

- `GET /incidents`
- `GET /incidents/{id}`
- `GET /filters`
- `GET /admin/incidents`
- `PATCH /admin/incidents/{id}`

Admin endpoints require the `X-Admin-Token` header to match `ADMIN_API_TOKEN`.

## Product Surface

### Public UI

- chronological incident feed
- category and company filters
- claim-vs-reality module when a reviewed match exists
- detail panel with source links

### Backend Workflows

- SQLite-backed repository for local development
- RSS ingestion with dedupe and `pending_review` persistence
- enrichment and heuristic claim matching
- resumable historical backfill with checkpoint and audit files
- daily ingestion orchestration with retry and run metrics

### Admin Review

- shared-secret protected admin queue
- editor overrides for status, company, severity, summary, categories, and claim match fields

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
