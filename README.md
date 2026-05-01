# AI Reality Check

AI Reality Check is an accountability product for tracking AI failures and reality-checking public claims against reported outcomes. The current codebase includes a working public feed, incident detail view, ingestion and enrichment workflows, claim matching, and a lightweight admin review surface.

## Current Product Status

The repository now supports a functional end-to-end MVP slice:

- public incident feed with category and company filters
- incident detail view with linked sources
- optional claim-vs-reality blocks
- daily RSS ingestion and historical backfill workflows
- manual review queue for approving and correcting incidents

It is not yet a full launch-ready MVP. The main remaining gaps are review audit history plus broader launch-readiness coverage and operations hardening. The canonical product docs now live in four files: `docs/product/mvp.md`, `docs/product/daily-runner.md`, `docs/product/prod-spec.md`, and `docs/product/database-schema.md`.

## Repository Layout

- `frontend/` - Vite + React + TypeScript project with lint, test, and build commands.
- `backend/` - FastAPI service with pytest and Ruff configuration.
- `infra/` - Supabase schema and scheduled-job runbooks.
- `docs/product/` - four canonical product docs covering MVP, daily runner operations, product behavior, and readable schema docs.
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

The backend now expects a PostgreSQL `DATABASE_URL`. Point it at a local PostgreSQL database before starting the API. On first connection, the repository bootstraps the core tables, but it does not auto-seed or re-seed incident data when tables are empty.

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

## Launch Readiness Evaluation

Run the seed gold-sample evaluation locally with:

```bash
cd backend
./.venv/bin/python -m app.evals.launch_readiness
```

For the full backend verification path, the evaluation is also covered by:

```bash
cd backend
./.venv/bin/python -m pytest -q tests/test_launch_readiness_eval.py
```

## Product Surface

### Public UI

- chronological incident feed
- category and company filters
- claim-vs-reality module when a reviewed match exists
- detail panel with source links

### Backend Workflows

- PostgreSQL-backed repository for local development
- RSS ingestion with dedupe plus `pending_review` / `pending_llm_review` persistence
- enrichment and heuristic claim matching
- primary LLM review with strict structured output, taxonomy-bound categories, severity suggestion, and approval gating
- resumable historical backfill with checkpoint and audit files
- daily ingestion orchestration with retry and run metrics
- CSV claim import with `python -m app.scripts.import_claims_csv /path/to/claims.csv --dry-run`
- incident daily runner commands documented in `docs/product/daily-runner.md`
- canonical operator research prompt for ChatGPT Deep Research / Gemini Deep Research in `backend/app/services/case_search_prompt.py`

### Admin Review

- shared-secret protected admin queue
- editor overrides for status, company, final severity, summary, categories, and claim match fields
- model-suggested severity, confidence, reasoning, and high-risk flags visible during review

## Notes

- The review taxonomy is fixed in code and currently includes `Autonomous Systems`, `Hallucinations`, `Job Automation Fails`, `Missed Timelines`, `Model Governance`, and `Privacy/Security`.
- Model-suggested severity is stored separately from final `severity_score`; a `null` suggestion is valid for rejected or unresolved incidents.

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
