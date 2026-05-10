# Daily Runner

## Purpose

This document describes the operational daily runner workflow for incident ingestion and review.

The product now has two daily tracks:

- `AI Accidents`: fixed high-provenance sources are checked for newly documented incidents. New records enter accident review before public accident publication.
- `AI News`: search discovery finds fresh AI failure reporting. New, non-duplicate items auto-publish to the public AI News stream as unverified news signals.

The main entrypoint is the all-in-one script:

- [run_incident_csv_workflow.py](/Users/leo/Desktop/AI_Oops/backend/app/scripts/run_incident_csv_workflow.py)

This script is the workflow body. It is not itself a scheduler. To run it every day, wrap it in cron, GitHub Actions scheduled jobs, Supabase scheduled jobs, or another deployment scheduler.

## Required Environment

The runner expects:

- `DATABASE_URL`
- `OPENAI_API_KEY`
- `DEEPSEEK_API_KEY`
- `BRAVE_SEARCH_API_KEY` for AI News search discovery

It also uses the configured models from app settings:

- primary review model: `gpt-5.4-mini`
- escalation review model: `gpt-5.2`
- embedding model: `text-embedding-3-small`
- AI News daily result limit: `AI_NEWS_DAILY_RESULT_LIMIT`, default `3`
- AI News freshness window: `AI_NEWS_FRESHNESS`, default `pd`

## Dual-Track Daily Runner

Run the dual-track daily runner from the backend directory:

```bash
cd /Users/leo/Desktop/AI_Oops/backend
UV_CACHE_DIR=../.uv-cache uv run python -m app.scripts.run_dual_track_daily_runner
```

Useful options:

```bash
--skip-news       # run only the accident side
--skip-verified   # run only AI News discovery
--dry-run         # compute create/skip counts without writing rows
--verified-sources all
--verified-sources ca_dmv_av_collisions,nhtsa_data
--since 2026-01-01
--limit-per-source 50
```

The runner prints a JSON summary with:

- `accident_sources_seen`
- `accidents_created`
- `accidents_skipped_existing`
- `news_queries_run`
- `news_results_seen`
- `news_created`
- `news_duplicates_skipped`
- `news_filtered`
- `source_failures`

### AI Accident Track

- The runner fetches fixed-source records from:
  - California DMV autonomous vehicle collision reports
  - NHTSA Standing General Order crash reporting data
  - Damien Charlotin's AI hallucination case tracker
  - EDRM judicial orders
  - FTC official AI enforcement actions
  - DOJ official AI-related enforcement actions and case announcements
  - SEC official AI-washing and AI-related enforcement actions
  - EEOC official AI/automated hiring enforcement actions
  - FDA official AI medical-device warning letters
- New fixed-source accident records are written with `publication_track="verified_accident"` and `status="pending_llm_review"`.
- Existing `external_id` or source URL matches are skipped.
- Existing reviewed incidents are not overwritten or moved back into review.
- FTC, DOJ, and SEC records are treated as regulator/court evidence, not as
  aggregator evidence. These sources start from official AI/enforcement index
  pages and curated case seeds, then follow only allowlisted official
  enforcement, case, litigation-release, complaint, order, or press-release
  links. Pure guidance, speeches, inventories, investor alerts, and policy pages
  are skipped unless they announce a named complaint, lawsuit, settlement,
  order, charges, or comparable enforcement action.
- DOJ coverage includes official Civil Rights case pages and settlement records
  when the alleged harm turns on algorithmic screening, automated software, or
  AI-assisted systems. SEC coverage includes official AI/ML enforcement matters
  such as AI-washing, AI-product misstatements, machine-learning startup fraud,
  and algorithmic-trading fraud.
- EEOC coverage is limited to named enforcement actions involving automated or
  AI-related employment decision systems. FDA coverage is limited to warning
  letters where the agency identifies AI-based medical-device claims,
  premarket-authorization issues, or software validation issues.
- The broader agency-action mode also searches official FTC, SEC, and EEOC
  listing/search pages for named software, automation, algorithm, and AI
  actions. It still requires an official action page and skips pure guidance,
  speeches, policy pages, and generic search hits. If the official eligible
  count is below an operator target such as 500, the scraper reports the actual
  count and does not fabricate rows or use non-official sources.

To generate a CSV for inspection before importing, run:

