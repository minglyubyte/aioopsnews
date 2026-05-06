# Production Operations

## Purpose

This document defines the minimum operating model for running AI Reality Check as a production editorial system. It ties together daily ingest, historical backfill, failure handling, queue monitoring, and launch-day checks.

## Operating Model

- One editor owns review and publication decisions.
- Public incidents remain manual-approval only.
- Daily dual-track ingestion is the default production workflow.
- AI News auto-publishes after duplicate checks as an unverified news signal.
- AI Accidents remain review-gated before public accident publication.
- Historical backfill is a controlled maintenance task, not part of the daily schedule.

## Daily Ingest Scheduling

### Recommended Production Schedule

- Run the daily ingest job once per day after major source RSS feeds have settled.
- Recommended cron: `15 13 * * *` UTC.
- Expected runtime for the current MVP feed set: under 10 minutes.

### Required Runtime Inputs

- `DATABASE_URL`
- `ADMIN_API_TOKEN`
- `SCRAPER_USER_AGENT`
- `BRAVE_SEARCH_API_KEY`
- `OPENAI_API_KEY` if enrichment later moves beyond heuristic mode

### Expected Daily Sequence

1. Start the scheduled ingest run.
2. Confirm the run completes without fatal process failure.
3. Review run metrics:
   - `accidents_created`
   - `accidents_skipped_existing`
   - `news_results_seen`
   - `news_created`
   - `news_duplicates_skipped`
   - `source_failures`
4. Review the pending accident queue before approving any accident case file.
5. Promote any AI News item to accident review only when it should become part
   of the reviewed accident archive.

## Backfill Execution Policy

### When To Run Backfill

- Run backfill only for historical coverage expansion or recovery from missing periods.
- Do not combine broad backfill with the same-day launch window unless necessary.

### Safe Backfill Sequence

1. Run a pilot on one source and one month first.
2. Review the resulting incidents for taxonomy, severity, summary quality, and claim-match quality.
3. Expand to the full selected date range only if the pilot looks acceptable.
4. Reuse the same checkpoint and audit files if a run is interrupted.

### Backfill Safeguards

- Do not delete checkpoint files until the full run is complete.
- Review audit logs for unexpected spikes in duplicates or low creation volume.
- Sample the admin queue before bulk approvals.

## Failure Handling

### Daily Ingest Failures

- If `source_failures` is `0`, continue with normal review.
- If one source fails but the rest of the run completes:
  - review the failed source entry
  - rerun or manually inspect before the next publish cycle if the source is high-value
- If the whole ingest job fails:
  - rerun once after verifying config and runtime inputs
  - if the second attempt fails, pause same-day publish expectations and investigate before continuing

### Backfill Failures

- Restart the job with the same checkpoint path.
- Confirm the checkpoint file still reflects completed `source|batch` pairs.
- Review the audit log before resuming.

### Classification or Claim-Match Concerns

- Keep questionable incidents in `pending_review`.
- Prefer no public publish over low-confidence approval.
- If a heuristic looks unstable, continue manual review and treat the metric as below launch confidence.

## Queue Monitoring Expectations

### Daily Checks

- Check pending queue size after each ingest run.
- Look for sharp changes in:
  - queue growth
  - severe incidents
  - claim-matched incidents
- Watch for repeated low-quality incidents from the same source.

### Escalation Heuristics

- If queue growth exceeds what one editor can review in one cycle, delay approvals and work the backlog first.
- If multiple days show elevated `source_failures`, treat the source set or runtime configuration as unstable.
- If evaluation metrics fall below thresholds, keep the system in manual-review mode and do not widen automation trust.

## Launch-Day Checks

### Before Publish

1. Confirm the latest daily ingest completed.
2. Confirm `source_failures` is `0` or understood and accepted.
3. Confirm the admin queue has been reviewed.
4. Run the launch-readiness evaluation:

```bash
cd backend
./.venv/bin/python -m app.evals.launch_readiness
```

5. Compare results against [launch-readiness-thresholds.md](/Users/leo/Desktop/AI_Oops/.worktrees/task-16-ops-docs/docs/product/launch-readiness-thresholds.md).
6. Confirm the public feed contains only intentionally approved incidents.

### After Publish

- Review the feed once as a reader.
- Check for broken source links or obviously bad summaries.
- Confirm the next daily ingest remains scheduled.

## Launch Readiness Boundary

This document makes operations explicit, but it does not remove the remaining launch blockers around:

- broader gold-sample coverage
- review-history / override traceability, if later judged necessary
- editorial confidence in ongoing heuristic quality
