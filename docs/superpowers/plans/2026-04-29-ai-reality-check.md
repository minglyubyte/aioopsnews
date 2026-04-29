# AI Reality Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an MVP accountability platform that ingests credible AI-failure reporting, enriches incidents with structured metadata and claim-vs-reality context, and serves a calm, filterable journalistic feed to end users.

**Architecture:** Use a greenfield monorepo with a React/Next.js frontend, a FastAPI backend, and PostgreSQL via Supabase. Separate ingestion from read APIs so scraping, enrichment, review, and public serving can evolve independently while sharing one normalized incident schema.

**Tech Stack:** Next.js, TypeScript, Tailwind CSS, FastAPI, Python, Supabase/PostgreSQL, pgvector or text-search indexes, cron/scheduled jobs, OpenAI-compatible LLM classification, pytest, Playwright, Vercel or similar frontend hosting.

---

## Recommended Repo Structure

Because the workspace is currently empty, start with a greenfield structure like this:

- `frontend/`
  - `app/`
  - `components/`
  - `lib/`
  - `types/`
- `backend/`
  - `app/api/`
  - `app/core/`
  - `app/db/`
  - `app/models/`
  - `app/services/`
  - `app/workflows/`
  - `app/scrapers/`
  - `tests/`
- `infra/`
  - `supabase/`
  - `cron/`
- `docs/`
  - `superpowers/plans/`
  - `product/`

## File Map

These are the primary files and directories the MVP should create.

### Frontend

- `frontend/app/page.tsx`
  - Landing page and main incident feed shell.
- `frontend/app/incidents/page.tsx`
  - Dedicated listing view if the team wants a separate route from the homepage.
- `frontend/components/incident-card.tsx`
  - Feed card for headline, summary, tags, severity, and sources.
- `frontend/components/claim-reality-block.tsx`
  - Two-column or stacked claim-vs-reality visual.
- `frontend/components/filter-sidebar.tsx`
  - Company, category, claimant, and severity filters.
- `frontend/components/severity-badge.tsx`
  - Shared severity color system and labeling.
- `frontend/lib/api.ts`
  - Client-side API fetch helpers.
- `frontend/types/incident.ts`
  - Shared frontend incident model.

### Backend

- `backend/app/main.py`
  - FastAPI app entrypoint.
- `backend/app/api/incidents.py`
  - Public incident feed endpoints.
- `backend/app/api/admin.py`
  - Admin review and override endpoints.
- `backend/app/models/incident.py`
  - Incident ORM or Pydantic model.
- `backend/app/models/claim.py`
  - Optional normalized claim model if claim tracking is split from incidents.
- `backend/app/db/schema.sql`
  - Initial database schema or SQL reference.
- `backend/app/services/incident_query.py`
  - Filter, pagination, and sort logic.
- `backend/app/services/classifier.py`
  - Category extraction, severity scoring, and structured enrichment.
- `backend/app/services/claim_matcher.py`
  - Claim lookup and claim-vs-reality matching.
- `backend/app/services/summarizer.py`
  - Neutral two-sentence summarization.
- `backend/app/workflows/backfill.py`
  - Historical import pipeline.
- `backend/app/workflows/daily_ingest.py`
  - Scheduled scrape and enrich workflow.
- `backend/app/scrapers/rss.py`
  - RSS fetch utility.
- `backend/app/scrapers/news_sites.py`
  - Site-specific parser adapters.
- `backend/tests/`
  - Unit, integration, and workflow tests.

### Infra

- `infra/supabase/migrations/`
  - Migration files for incidents, claims, sources, and review metadata.
- `infra/cron/daily-ingest.md`
  - Scheduler contract, runtime env vars, retry rules.
- `infra/cron/backfill-runbook.md`
  - Historical import execution notes and recovery steps.

## Delivery Phases

### Phase 0: Product and Delivery Foundation

**Why first:** The PRD is clear on product goals, but the MVP still needs a few operating constraints nailed down before implementation starts.

- [ ] Confirm the initial source list for ingest.
  - Target 10-20 trusted sources only for MVP.
  - Suggested starting list: Reuters, AP, FT, Bloomberg, The Verge, Wired, Ars Technica, company blogs, legal filings, NHTSA, EEOC, FTC.
- [ ] Freeze the MVP taxonomy.
  - Categories: Hallucinations, Autonomous Systems, Bias/Discrimination, Copyright, Job Automation Fails, Privacy/Security, Missed Timelines.
- [ ] Decide whether `claims` should be a separate table from `incident_logs`.
  - Recommendation: yes. Reuse the same claim across multiple incidents.
- [ ] Decide the admin-review posture for launch.
  - Recommendation: public incidents are visible only after automated enrichment plus one manual review until precision is proven.
- [ ] Write a source credibility policy.
  - Define acceptable primary, secondary, and disallowed sources.

