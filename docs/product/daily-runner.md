# Daily Runner

## Purpose

This document describes the operational daily runner workflow for incident ingestion and review.

The main entrypoint is the all-in-one script:

- [run_incident_csv_workflow.py](/Users/leo/Desktop/AI_Oops/backend/app/scripts/run_incident_csv_workflow.py)

This script is the workflow body. It is not itself a scheduler. To run it every day, wrap it in cron, GitHub Actions scheduled jobs, Supabase scheduled jobs, or another deployment scheduler.

## Required Environment

The runner expects:

- `DATABASE_URL`
- `OPENAI_API_KEY`
- `DEEPSEEK_API_KEY`

It also uses the configured models from app settings:

- primary review model: `gpt-5.4-mini`
- escalation review model: `gpt-5.2`
- embedding model: `text-embedding-3-small`

## Core State Flow

The daily runner moves incidents through these states:

1. CSV import creates incidents in `pending_llm_review`
2. primary review returns legitimacy plus severity suggestion
3. low-risk incidents may become `approved`
4. ambiguous incidents may become `pending_llm_escalation`
5. serious but otherwise clear incidents become `pending_editor_review`
6. approved incidents run duplicate review
7. still-approved incidents run translation
8. only `approved` incidents appear in the public feed

## All-In-One Command

Run the full workflow from the backend directory:

```bash
cd /Users/leo/Desktop/AI_Oops/backend
UV_CACHE_DIR=../.uv-cache uv run python -m app.scripts.run_incident_csv_workflow
```

By default this does all of the following:

- scans the inbox directory for incident CSV files
- validates and imports them
- archives successfully imported CSV files
- submits primary review batches for unbatched incidents
- reconciles any batches that are already completed

## Wait For Batches In One Run

To run the full workflow and keep polling until newly submitted batches complete:

```bash
cd /Users/leo/Desktop/AI_Oops/backend
UV_CACHE_DIR=../.uv-cache uv run python -m app.scripts.run_incident_csv_workflow \
  --wait-for-batches \
  --poll-interval-seconds 30
```

This is the closest thing to a single manual “daily run everything now” command.

## Dry Run

To validate CSV files without writing rows or moving files:

```bash
cd /Users/leo/Desktop/AI_Oops/backend
UV_CACHE_DIR=../.uv-cache uv run python -m app.scripts.run_incident_csv_workflow \
  --dry-run
```

Use this before a live run when testing a new batch of CSV input.

## Custom Inbox And Archive Paths

To point the runner at a custom inbox and archive:

```bash
cd /Users/leo/Desktop/AI_Oops/backend
UV_CACHE_DIR=../.uv-cache uv run python -m app.scripts.run_incident_csv_workflow \
  --inbox-dir /absolute/path/to/inbox \
  --archive-dir /absolute/path/to/archive
```

Default directories are:

- inbox: `backend/app/imports/inbox`
- archive: `backend/app/imports/archive`

The legacy `submit_incident_review_batch` and
`reconcile_incident_review_batch` commands are deprecated. Use
`run_incident_csv_workflow` for the full one-pass import and review flow.

## What The Runner Actually Does

### 1. Import

- reads incident CSV files from the inbox
- validates required columns and source URLs
- writes incident rows into the database
- places imported incidents into `pending_llm_review`

### 2. Fetch Evidence

- fetches source URLs for pending review incidents
- stores canonical URLs, HTTP status, and extracted evidence text

### 3. Primary Review

- sends incidents directly to the primary OpenAI review model with bounded async
  concurrency
- uses a strict JSON Schema response contract
- receives:
  - legitimacy verdict and score
  - editorial reasoning
  - English headline and summary normalization
  - one or more taxonomy-bound categories
  - severity suggestion, confidence, reasoning, and flags
  - required `needs_escalation` boolean

Primary review output must satisfy all of the following:

- `categories` must be a non-empty list from the fixed product taxonomy
- `severity_confidence` must be numeric when present
- `suggested_severity_score` may be `null` when the model rejects or cannot safely score the incident
- `needs_escalation` must always be present as `true` or `false`

### 4. Approval Routing

- auto-approves only low-risk, high-confidence incidents
- runs a second LLM pass when phase 1 or server-side rules mark the result as
  uncertain
- routes serious incidents to `pending_editor_review`
- routes low-confidence or ambiguous incidents to human review when the second
  pass still returns `needs_escalation=true`

### 5. Escalation

- uses the stronger escalation model only when the incident is ambiguous
- does not escalate just because an incident is high severity
- also escalates when structured review output is invalid, including unknown categories or malformed severity fields

### 6. Duplicate Review

- runs only after approval
- may merge duplicates into an existing canonical incident

### 7. Translation

- runs only for incidents still approved after duplicate review

## Operational Notes

- This workflow is safe to run repeatedly because import and batch reconciliation are designed around current queue state.
- `--wait-for-batches` is useful for manual runs, but scheduled environments may prefer submit-first and reconcile-later behavior depending on runtime limits.
- High-severity incidents will often stop in `pending_editor_review`; that is expected and is part of the product policy.
- The workflow decides final persisted `severity_score` in Python and stores `suggested_severity_score` separately. A `null` model suggestion is valid and does not clear an existing final severity.

## Recommended Modes

### Local Operator Run

Use:

```bash
cd /Users/leo/Desktop/AI_Oops/backend
UV_CACHE_DIR=../.uv-cache uv run python -m app.scripts.run_incident_csv_workflow \
  --wait-for-batches \
  --poll-interval-seconds 30
```

### Scheduler-Friendly Mode

Use:

```bash
cd /Users/leo/Desktop/AI_Oops/backend
UV_CACHE_DIR=../.uv-cache uv run python -m app.scripts.run_incident_csv_workflow
```

Then run a second scheduled reconciliation pass later if needed.

## Success Output

The runner prints a JSON summary containing fields such as:

- `files_found`
- `files_imported`
- `files_failed`
- `incidents_imported`
- `reviews_attempted`
- `reviews_completed`
- `reviews_failed`
- `review_failures`
- `approved`
- `pending_review`
- `rejected`
- `translations_completed`
- `translations_failed`

Treat `pending_review` here as a summary bucket that may include `pending_editor_review` outcomes.
