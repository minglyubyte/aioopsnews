# MVP Launch Checklist

## Product Surface

- [x] Public incident feed renders from API data
- [x] Feed supports reader-facing filtering
- [x] Incident detail view shows source links
- [x] Claim-vs-reality block appears only when a reviewed match exists
- [x] Admin can review and update pending incidents without direct database edits

## Ingestion and Data Flow

- [x] Daily ingestion workflow exists
- [x] Historical backfill workflow exists
- [x] Ingested incidents are enriched before review
- [x] Source dedupe is in place
- [ ] Source list has been expanded and editorially confirmed for launch volume

## Trust and Safety

- [x] Public records require manual approval before appearing in the feed
- [x] Admin endpoints require authentication
- [x] Admin UI is protected from public access
- [ ] Review corrections are stored as audit history
- [ ] Claim-match overrides retain rationale for later analysis

## Quality Evaluation

- [x] Gold-sample review set exists
- [x] Category accuracy has been measured
- [x] Severity agreement has been measured
- [x] Claim-match precision has been measured
- [x] Summary acceptability has been measured
- [x] Launch thresholds are defined for review volume and automation quality
- [ ] Gold-sample coverage has grown to launch-scale editorial review volume

## Operations

- [x] Daily ingest runbook exists
- [x] Backfill runbook exists
- [ ] Production scheduler wiring is documented
- [ ] Failure and backlog monitoring expectations are documented

## Release Decision

The product should be considered launch-ready only when every trust, quality, and operations item above is complete.