**Acceptance criteria:**

- A short product decision record exists for source policy, taxonomy, review policy, and launch gate.
- Engineering can implement the schema without guessing missing product rules.

## Actionable Backlog

### Epic 1: Repository Bootstrap and Environment Setup

**Owner:** Full-stack engineer

**Dependencies:** None

**Deliverables:**

- Monorepo scaffold with `frontend/`, `backend/`, and `infra/`.
- FastAPI service booting locally.
- Next.js app booting locally.
- Shared `.env.example` for Supabase, LLM keys, and scraping config.
- README with local setup and run commands.

**Action items:**

- [ ] Initialize the repository structure and baseline docs.
- [ ] Create frontend app shell and backend app shell.
- [ ] Add formatting, linting, and test runners for both apps.
- [ ] Add CI for backend tests and frontend build.
- [ ] Document local developer setup in `README.md`.

**Acceptance criteria:**

- `frontend` runs locally and renders a placeholder page.
- `backend` exposes `/health` and returns `200`.
- CI fails on lint or test regressions.

### Epic 2: Database Schema and Persistence Layer

**Owner:** Backend engineer

**Dependencies:** Epic 1

**Deliverables:**

- Production-ready PostgreSQL schema for incidents, claims, sources, and review metadata.
- Migrations in `infra/supabase/migrations/`.
- Backend models and query helpers.

**Action items:**

- [ ] Create `incident_logs` with the PRD fields plus operational fields:
  - `created_at`
  - `updated_at`
  - `status`
  - `ingestion_run_id`
  - `confidence_score`
  - `review_notes`
- [ ] Create a `claims` table:
  - `id`
  - `claimant_name`
  - `company_involved`
  - `original_claim`
  - `claim_date`
  - `claim_topic`
  - `status`
- [ ] Create an `incident_sources` table so one incident can reference multiple URLs with source type metadata.
- [ ] Add indexes for `date_logged`, `severity_score`, `company_involved`, `status`, and category search.
- [ ] Decide whether categories are stored as `text[]` or normalized with a join table.
  - Recommendation: use `text[]` for MVP and normalize later only if necessary.

**Acceptance criteria:**

- Schema supports all PRD fields without denormalizing claim reuse.
- API queries can filter by date, severity, category, company, and claimant without table scans for typical MVP usage.

### Epic 3: Source Registry and Scraper Adapters

**Owner:** Backend engineer

**Dependencies:** Epic 2

**Deliverables:**

- Config-driven source registry.
- RSS fetcher and site parser adapters.
- Raw article capture format for enrichment input.

**Action items:**

- [ ] Create `backend/app/core/source_registry.py` for source definitions.
- [ ] Implement RSS polling in `backend/app/scrapers/rss.py`.
- [ ] Implement HTML/article extraction for non-RSS cases in `backend/app/scrapers/news_sites.py`.
- [ ] Store raw scrape payloads or normalized article blobs before enrichment for auditability.
- [ ] Add deduplication logic by canonical URL, title similarity, and publication date.

**Acceptance criteria:**

- A scheduled run can ingest source metadata from at least 5 trusted sources.
- Duplicate articles are skipped or merged cleanly.
- Failed scrapes are logged and do not crash the whole workflow.

### Epic 4: LLM Enrichment Pipeline

**Owner:** Backend engineer

**Dependencies:** Epic 3

**Deliverables:**

- Structured classification prompt and response schema.
- Two-sentence neutral summary generation.
- Severity scoring implementation.
- Category tagging implementation.

**Action items:**

- [ ] Define a strict JSON response contract for enrichment:
  - `headline`
  - `date_logged`
  - `company_involved`
  - `categories`
  - `severity_score`
  - `reality_summary`
  - `claim_match_confidence`
  - `source_urls`
- [ ] Implement `backend/app/services/summarizer.py` for neutral summaries.
- [ ] Implement `backend/app/services/classifier.py` for category and severity classification.
- [ ] Hard-code the 1-5 severity rubric from the PRD into prompt instructions and validation rules.
- [ ] Add post-processing validation to reject malformed, speculative, or low-confidence outputs.
- [ ] Add manual fallback status for incidents the model cannot classify confidently.

**Acceptance criteria:**

- Enrichment returns parseable JSON for a representative article set.
- Summaries stay neutral and capped at two sentences.
- Severity scores always fall within 1-5 and map back to the rubric.

### Epic 5: Claim Registry and Claim-vs-Reality Matching

**Owner:** Backend engineer

**Dependencies:** Epics 2 and 4

**Deliverables:**

- Claim database bootstrap.
- Claim matcher service.
- UI-ready claim-vs-reality payload.

**Action items:**