```bash
cd /Users/leo/Desktop/AI_Oops/backend
UV_CACHE_DIR=../.uv-cache uv run python -m app.scripts.generate_verified_source_csv \
  --sources all \
  --since 2026-01-01 \
  --limit-per-source 50 \
  --out app/imports/inbox/verified-source-auto.csv
```

Then validate the generated CSV with:

```bash
UV_CACHE_DIR=../.uv-cache uv run python -m app.scripts.import_incidents_csv \
  app/imports/inbox/verified-source-auto.csv --dry-run
```

To generate only the official FTC, DOJ, SEC, EEOC, and FDA AI enforcement tier:

```bash
cd /Users/leo/Desktop/AI_Oops/backend
UV_CACHE_DIR=../.uv-cache uv run python -m app.scripts.generate_verified_source_csv \
  --sources ftc_ai_enforcement,doj_ai_enforcement,sec_ai_enforcement,eeoc_ai_enforcement,fda_ai_medical_device_warning_letters \
  --limit-per-source 50 \
  --out app/imports/inbox/verified-source-enforcement.csv
```

To prepare source-named import batches for the five-agency tier while skipping
existing DB rows and writing only enough rows to reach a target total:

```bash
cd /Users/leo/Desktop/AI_Oops/backend
../backend/.venv/bin/python -m app.scripts.prepare_verified_source_import_batch \
  --sources ftc_ai_enforcement,doj_ai_enforcement,sec_ai_enforcement,eeoc_ai_enforcement,fda_ai_medical_device_warning_letters \
  --target-total 500 \
  --limit-per-source 2500 \
  --out-dir app/imports/inbox \
  --out-prefix agency-ai-action-$(date -u +%Y%m%d)
```

Then import without review and refresh evidence:

```bash
../backend/.venv/bin/python -m app.scripts.run_incident_csv_workflow --import-only
../backend/.venv/bin/python -m app.scripts.refresh_source_evidence \
  --limit 500 \
  --source-registry-keys ftc_ai_enforcement,doj_ai_enforcement,sec_ai_enforcement,eeoc_ai_enforcement,fda_ai_medical_device_warning_letters
```

When refreshing source evidence for only this tier, keep the refresh scoped to
the five agency source registry keys so unrelated pending incidents are not fetched:

```bash
cd /Users/leo/Desktop/AI_Oops/backend
UV_CACHE_DIR=../.uv-cache uv run python -m app.scripts.refresh_source_evidence \
  --limit 500 \
  --source-registry-keys ftc_ai_enforcement,doj_ai_enforcement,sec_ai_enforcement,eeoc_ai_enforcement,fda_ai_medical_device_warning_letters
```

### AI News Track

- Brave News Search runs the configured watch queries in small batches.
- Search-result URLs are canonicalized before duplicate checks.
- New AI News records are written with:
  - `status="approved"`
  - `publication_track="accident_watch"`
  - `evidence_tier="reported_unconfirmed"`
  - `source_origin="search_discovery"`
  - `source_registry_key="brave_news_search"`
- AI News does not run accident legitimacy review before publication. It is a public news signal, not a verified accident case file.

### Manual News Upgrade

Editors can upgrade an auto-published AI News item into accident review:

```http
POST /admin/incidents/{id}/upgrade-to-accident
X-Admin-Token: <admin token>
```

The same row is moved to `publication_track="verified_accident"` and `status="pending_llm_review"`. Source metadata is preserved. While review is pending, the row no longer appears in the public AI News stream.

## Core State Flow

The daily runner moves incidents through these states:

1. CSV import creates incidents in `pending_llm_review`
2. primary review returns legitimacy plus severity suggestion
3. high-confidence fixed-source incidents may become `approved`
4. model-rejected incidents become `rejected`
5. uncertain or incomplete incidents become `pending_review`
6. approved incidents run duplicate review
7. still-approved incidents run translation, including company-name localization
8. only `approved` incidents appear in the public feed

The expected production path is therefore: fetch or generate source-backed
records, import them, review or approve them, translate approved incidents, and
then expose them publicly. Translation is not an optional follow-up for newly
approved public incidents; it is part of the approval path.

## Publication Safety

Re-imports are allowed to refresh source and metadata fields, but they must not
undo publication decisions. If a row is already `approved`, a later import of the
same `external_id` must keep it approved. If Chinese public copy has already
completed, a later import must keep the existing `headline_zh`,
`reality_summary_zh`, `translation_status="completed"`, and `translated_at`
instead of replacing them with empty values or `not_requested`.

The repair script below is not the normal daily publication path. Use it only
for historical/backfill repair when sitemap incidents already exist but their
database status or required Chinese public fields are incomplete:

