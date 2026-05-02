# Incident Forensic Detail Design

## Summary

Redesign the public incident detail experience so it reads like a forensic brief instead of a generic context card. The current `Full context` panel is too abstract, repeats summary copy, and does not explain the exact AI failure mode clearly enough. The new design introduces a more specific editorial structure for readers and a richer provenance-aware structure for reviewers.

This work also changes the real default primary analysis model to `DeepSeek Flash V4` while keeping that model label out of the public dashboard. Model provenance should appear only in the reviewer panel.

Any new reader-facing analysis field introduced by this redesign must be added end-to-end to the translation pipeline, storage schema, API contracts, and localized frontend rendering.

## Goals

- Make the public incident detail view answer the reader's core questions in a clear order:
  - what happened
  - what in the AI failed
  - why it matters
  - how well supported the incident is
- Keep `Evidence summary` as a compact, trusted section.
- Replace abstract or repetitive analysis copy with more concrete incident reporting.
- Introduce a first-class analysis field for AI failure explanation instead of forcing that meaning into `what happened` or `why it matters`.
- Change the real default primary analysis model to `DeepSeek Flash V4`.
- Show model provenance only in the internal reviewer panel.
- Ensure every new reader-facing analysis field is translated into Chinese and tracked in the translation workflow.

## Non-Goals

- No redesign of ingestion or review workflow outside the areas needed to support the new analysis structure.
- No public exposure of model labels or generation provenance.
- No new source preview cards, embedded PDFs, or richer source crawler behavior.
- No removal of legacy analysis fields before compatibility and migration are in place.
- No broader localization redesign beyond keeping new fields synchronized with the existing English/Chinese pattern.

## Product Decisions

### Public Incident Detail Layout

The public incident detail card on `/` should adopt a balanced forensic story layout. It should feel editorial and investigative, not operational.

Reading hierarchy:

1. Incident header
2. Opening incident summary
3. What happened
4. Failure point in the AI stack
5. Why it matters
6. Evidence summary
7. Reporting trail

### Reviewer Panel Layout

The internal reviewer panel should reuse the same underlying incident analysis fields, but add operational provenance and editorial controls. This is where the model label changes to `DeepSeek Flash V4`.

The public dashboard and reviewer panel should not drift into separate content models. They share the same analysis bundle and differ only in presentation and operational metadata.

## Public Detail Design

### Incident Header

The header belongs to the public dashboard's selected incident detail card, not the reviewer panel.

It should include:

- company
- severity
- date
- category chips

It should not include:

- model name
- translation status
- internal review metadata
- source validation internals

### Opening Incident Summary

Add a short summary field that states the incident plainly and specifically. This summary should not simply restate the headline. It should orient the reader before the deeper forensic sections begin.

### What Happened

This section should describe the event sequence in concrete language:

- the actors involved
- the triggering event
- the key failure moment
- the immediate consequences

This section should read like reported incident context, not like a generic AI risk summary.

### Failure Point in the AI Stack

This becomes the anchor section of the redesigned detail view.

It should explain both:

- system-level failure
- model-level or subsystem-level miss when the evidence supports it

The section should answer:

- what layer of the AI system failed
- what the model or subsystem likely got wrong
- how that failure propagated into the real-world incident
- what fallback, safeguard, or human checkpoint should have prevented escalation

The presentation should prefer specificity without overclaiming internals that are not source-supported.

### Why It Matters

This section should focus on consequences instead of repetition.

It should address:

- user harm
- operational impact
- regulatory or business fallout
- what the incident reveals about the limitations of the AI system

### Evidence Summary

Keep this section compact and strong. It should summarize:

- source quality
- agreement across sources
- uncertainty or caveats

This section remains a trust-building layer, not the main narrative.

### Reporting Trail

Sources remain in a support panel or secondary area so the main reading flow stays narrative-first.

Source rendering remains lightweight:

- publisher
- title when available
- outbound link

## Reviewer Panel Design

The reviewer panel should present the same analysis content plus operational provenance.

It should include:

- the same forensic analysis sections used publicly
- primary model label set to `DeepSeek Flash V4`
- translation status for the full forensic analysis bundle
- existing source validation and review metadata
- existing editorial controls for review or revision

