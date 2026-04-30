# MVP Status

## Summary

AI Reality Check currently has a working end-to-end MVP implementation in code, but it is not yet fully launch-ready.

## Implemented

- Public feed of approved incidents
- Category and company filtering
- Incident detail view with source links
- Claim-vs-reality block for reviewed matches
- SQLite-backed read layer and seed data for local development
- RSS ingestion with dedupe
- Enrichment and heuristic claim matching
- Historical backfill workflow with checkpointing and audit output
- Daily ingestion workflow with retry behavior and run metrics
- Shared-secret protected admin review API
- Minimal admin review UI
- Seed gold-sample evaluation flow with launch-threshold reporting

## Launch Blockers

- Editor corrections overwrite the incident row and do not yet create a separate audit trail or correction history.
- Launch-readiness evaluation still needs broader editorial coverage:
  - grow the gold sample toward launch-scale coverage
  - add override-rate measurements from real review activity
  - validate metrics against a larger reviewed set
- Production scheduler wiring and ongoing monitoring expectations are not yet documented.

## Readiness Call

- Demo-ready: yes
- Internal functional MVP: yes
- Public launch-ready MVP: not yet

## Recommended Next Steps

1. Add review history and override audit logging.
2. Expand the gold-sample set and run launch-readiness evaluation on a larger reviewed corpus.
3. Document production scheduling and monitoring expectations.
