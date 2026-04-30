# Launch Readiness Thresholds

## Purpose

These thresholds are the first code-assisted launch gates for the gold-sample evaluation flow. They are intentionally conservative and should be revisited as the gold sample grows beyond the initial seed set.

## Current Thresholds

- Category accuracy: `>= 75%`
- Severity exact agreement: `>= 75%`
- Severity within-1 agreement: `>= 95%`
- Claim-match precision: `>= 85%`
- Summary acceptability: `>= 90%`

## Interpretation Notes

- The current repo sample is a seed dataset that proves the evaluation flow works. It is not large enough on its own to justify launch.
- Claim-match precision should remain a conservative gate because a false match is a reputational risk.
- Severity within-1 agreement matters more than exact agreement for the first pass because it measures whether the rubric is directionally stable.
- The eventual launch review should use a larger reviewed sample before treating these thresholds as decisive.
