# Incident Import Design

## Goal

Build a PostgreSQL-backed incident CSV import path for AI Reality Check that turns curated, source-backed AI incident batches into structured incident records.

This importer should support the product's core editorial idea:

- AI is not perfect
- documented AI-related failures should be captured as first-class records
- some incidents should be linked to public AI claims when that connection is defensible
- some incidents should remain standalone and still be publishable

The import path should preserve editorial judgment instead of hiding it. Each imported incident should carry both:

- a legitimacy decision
- a confidence level

That lets the team filter, audit, and revisit incident quality over time instead of treating those labels as one-time import metadata.

## Recommended Approach

Build a full editorial incident importer parallel to the existing claim importer.

The importer should:

- parse the new incident CSV format with pipe-separated `source_links`
- validate that each incident has at least 3 links
- upsert incidents by `incident_id`
- replace incident sources on upsert
- store `legitimacy_flag` and `confidence_level` on the incident record
- derive incident publication status from those editorial fields

This keeps the workflow operationally simple while preserving enough structure for future filtering and auditing.

## CSV Format

Use this header:

```csv
ref_number,incident_id,company,incident_date,incident_topic,incident_description,mapped_claim,source_links,legitimacy_flag,confidence_level,notes
```

Required columns:

- `incident_id`
- `company`
- `incident_date`
- `incident_topic`
- `incident_description`
- `source_links`
- `legitimacy_flag`
- `confidence_level`

Optional columns:

- `ref_number`
- `mapped_claim`
- `notes`

## Validation Rules

- `incident_date` must use `YYYY-MM-DD`
- `incident_id` must be unique within the file
- `source_links` must split into at least 3 valid `http://` or `https://` URLs
- duplicate links within a row should be deduped
- `legitimacy_flag` must be one of:
  - `ACCEPT`
  - `REVIEW`
  - `REJECT`
- `confidence_level` must be one of:
  - `low`
  - `medium`
  - `high`
- `mapped_claim` may be blank
- `notes` may be blank

## Status Mapping

Imported status should be derived from the editorial fields:

- `ACCEPT` + `high` -> `approved`
- everything else -> `pending_review`

This keeps the manual review queue as the default gate while still allowing the strongest curated incidents to enter the live feed immediately.

## Database Changes

Extend `incident_logs` with:

- `incident_topic text`
- `legitimacy_flag text`
- `confidence_level text`
- `import_notes text`

Keep using:

- `matched_claim_id` for `mapped_claim`
- `incident_sources` for normalized incident links

No new staging table is needed in v1.

## Source Storage

`source_links` should be normalized into `incident_sources`.

Recommended v1 behavior:

- one URL becomes one `incident_sources` row
- `source_type` should be set to `imported`
- `is_primary` should be `1` for the first link and `0` for the rest
- `publisher`, `title`, and `published_at` can remain null when the CSV does not provide them

This keeps import simple without losing link-level provenance.

## Upsert Behavior

Use `incident_id` as the stable key.

If an imported `incident_id` already exists:

- update the incident row
- replace all existing `incident_sources` rows for that incident with the current CSV links
- recompute status from `legitimacy_flag` and `confidence_level`
- preserve `created_at`
- refresh `updated_at`

This supports iterative editorial improvement without creating duplicate incidents.

## Import Surface

Add a new backend import path parallel to claim import:

- service: `backend/app/services/incident_import.py`
- CLI: `backend/app/scripts/import_incidents_csv.py`

The CLI should support:

- `--dry-run`
- `--apply`

## Repository Changes

Extend the repository protocol with:

- `upsert_incident_import_row(...)`

Implement that in:

- `backend/app/db/postgres_repository.py`
- `backend/tests/fakes.py`

## Testing

Add parser tests for:

- valid CSV parsing
- duplicate `incident_id`
- invalid dates
- invalid legitimacy/confidence values
- malformed URLs
- fewer than 3 links

Add import tests for:

- dry run validates without persisting
- apply inserts incident rows and normalized sources
- repeated import upserts the same incident
- re-import replaces source rows
- `ACCEPT/high` becomes `approved`
- all other combinations become `pending_review`

## Scope Boundaries

- PostgreSQL only
- no SQLite compatibility
- no claim auto-matching inside this importer
- no fuzzy dedupe by headline or description
- no staging table in v1
- no automatic source metadata extraction in v1

## Success Criteria

This design is successful if:

- curated AI incident batches can be imported reliably
- every imported incident carries at least 3 source links
- editorial legitimacy and confidence remain queryable on the record
- high-confidence accepted incidents can go live immediately
- lower-confidence or disputed incidents land in the review queue
- repeated imports improve existing records instead of fragmenting them