The reviewer panel should support quick inspection of whether the generated analysis is specific enough, especially in:

- `what happened`
- `ai failure point`
- `why it matters`

## Data Model Changes

The current analysis shape is too narrow for the agreed detail design. The redesigned analysis bundle should become first-class in the domain model and API.

Recommended reader-facing fields:

- `incident_summary`
- `what_happened`
- `ai_failure_point`
- `why_it_matters`
- `evidence_summary`

Recommended localized storage pattern:

- `incident_summary_en`
- `incident_summary_zh`
- `what_happened_en`
- `what_happened_zh`
- `ai_failure_point_en`
- `ai_failure_point_zh`
- `why_it_matters_en`
- `why_it_matters_zh`
- `evidence_summary_en`
- `evidence_summary_zh`

Compatibility guidance:

- legacy incidents may continue to rely on existing fields during transition
- the API should provide a safe compatibility path for older records
- reviewer surfaces should reveal when a record is missing the richer forensic structure

## Translation Synchronization

Translation coverage is a hard requirement for this redesign.

Rule:

`new reader-facing detail field = new translated field`

That means every new analysis field must be added consistently across:

- database schema
- backend models
- serialization and API responses
- translation workflow input and output
- frontend localized rendering

The system should not silently allow English analysis to become richer while Chinese falls behind.

Preferred behavior:

- if a new reader-facing field exists but is not translated, the translation workflow should mark the record incomplete or stale
- reviewer surfaces should make missing translation coverage visible
- translation status should cover the full forensic bundle, not only legacy analysis fields

## Generation Model Behavior

The real default primary analysis model should change to `DeepSeek Flash V4`.

This change must be real pipeline behavior, not only display copy. It should apply wherever the primary incident analysis content is generated for storage or review.

Public behavior:

- do not display the model name on the public dashboard

Reviewer behavior:

- display the actual primary model used for the analysis
- show `DeepSeek Flash V4` in reviewer provenance surfaces after the default switch

If model metadata is stored separately from analysis content, the reviewer panel should read from the same truthful source of record rather than a hardcoded label.

## Migration Strategy

This redesign should ship without breaking older incidents.

Recommended migration approach:

1. add the new analysis fields and API support
2. keep compatibility rendering for older incidents
3. generate or backfill the richer forensic fields for newly reviewed incidents first
4. surface incomplete forensic coverage in reviewer tools
5. backfill or regenerate older incidents over time as needed

Fallback behavior for older records should be explicit and safe rather than silently producing empty sections.

## Error Handling

### Public Dashboard

- Missing detail fields should degrade gracefully without breaking the whole detail panel.
- Empty forensic sections should not render as blank headings.
- Source load or detail load failures should remain localized to the detail area.

### Reviewer Panel

- Missing translation coverage should be visible.
- Missing provenance or model metadata should be visible.
- Reviewers should be able to distinguish:
  - legacy record
  - incomplete forensic bundle
  - stale translation bundle

## Testing

### Backend Tests

- verify new analysis fields are stored and returned correctly
- verify compatibility behavior for older incidents
- verify the real default primary analysis model changes to `DeepSeek Flash V4`

### Translation Tests

- verify each new reader-facing field is included in translation input
- verify translated values are stored and returned in localized responses
- verify missing translated fields are surfaced as incomplete or stale states

### Frontend Tests

- verify the public dashboard renders the new forensic brief sections
- verify the public dashboard does not show the model label
- verify the reviewer panel does show the model label
- verify localized English and Chinese rendering for the full forensic bundle
- verify older incidents still render safely

### Regression Tests

- verify incidents with only legacy analysis fields do not break public detail rendering
- verify reviewer views surface missing bundle coverage correctly

## Implementation Notes

- Reuse the existing English/Chinese rendering patterns already present in the public dashboard.
- Prefer extending the current `IncidentAnalysis` model rather than introducing a disconnected parallel analysis object.
- Keep the public and reviewer views coupled to the same canonical analysis payload to reduce drift.
- Avoid shipping English-only content for any new public detail section.

## Open Questions

No unresolved product questions remain for this slice. The implementation plan should focus on execution details, migration boundaries, and test sequencing.