```bash
cd /Users/leo/Desktop/AI_Oops/backend
../backend/.venv/bin/python -m app.scripts.publish_sitemap_incidents
../backend/.venv/bin/python -m app.scripts.publish_sitemap_incidents \
  --apply \
  --missing-limit 100 \
  --concurrency 100
```

Run the command without `--apply` first. The dry run should report how many
sitemap incidents exist, how many rows are missing, and how many records still
need `headline_zh` or `reality_summary_zh`. The apply form only translates rows
missing those required Chinese fields and only marks rows publishable when the
required Chinese copy is present.

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
- reviews pending incidents with bounded async primary-review concurrency and
  global cooldown after provider 429s
- applies approval, rejection, duplicate, translation, and human-review routing
  decisions

## Bounded Review Runs

To import any inbox CSVs and review at most 100 pending incidents with 10
simultaneous primary review calls:

```bash
cd /Users/leo/Desktop/AI_Oops/backend
UV_CACHE_DIR=../.uv-cache uv run python -m app.scripts.run_incident_csv_workflow \
  --max-reviews 100 \
  --review-concurrency 10
```

DeepSeek review no longer applies a proactive qps cap. Keep
`--review-concurrency` near 10 for local operator runs; if the provider returns
HTTP 429, all review workers share a short global cooldown and then continue.
The legacy adaptive RPS flags are still accepted for CLI compatibility, but
they do not impose proactive request-per-second pacing.

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

## Import Without Review

To load CSV rows first and leave review for later:

```bash
cd /Users/leo/Desktop/AI_Oops/backend
UV_CACHE_DIR=../.uv-cache uv run python -m app.scripts.run_incident_csv_workflow \
  --import-only
```

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

- sends incidents directly to the primary review model with bounded async
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

- auto-approves fixed-source incidents when the primary model returns
  `verdict="approved"`, `score >= 0.95`, `severity_confidence >= 0.85`,
  a non-null severity suggestion, confirmed date and company,
  `publication_track="verified_accident"`, official/court evidence tier, and
  fetched fixed-source evidence text
- rejects incidents when the primary model returns `verdict="rejected"`
- routes low-confidence, missing-severity, weak-evidence, unconfirmed, or
  otherwise ambiguous incidents to `pending_review` for the operator

### 5. Escalation

- second-phase escalation is currently disabled for the daily review path;
  `pending_llm_escalation` is retained only as a legacy/manual queue state
- invalid structured review output, including unknown categories or malformed
  severity fields, fails the row for operator follow-up instead of silently
  approving it

### 6. Duplicate Review

- runs only after approval
- may merge duplicates into an existing canonical incident

### 7. Translation

- runs only for incidents still approved after duplicate review
- sends the English company name, headline, reality summary, legitimacy reasoning, and source-validation summary into the translation step
- stores the returned Chinese fields on the incident row, including `company_involved_zh`, `headline_zh`, and `reality_summary_zh`
- marks `translation_status` so operators can distinguish incidents that are still `not_requested` from incidents with completed translated copy

## Operational Notes

- This workflow is safe to run repeatedly because import and review are driven by current queue state.
- `--max-reviews` keeps a run bounded; `--review-concurrency` controls simultaneous primary review API calls.
- Review calls have no proactive qps cap; provider 429s trigger shared cooldown
  and retry.
- High-severity incidents can still auto-approve when evidence and model
  confidence are strong; uncertainty stops in `pending_review`.
- The workflow decides final persisted `severity_score` in Python and stores `suggested_severity_score` separately. A `null` model suggestion is valid and does not clear an existing final severity.
- Public archive filter values are computed from the full approved archive in
  PostgreSQL, not from a paginated archive page. After large approval sweeps,
  refresh the frontend or refetch `/filters` to see new company/category/year
  values.
- For autonomous-vehicle records, `detail_quality="insufficient"` is a reader
  quality warning based on source fact extraction. It does not mean the row
  lacks LLM-written detail sections.

## Recommended Modes

### Local Operator Run

Use:

```bash
cd /Users/leo/Desktop/AI_Oops/backend
UV_CACHE_DIR=../.uv-cache uv run python -m app.scripts.run_incident_csv_workflow \
  --max-reviews 100 \
  --review-concurrency 10
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

For translated incidents, the completed summary corresponds to rows whose translation step has already written `company_involved_zh` and the rest of the Chinese-language display fields.
