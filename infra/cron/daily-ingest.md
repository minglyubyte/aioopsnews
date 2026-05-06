# Daily Ingest

## Schedule

- Run once per day after the major source RSS feeds have settled.
- Recommended cron: `15 13 * * *` UTC.
- Expected runtime for the MVP feed set: under 10 minutes.

## Secrets and Configuration

- `DATABASE_URL`
- `OPENAI_API_KEY` when enrichment moves from heuristic mode to hosted model calls
- `BRAVE_SEARCH_API_KEY` for the AI News discovery side of the dual-track runner
- a descriptive RSS fetch user agent for source requests

## Run Stages

1. `accident_fixed_source_check`
2. `news_search_discovery`
3. `dedupe`
4. `persist`
5. `accident_review`
6. `news_auto_publish`

AI News items are public after duplicate checks and basic discovery metadata capture. They remain separate from reviewed AI Accident case files and can be manually upgraded into accident review from the admin surface.

## Retry Policy

- Retry transient source fetch failures up to 2 times after the initial attempt.
- Treat per-source failures as isolated; one failed source should not stop the rest of the run.
- Record the final error string in run output for operator review.

## Operator Checks

- confirm `source_failures` is `0`
- review `accidents_created`, `news_created`, and `news_duplicates_skipped` for sharp changes
- review pending accident-review queue growth after upgrades or fixed-source discoveries
- inspect any failed source entries before the next run
