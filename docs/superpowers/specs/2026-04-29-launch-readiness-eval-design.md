# Launch Readiness Evaluation Design

## Goal

Add a repeatable, code-assisted evaluation flow that measures whether the current AI Reality Check pipeline is trustworthy enough for launch.

## Recommended Approach

Use a repo-owned gold-sample dataset plus a backend evaluation runner.

This keeps the first evaluation pass deterministic, easy to re-run in CI or locally, and lightweight enough for the current MVP without adding more UI complexity.

## Dataset Design

- Store a reviewed gold-sample file in the repo.
- Keep the format simple and explicit:
  - incident input fields
  - expected category labels
  - expected severity score
  - expected claim-match expectation
  - expected summary acceptability judgment
- Start with a small seed sample that proves the evaluation flow works, even if it is below the eventual launch target of 50 incidents.

## Evaluation Design

- Add a backend evaluation module that reads the gold-sample file.
- Reuse the current enrichment and claim-matching logic where possible.
- Compute at least these metrics:
  - category exact-match accuracy
  - severity exact agreement
  - severity within-1 agreement
  - claim-match precision
  - summary acceptability rate
- Return both machine-readable metric data and a human-readable summary.

## Output Shape

- A structured result object for tests and scripting.
- A readable text summary for terminal use and docs.
- Metric counts should include numerator and denominator, not just percentages.

## Threshold Design

- Put initial launch thresholds in product docs, not in a complex runtime config system.
- Thresholds should be conservative and easy to revise.
- The evaluation runner should make it obvious whether current metrics meet those thresholds.

## Scope Boundaries

- No new frontend evaluation UI in this slice.
- No reviewer identity system.
- No live network evaluation runs.
- No attempt to automate gold-sample authoring yet.

## Testing

- Add tests for:
  - parsing the gold-sample dataset
  - metric calculation on a known fixture
  - threshold/pass-fail summary on a known fixture

## Documentation Updates

- Update `docs/product/mvp-launch-checklist.md`
- Update `docs/product/mvp-status.md`
- Document how to run the evaluation locally in `README.md`