- [ ] Seed `claims` with an initial curated dataset of high-profile AI promises.
  - Example domains: autonomous driving, AGI timelines, job replacement claims, coding automation promises.
- [ ] Implement `backend/app/services/claim_matcher.py` to match incidents against seeded claims using entity, topic, date, and semantic similarity heuristics.
- [ ] Store:
  - matched claim id
  - match confidence
  - generated reality statement
- [ ] Require stricter confidence thresholds for public display than for internal suggestions.
- [ ] Add a null-match path so most incidents can remain plain incident cards when no credible claim pairing exists.

**Acceptance criteria:**

- Matching does not fabricate claims.
- The system can attach a curated claim to relevant incidents and leave unrelated incidents untouched.
- Claim-vs-reality output is concise and fact-based.

### Epic 6: Historical Backfill Workflow

**Owner:** Backend engineer

**Dependencies:** Epics 3, 4, and 5

**Deliverables:**

- One-time backfill script covering November 30, 2022 through launch date.
- Progress tracking and resumability.
- Audit log of imported sources and skipped records.

**Action items:**

- [ ] Implement `backend/app/workflows/backfill.py`.
- [ ] Partition the date range into monthly or quarterly batches.
- [ ] Add checkpointing after each batch so failed runs can resume.
- [ ] Run a smaller pilot backfill first on one source and one month.
- [ ] Review pilot precision before starting the full backfill.

**Acceptance criteria:**

- Backfill can resume after interruption without duplicate inserts.
- A pilot sample can be reviewed quickly for taxonomy, severity, and summary quality.
- Full historical coverage is operationally tractable.

### Epic 7: Daily Cron Ingestion Pipeline

**Owner:** Backend engineer

**Dependencies:** Epics 3, 4, and 5

**Deliverables:**

- Daily scheduled ingestion job.
- Retry and alerting behavior.
- Run metrics by source and classifier stage.

**Action items:**

- [ ] Implement `backend/app/workflows/daily_ingest.py`.
- [ ] Add run stages:
  - fetch
  - dedupe
  - enrich
  - claim match
  - persist
  - mark review status
- [ ] Define retry behavior for transient fetch or LLM failures.
- [ ] Record run stats:
  - articles fetched
  - incidents created
  - incidents flagged for manual review
  - source failures
- [ ] Write `infra/cron/daily-ingest.md` with schedule, secrets, and expected runtime.

**Acceptance criteria:**

- A daily run can complete unattended.
- Failures are visible and isolated.
- Review queue volume is measurable.

### Epic 8: Public Read API and Filter Endpoints

**Owner:** Backend engineer

**Dependencies:** Epics 2, 4, and 5

**Deliverables:**

- Public incident list endpoint.
- Filter and pagination support.
- Optional summary stats endpoint for filter counts.

**Action items:**

- [ ] Create `backend/app/api/incidents.py`.
- [ ] Implement `GET /incidents` with:
  - date sort
  - page or cursor pagination
  - category filter
  - company filter
  - claimant filter
  - severity min/max filter
- [ ] Implement `GET /incidents/{id}` for detail view expansion if needed.
- [ ] Implement `GET /filters` or equivalent metadata endpoint for available companies, claimants, and categories.
- [ ] Expose only approved incidents to public consumers.

**Acceptance criteria:**

- Frontend can render the full MVP feed from API data alone.
- Filter interactions do not require client-side hard-coded taxonomies.
- Draft or low-confidence incidents stay hidden from public views.

### Epic 9: Frontend Feed Experience

**Owner:** Frontend engineer

**Dependencies:** Epic 8

**Deliverables:**

- Calm, premium-looking homepage or feed page.
- Responsive incident feed.
- Persistent filter sidebar or mobile drawer.

**Action items:**

- [ ] Implement the main feed shell in `frontend/app/page.tsx`.
- [ ] Build `frontend/components/incident-card.tsx`.
- [ ] Build `frontend/components/filter-sidebar.tsx`.
- [ ] Build `frontend/components/severity-badge.tsx` with the PRD palette:
  - 1: Slate Gray
  - 2: Muted Blue
  - 3: Soft Gold
  - 4: Burnt Orange
  - 5: Deep Maroon
- [ ] Implement empty states, loading states, and zero-results messaging that reinforce the platform’s grounded tone.

**Acceptance criteria:**

- Users can scan incidents chronologically and understand severity at a glance.
- Filters are usable on desktop and mobile.
- The visual design feels editorial and trustworthy rather than alarmist.

### Epic 10: Claim-vs-Reality UI Component

**Owner:** Frontend engineer

**Dependencies:** Epics 5 and 9

**Deliverables:**

- Clear side-by-side or stacked claim-vs-reality module.
- Attribution for claimant, claim date, and reality date.

**Action items:**

