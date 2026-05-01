# Company Name Chinese Translation Design

## Summary

Extend the daily runner translation workflow so Chinese reader mode can localize the company name alongside the existing translated incident copy.

Today the workflow stores Chinese versions of the headline, summary, legitimacy reasoning, and source validation summary, but the company name remains in the shared `company_involved` field. That means the public Chinese toggle still shows English company names even when the rest of the incident card and detail view are localized.

The recommended approach is to add a dedicated `company_involved_zh` field end to end. English source data remains canonical in `company_involved`, while Chinese reader surfaces use `company_involved_zh` when it is available.

## Goals

- Translate company names during the existing daily runner translation step.
- Preserve the canonical source company name in English.
- Expose Chinese company names through the public incident APIs.
- Make the public Chinese toggle render the translated company name consistently in archive cards and detail views.
- Keep English behavior unchanged.

## Non-Goals

- No replacement of the canonical `company_involved` field.
- No on-demand runtime translation in the frontend or public API.
- No redesign of company filtering semantics in this slice.
- No admin workflow redesign beyond carrying the new translated field through existing payloads.

## Data Model

Add `company_involved_zh text` to the incident record alongside the existing translation fields.

The model should then follow this shape:

- `company_involved`: canonical source-language company name
- `company_involved_zh`: translated company name for Chinese reader mode

This mirrors the current `headline_en` / `headline_zh` and `reality_summary_en` / `reality_summary_zh` pattern and keeps locale-specific presentation separate from editorial source data.

## Translation Workflow

Update the translation client contract so it accepts the English company name and returns `company_involved_zh` in the structured JSON response.

The daily runner translation step should:

- pass `incident["company_involved"]` into translation
- persist the returned `company_involved_zh`
- keep the existing translation status behavior unchanged

Approved incidents that reach translation should therefore receive a full Chinese payload that includes:

- `headline_zh`
- `company_involved_zh`
- `reality_summary_zh`
- `legitimacy_reasoning_zh`
- `source_validation_summary_zh`

## Persistence

Repository translation update methods should persist `company_involved_zh` with the same write path already used for the other translated fields.

Required persistence changes:

- schema / migration update for `incident_logs.company_involved_zh`
- repository protocol update
- PostgreSQL repository update methods and serializers
- fake repositories and fixtures used by tests

New incidents imported before translation should default `company_involved_zh` to `null`.

## API Contract

Expose `company_involved_zh` from the public incident feed and incident detail responses.

This keeps locale choice in the client while preserving a stable API contract:

- English readers use `company_involved`
- Chinese readers use `company_involved_zh ?? company_involved`

The public response models should therefore include both fields for list and detail payloads.

## Frontend Rendering

Update the public dashboard locale helpers so Chinese mode localizes company names the same way it already localizes headlines and summaries.

Recommended behavior:

- archive cards show `company_involved_zh ?? company_involved` in Chinese mode
- incident detail metadata shows `company_involved_zh ?? company_involved` in Chinese mode
- English mode continues using `company_involved`

This change should stay limited to reader-facing surfaces that already use the locale toggle. Internal review tooling can continue showing the canonical company field unless there is an explicit product need to localize staff tooling too.

## Testing

Follow TDD for the change.

Backend tests should cover:

- translation client contract includes `company_involved_en` input and `company_involved_zh` output
- daily runner review application persists `company_involved_zh` on approved translated incidents
- schema bootstrap expectations include the new column
- repository translation update methods read and write the new field
- public feed and detail serialization expose `company_involved_zh`

Frontend tests should cover:

- Chinese reader mode renders `company_involved_zh` in the public archive list
- Chinese reader mode renders `company_involved_zh` in incident detail metadata
- fallback to `company_involved` still works when `company_involved_zh` is absent

## Risks And Guardrails

- Some company names may remain unchanged between English and Chinese. That is acceptable; the translated field can equal the source value.
- Existing English filters likely remain keyed to `company_involved`. This is acceptable for this slice because the request is about rendering, not localized filter taxonomies.
- Historical incidents without backfilled company translations should degrade gracefully through frontend fallback behavior.

## Success Criteria

This design is successful if:

- the daily runner stores a Chinese company name whenever translation completes
- public incident APIs return both canonical and Chinese company fields
- the Chinese toggle shows localized company names everywhere the reader currently sees localized incident copy
- English rendering and existing workflow states continue to behave as before
