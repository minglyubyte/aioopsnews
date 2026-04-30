# Daily Ingest

## Schedule

- Run once per day after the major source RSS feeds have settled.
- Recommended cron: `15 13 * * *` UTC.
- Expected runtime for the MVP feed set: under 10 minutes.

## Secrets and Configuration

- `DATABASE_URL`
- `OPENAI_API_KEY` when enrichment moves from heuristic mode to hosted model calls
- a descriptive RSS fetch user agent for source requests

## Run Stages

1. `fetch`
2. `dedupe`
3. `persist`
4. `enrich`
5. `claim_match`
6. `mark_review_status`

## Retry Policy

- Retry transient source fetch failures up to 2 times after the initial attempt.
- Treat per-source failures as isolated; one failed source should not stop the rest of the run.
- Record the final error string in run output for operator review.

## Operator Checks

- confirm `source_failures` is `0`
- review `incidents_created` and `duplicates_skipped` for sharp changes
- review `incidents_flagged_for_manual_review` to understand queue growth
- inspect any failed source entries before the next run