- [ ] Implement `frontend/components/claim-reality-block.tsx`.
- [ ] Render the exact stored claim text, claimant, and claim date.
- [ ] Render the current factual reality summary and visible “as of” date.
- [ ] Only show the module when confidence and review state pass the public threshold.
- [ ] Make the module visually distinct from the base incident card without becoming sensational.

**Acceptance criteria:**

- Users can immediately distinguish hype from documented outcomes.
- The component does not display unmatched or low-confidence claims.

### Epic 11: Admin Review and Correction Workflow

**Owner:** Full-stack engineer

**Dependencies:** Epics 4, 5, and 8

**Deliverables:**

- Review queue for pending incidents.
- Admin override flow for categories, severity, summaries, and claim matches.

**Action items:**

- [ ] Create `backend/app/api/admin.py`.
- [ ] Add incident status values:
  - `pending_review`
  - `approved`
  - `rejected`
  - `needs_rework`
- [ ] Build a minimal internal page or protected admin table for triage.
- [ ] Store all human corrections for later pipeline evaluation.
- [ ] Add audit visibility for why a claim match or severity score was overridden.

**Acceptance criteria:**

- Editors can correct mistakes without manual database edits.
- Correction history is retained for quality analysis.

### Epic 12: Quality Evaluation and Launch Readiness

**Owner:** Full-stack engineer

**Dependencies:** All earlier epics

**Deliverables:**

- Precision review set for severity and claim matching.
- Observability dashboard or logged metrics.
- Launch checklist.

**Action items:**

- [ ] Create a gold-sample evaluation set of at least 50 incidents.
- [ ] Measure:
  - category accuracy
  - severity agreement
  - claim-match precision
  - summary acceptability
- [ ] Set launch thresholds for auto-approval versus manual review.
- [ ] Add logging for scraper failures, classifier exceptions, and review backlog growth.
- [ ] Write `docs/product/mvp-launch-checklist.md`.

**Acceptance criteria:**

- The team can quantify whether the pipeline is trustworthy enough for public release.
- Launch decisions are tied to measurable quality rather than gut feel.

## Suggested Build Order

If the team wants the shortest path to a demo:

1. Epic 1: bootstrap repo and environments
2. Epic 2: schema and persistence
3. Epic 8: basic public API
4. Epic 9: frontend feed with mocked data first, then live API
5. Epic 4: enrichment pipeline
6. Epic 5: claim matching
7. Epic 11: admin review
8. Epic 3: source registry and scrapers
9. Epic 7: daily cron ingestion
10. Epic 6: historical backfill
11. Epic 12: evaluation and launch gates

This order gives the team a visible product quickly, then hardens the automation behind it.

## First 15 Tickets

If you want to move this PRD straight into a tracker, create these tickets first:

1. Create greenfield monorepo structure for frontend, backend, and infra
2. Scaffold FastAPI app with `/health` endpoint
3. Scaffold Next.js app with editorial feed placeholder
4. Add shared environment config and README setup guide
5. Design and migrate `incident_logs` table
6. Design and migrate `claims` table
7. Design and migrate `incident_sources` table
8. Add public `GET /incidents` endpoint with mock data
9. Build incident card component and severity badge system
10. Build filter sidebar with local state
11. Implement source registry for trusted publications
12. Implement RSS fetcher with dedupe
13. Implement neutral summary generator with strict JSON schema
14. Implement severity scoring service from PRD rubric
15. Seed first claim dataset and build claim matcher

## Risks and Open Decisions

- Scraping reliability will vary widely across publishers.
- Claim matching is the highest reputational-risk feature and should launch conservatively.
- Severity scoring needs human feedback loops early or it will drift into overstatement.
- “Credible primary source” needs a written standard before automation scales.
- Legal review may be needed if source excerpting becomes more than headline-plus-summary-plus-link.

## Success Metrics Mapped to Delivery

- **Pipeline accuracy**
  - Measure admin override rate for severity, summaries, and claim matching.
- **Engagement**
  - Measure filter interactions per session, average feed depth, and return visits.
- **Editorial trust**
  - Measure proportion of incidents backed by primary or high-confidence secondary sources.

## Recommended Team Split

- **Backend engineer**
  - Schema, ingestion, enrichment, APIs, cron workflows
- **Frontend engineer**
  - Feed UX, filters, claim-vs-reality component, responsive polish
- **Editor or product owner**
  - Source policy, gold-sample review, claims seed list, launch thresholds

## Definition of MVP Done

The MVP is done when:

- A user can open the site and browse a filterable chronological feed of approved incidents.
- Each incident shows headline, date, company, categories, summary, severity, and source links.
- Some incidents can show a reviewed claim-vs-reality block.
- A daily ingest job can fetch, enrich, and queue new incidents for review.
- An admin can correct bad classifications without touching the database directly.
- The team has quality metrics proving the automation is reliable enough to operate.
