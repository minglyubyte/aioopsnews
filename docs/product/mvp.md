# MVP

## Summary

AI Reality Check has a working end-to-end MVP in code, but it is not yet fully launch-ready.

The current MVP includes:

- a public feed of approved incidents
- incident detail views with sources
- optional claim-vs-reality blocks
- RSS and CSV-based incident ingestion
- enrichment, legitimacy review, severity suggestion, and approval gating
- duplicate review and post-approval translation
- a protected admin review queue

## Current Product Surface

### Public Experience

- chronological incident feed
- category and company filtering
- incident detail view with linked sources
- claim-vs-reality module when a reviewed match exists

### Internal Operations

- shared-secret protected admin review API
- internal review UI for queue triage and overrides
- model-suggested severity, confidence, reasoning, and flags visible during review
- duplicate candidate review context in the admin surface

### Data And Workflow

- PostgreSQL-backed incident repository
- RSS ingestion with dedupe
- curated CSV import for incidents and claims
- enrichment for company/category suggestion and claim matching
- primary review with legitimacy scoring and severity suggestion
- escalation review for ambiguous incidents
- duplicate review after approval
- translation after approval

## MVP Decisions

### Trusted Source List

The MVP trusted source list is intentionally narrow and begins with Reuters, AP, Financial Times, Bloomberg, The Verge, Wired, Ars Technica, company blogs, legal filings, NHTSA, EEOC, and FTC publications. New sources should be added only after editorial review.

### Taxonomy

The launch taxonomy is fixed for MVP:

- Autonomous Systems
- Hallucinations
- Job Automation Fails
- Missed Timelines
- Model Governance
- Privacy/Security

### Claims Model

Claims live in a separate claims table rather than being embedded into incident rows. This keeps public promises reusable across multiple incidents and avoids denormalizing claim history.

### Review Gate

Public incidents require legitimacy review before publication. Low-risk incidents may auto-approve when both legitimacy and severity gates pass, but higher-severity or high-risk incidents still require editor review.

The review contract is now strict:

- the primary and escalation review models return schema-bound structured output
- `categories` must be a non-empty list from the fixed MVP taxonomy
- invalid taxonomy values do not get silently repaired; they force escalation or review
- model-suggested severity may be `null` when the incident is rejected, unsupported, or otherwise not safely scoreable

## Launch Readiness

### Current Call

- Demo-ready: yes
- Internal functional MVP: yes
- Public launch-ready MVP: not yet

### Main Blockers

- Editor corrections still overwrite the incident row instead of producing a separate review history or full audit trail.
- Launch-readiness evaluation still needs broader editorial coverage and more reviewed samples.
- Override-rate measurement and longer-term review quality monitoring are still missing.
- Operational readiness is documented, but not yet proven at launch-scale volume.

## Launch Checklist

### Product Surface

- [x] Public incident feed renders from API data
- [x] Feed supports reader-facing filtering
- [x] Incident detail view shows source links
- [x] Claim-vs-reality block appears only when a reviewed match exists
- [x] Admin can review and update pending incidents without direct database edits

### Ingestion And Data Flow

- [x] Daily ingestion workflow exists
- [x] Historical backfill workflow exists
- [x] Ingested incidents are enriched before review
- [x] Source dedupe is in place
- [ ] Source list has been expanded and editorially confirmed for launch volume

### Trust And Safety

- [x] Public records require review gating before appearing in the feed
- [x] Admin endpoints require authentication
- [x] Admin UI is protected from public access
- [ ] Review corrections are stored as audit history
- [ ] Claim-match overrides retain rationale for later analysis

### Quality Evaluation

- [x] Gold-sample review set exists
- [x] Category accuracy has been measured
- [x] Severity agreement has been measured
- [x] Claim-match precision has been measured
- [x] Summary acceptability has been measured
- [x] Launch thresholds are defined
- [ ] Gold-sample coverage has grown to launch-scale editorial review volume

### Operations

- [x] Daily runner exists
- [x] Backfill workflow exists
- [x] Batch reconciliation workflow exists
- [x] Failure and backlog monitoring expectations are documented
- [ ] Production scheduler wiring has been exercised in a real deployment

## Recommended Next Steps

1. Add review history and override audit logging.
2. Expand the reviewed gold sample and rerun launch-readiness evaluation on a broader corpus.
3. Validate the daily runner against realistic operations volume before treating it as launch-hardened.
