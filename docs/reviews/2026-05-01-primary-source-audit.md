# Primary Source Audit

Source file reviewed: [incidents_2023_user_paste.csv](/Users/leo/Desktop/AI_Oops/backend/app/imports/inbox/incidents_2023_user_paste.csv)

## What I changed

- Promoted `56` rows to a clearer primary-source anchor.
- Replaced generic California DMV collision index links with incident-specific DMV PDF reports for rows `6-50`.
- Added stronger direct links for these non-AV rows:
`51`, `58`, `59`, `60`, `63`, `71`, `80`, `81`, `86`, `87`, `90`

## Likely already had a defensible primary

- `1 inc-av-001`
- `4 inc-av-004`
- `53 inc-legal-003`
- `54 inc-legal-004`
- `69 inc-scam-006`

## Still weak after this pass

These rows still rely on indirect reporting, tracker pages, generic company pages, or other links I would not yet treat as a clean prompt-compliant primary source:

- `2 inc-av-002`
- `3 inc-av-003`
- `5 inc-av-005`
- `52 inc-legal-002`
- `55 inc-defam-001`
- `56 inc-defam-002`
- `57 inc-defam-003`
- `61 inc-info-003`
- `62 inc-oper-001`
- `64 inc-scam-001`
- `65 inc-scam-002`
- `66 inc-scam-003`
- `67 inc-scam-004`
- `68 inc-scam-005`
- `70 inc-info-004`
- `72 inc-info-006`
- `73 inc-info-007`
- `74 inc-abuse-001`
- `75 inc-abuse-002`
- `76 inc-abuse-003`
- `77 inc-bias-001`
- `78 inc-bias-002`
- `79 inc-bias-003`
- `82 inc-bias-006`
- `83 inc-bias-007`
- `84 inc-bias-008`
- `85 inc-data-001`
- `88 inc-data-004`
- `89 inc-copy-001`
- `91 inc-copy-003`
- `92 inc-copy-004`
- `93 inc-copy-005`
- `94 inc-oper-003`
- `95 inc-oper-004`

## Verification

- Direct parser validation succeeded: `validated_rows=95`
- Import order check: first row `inc-av-001`, last row `inc-oper-004`
- `uv run pytest tests/services/test_incident_import.py -q` did not complete because `uv` panicked in the local runtime, so I did not use that as success evidence.
