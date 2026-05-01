# Database Schema

## Purpose

This document explains the product schema in readable terms. It is not the source of truth for SQL syntax, but it is the human-readable guide to what each table is for and how product concepts map into stored fields.

The actual bootstrap and migration definitions live in:

- [postgres_repository.py](/Users/leo/Desktop/AI_Oops/backend/app/db/postgres_repository.py)
- [20260429170000_initial_incident_schema.sql](/Users/leo/Desktop/AI_Oops/infra/supabase/migrations/20260429170000_initial_incident_schema.sql)

## Schema Overview

The core tables are:

- `claims`
- `claim_sources`
- `incident_logs`
- `incident_sources`
- `incident_duplicate_candidates`

## `claims`

### Purpose

Stores reusable public claims that incidents can match against.

### Important Fields

| Field | Meaning |
| --- | --- |
| `id` | Claim identifier |
| `claimant_name` | Who made the claim |
| `company_involved` | Company associated with the claim |
| `original_claim` | Original claim text |
| `claim_date` | Date of the claim |
| `claim_topic` | Topic bucket |
| `status` | Claim lifecycle state |
| `notes` | Editorial notes |

## `claim_sources`

### Purpose

Stores source URLs that support a claim.

### Important Fields

| Field | Meaning |
| --- | --- |
| `id` | Claim source identifier |
| `claim_id` | Parent claim |
| `source_url` | Source URL |
| `source_kind` | `primary` or `secondary` style source kind |
| `display_order` | Preferred display ordering |

## `incident_logs`

### Purpose

Stores the main incident record. This is the most important table in the system.

### Product Areas Stored Here

- core incident copy
- company and category metadata
- final and suggested severity
- legitimacy review results
- workflow state
- claim-match metadata
- duplicate status
- translation state
- model provenance

### Core Identity And Copy Fields

| Field | Meaning |
| --- | --- |
| `id` | Incident identifier |
| `external_id` | External import identifier |
| `headline` | Current primary headline |
| `headline_en` | English headline |
| `headline_zh` | Chinese headline |
| `date_logged` | Incident date |
| `company_involved` | Company tied to the incident |
| `company_involved_zh` | Chinese translation of the company name for public display when available |
| `incident_topic` | Topic text from import/editorial input |
| `claimant_name` | Claimant associated with the incident when relevant |
| `categories` | Category list from the fixed taxonomy |
| `reality_summary` | Current primary summary |
| `reality_summary_en` | English summary |
| `reality_summary_zh` | Chinese summary |

The current fixed incident taxonomy is:

- Autonomous Systems
- Hallucinations
- Job Automation Fails
- Missed Timelines
- Model Governance
- Privacy/Security

### Severity Fields

| Field | Meaning |
| --- | --- |
| `severity_score` | Final persisted publishable severity decided by workflow or editor |
| `suggested_severity_score` | Model-suggested severity, which may be `null` |
| `severity_confidence` | Confidence in the suggestion |
| `severity_reasoning` | Explanation for the suggestion |
| `severity_flags` | Risk flags such as `privacy_breach` |
| `severity_model` | Model that produced the suggestion |
| `severity_decision_source` | Final severity provenance such as `primary_llm`, `escalation_llm`, `editor`, or `legacy_heuristic` |
| `severity_suggested_at` | Timestamp of latest severity suggestion |

Practical rule:

- `suggested_severity_score` records what the model recommended
- `severity_score` is the final score used by the product
- rejected or unresolved incidents may have a `null` suggested severity without changing the stored final severity

### Legitimacy And Claim Fields

| Field | Meaning |
| --- | --- |
| `confidence_score` | Enrichment classifier confidence |
| `matched_claim_id` | Linked claim when matched |
| `claim_match_confidence` | Confidence of the claim match |
| `legitimacy_score` | Legitimacy review score |
| `legitimacy_label` | Legitimacy verdict |
| `legitimacy_reasoning` | Legitimacy explanation |
| `source_validation_summary` | Source review summary |
| `legitimacy_flag` | Imported editorial flag |
| `confidence_level` | Imported confidence label |
| `import_notes` | Imported notes |
| `review_notes` | Editor or workflow notes |

### Workflow And Operations Fields

| Field | Meaning |
| --- | --- |
| `status` | Workflow state |
| `translation_status` | Translation workflow state such as `not_requested` before approval or `completed` after translated copy is stored |
| `review_batch_id` | Batch review identifier |
| `review_model` | Review model used for the incident |
| `duplicate_status` | Duplicate-review result |
| `duplicate_of_incident_id` | Canonical incident this row duplicates |
| `canonical_incident_id` | Canonical incident reference |
| `embedding_model` | Embedding model used |
| `embedding_vector` | Stored embedding payload |
| `ingestion_run_id` | Ingestion job identifier |
| `reviewed_at` | Review timestamp |
| `translated_at` | Translation timestamp |
| `created_at` | Row creation timestamp |
| `updated_at` | Row update timestamp |

### Translation Payload

When translation completes for an approved incident, `incident_logs` stores a Chinese-language payload that includes:

- `company_involved_zh`
- `headline_zh`
- `reality_summary_zh`

The translated company field is optional at the schema level, but the product uses it when present so Chinese readers can see a localized company name instead of always falling back to the English value.

## `incident_sources`

### Purpose

Stores article, filing, or statement sources associated with each incident.

### Important Fields

| Field | Meaning |
| --- | --- |
| `id` | Incident source identifier |
| `incident_id` | Parent incident |
| `source_url` | Original source URL |
| `canonical_url` | Canonicalized source URL after fetch |
| `source_type` | Source type |
| `publisher` | Source publisher |
| `title` | Source title |
| `published_at` | Source publication time |
| `fetch_status` | Source fetch result |
| `http_status` | HTTP status from fetch |
| `evidence_text` | Extracted evidence text |
| `fetch_error` | Fetch error details |
| `fetched_at` | Fetch timestamp |
| `is_primary` | Whether this source is the primary displayed source |

## `incident_duplicate_candidates`

### Purpose

Stores duplicate-review candidates for a specific incident.

### Important Fields

| Field | Meaning |
| --- | --- |
| `id` | Candidate row identifier |
| `incident_id` | Incident under review |
| `candidate_incident_id` | Potential duplicate incident |
| `embedding_score` | Vector similarity score |
| `llm_verdict` | Duplicate-review verdict |
| `confidence` | Duplicate-review confidence |
| `reasoning` | Duplicate-review reasoning |
| `status` | Candidate status such as pending, confirmed, or dismissed |

## How Product Concepts Map To Tables

### Public Incident Feed

The public feed primarily reads from:

- `incident_logs`
- `incident_sources`
- optionally `claims` through approved claim matching

### Admin Review

Admin review primarily reads from:

- `incident_logs`
- `incident_sources`
- `incident_duplicate_candidates`

### Claim-Vs-Reality

Claim-vs-reality joins:

- `incident_logs.matched_claim_id`
- `claims.id`

### Duplicate Review

Duplicate review uses:

- `incident_logs` for canonical and duplicate state
- `incident_duplicate_candidates` for review evidence

## Practical Reading Guide

- If you want to understand what readers see, start with `incident_logs`.
- If you want to understand where source evidence comes from, look at `incident_sources`.
- If you want to understand reusable promises, look at `claims`.
- If you want to understand duplicate reasoning, look at `incident_duplicate_candidates`.
