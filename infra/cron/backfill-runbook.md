# Historical Backfill Runbook

## Purpose

Use the historical backfill workflow to populate incidents over a larger date range without creating duplicates.

## Workflow Capabilities

- partitions a date range into monthly batches by default
- supports pilot mode for one source and one batch
- writes a checkpoint file so interrupted runs can resume
- writes an audit log with fetched, created, and skipped counts
- reuses the enrichment workflow after each batch

## Required Inputs

- `DATABASE_URL`
- a writable checkpoint path
- a writable audit-log path
- a selected source list
- start and end dates

## Recommended Operating Sequence

1. Run a pilot on one source and one month first.
2. Review the created incidents for taxonomy, severity, summary quality, and claim-match quality.
3. Expand to the full source list only after the pilot looks acceptable.
4. If a run is interrupted, restart with the same checkpoint and audit paths.

## Output Files

- checkpoint JSON:
  - tracks completed `source|batch` pairs
- audit JSON:
  - records `articles_fetched`
  - records `incidents_created`
  - records `duplicates_skipped`

## Operator Checks

- confirm the checkpoint file is advancing between completed batches
- review the audit log for unexpected spikes in duplicates or low creation volume
- spot-check a sample of created incidents in the admin queue before broad approval
- do not delete the checkpoint file until the entire run is complete
