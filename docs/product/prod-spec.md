# Product Spec

## Purpose

This is the canonical product behavior document for AI Reality Check. It covers severity policy, review logic, approval gating, admin workflow, duplicate handling, translation, and launch-readiness expectations.

## Core Product Model

AI Reality Check is an accountability product for tracking AI failures and comparing public claims against observed outcomes. Incidents are the core public record. Claims are reusable statements that may attach to multiple incidents.

The system is designed to:

- collect incidents from trusted reporting and curated imports
- validate whether an incident is legitimate and publishable
- assess severity using an impact-first rubric
- match incidents to public claims when appropriate
- surface only reviewed approved incidents to readers

## Severity Rubric

`severity_score` is the final publishable severity. It reflects real-world impact first, not how sensational a story sounds.

### Severity 1

Minor, limited, quickly reversible, and no meaningful external harm.

Example: a support chatbot gives a few users an incorrect FAQ answer, but nobody acts on it and the team fixes it quickly.

### Severity 2

Real problem, but limited and reversible, usually localized and with a workaround.

Example: an internal scheduling or workflow assistant misroutes a small batch of work and causes temporary operational friction.

### Severity 3

Clear operational or business impact that requires rollback, manual intervention, or a pause in service.

Example: AI-generated code causes a production outage for a couple of hours. This defaults to Severity 3 unless there is additional evidence of privacy, safety, legal, regulatory, or major financial harm.

### Severity 4

Major real-world harm or sensitive-domain impact, especially where privacy, legal, regulatory, financial, or broad safety consequences are involved.

Example: an AI system leaks sensitive personal data or wrongly denies high-stakes services, housing, credit, or benefits at meaningful scale.

### Severity 5

Catastrophic, severe, and hard to reverse. Usually involves serious injury, death, systemic safety failure, or very large-scale harm.

Example: an autonomous or medical AI failure contributes to death, serious injury, or a major public-safety incident.

### Upgrade Rules

- Safety-critical incidents should start at Severity 4 unless clearly minor.
- Confirmed serious injury or death is Severity 5.
- Broad privacy breach, major legal or regulatory action, or major financial harm is at least Severity 4.
- A near miss in a safety-critical system may raise severity by one level, but near miss logic does not replace actual harm.
- Editorial tone never changes severity on its own.

## Trusted Source And Editorial Policy

### Trusted Source List

The trusted source list is intentionally narrow. Fixed verified accident sources
include official regulator/court records such as California DMV, NHTSA, FTC,
DOJ, SEC, court filings, and judicial orders. News publications remain useful
for discovery, but they do not replace primary official evidence for verified
accident records.

### Source Credibility Policy

- Primary sources include official filings, regulator notices, court documents, company statements, and direct reporting from the originating organization.
- Secondary sources include established publications that clearly attribute reporting and link back to primary material when possible.
- Disallowed sources include anonymous summary farms, unattributed reposts, and low-accountability aggregators that cannot support fact checking.

## Taxonomy

The current taxonomy is:

- Autonomous Systems
- Hallucinations
- Job Automation Fails
- Missed Timelines
- Model Governance
- Privacy/Security

## Claims

Claims live in a separate claims table rather than being embedded into incident rows. This keeps public promises reusable across multiple incidents.

## Review And Approval Logic

This section is the current manual review and approval gate for the product.

## Primary Review

The primary model reviews legitimacy and also returns:

- `legitimacy_label`
- `legitimacy_score`
- `legitimacy_reasoning`
- `source_validation_summary`
- normalized English headline and summary
- `categories`
- `suggested_severity_score`
- `severity_confidence`
- `severity_reasoning`
- `severity_flags`

The primary review contract is strict structured output:

- responses use a JSON Schema contract rather than loose JSON mode
- `categories` must be a non-empty list drawn only from the fixed product taxonomy
- invalid or unknown categories are treated as invalid output and force escalation or review
- `suggested_severity_score` may be `null` when the model cannot responsibly assign severity

## Auto-Approval Gate

An incident may auto-approve only when all of the following are true:

- legitimacy verdict is `approved`
- `legitimacy_score >= 0.95`
- `suggested_severity_score` is present
- `severity_confidence >= 0.85`
- date is confirmed
- company is confirmed
- `publication_track` is `verified_accident`
- `evidence_tier` is `official_documented` or `court_or_regulator`
- at least one fixed verified source has fetched evidence text

## Escalation Logic

Second-phase escalation is disabled for the normal daily review path.
`pending_llm_escalation` is retained as a legacy/manual queue state, but new
uncertain incidents should route to `pending_review`.

## Human Review Logic

Use `pending_review` when an incident needs an operator decision before
publication. High severity alone does not require a separate status; severity,
confidence, and high-risk flags remain visible inside the review record.

## Duplicate Handling

- duplicate review runs only after approval
- confirmed duplicates move to `duplicate_confirmed`
- duplicates do not publish as separate public incidents

## Translation

- translation runs only after approval
- translation does not run for incidents merged away as duplicates

## Admin Review Behavior

Editors should see both:

- final editable `severity_score`
- suggested severity block with score, confidence, reasoning, and flags

If an editor overrides the final severity away from the model suggestion, the system should preserve that distinction through severity provenance fields.

The workflow decides final stored severity separately from the model suggestion:

- `suggested_severity_score` is the model recommendation and may be `null`
- `severity_score` is the persisted publishable severity
- the workflow only overwrites `severity_score` from model output when the final incident status is `approved`
- non-approved incidents may still retain a suggested severity for editor context without changing the final published score

## Workflow States

Main workflow states include:

- `pending_review`
- `pending_llm_review`
- `approved`
- `rejected`
- `duplicate_confirmed`

Legacy/manual queue compatibility also recognizes `pending_llm_escalation`.

## Reader Detail Quality

Autonomous-vehicle incidents include a computed `detail_quality` signal. A value
of `insufficient` means the source fact extractor could not confirm enough AV
specifics, not that the incident lacks LLM-written detail sections.

Only `approved` incidents are public.

## Product Metrics

### Incident-Level Fields

- `severity_score`
- `suggested_severity_score`
- `severity_confidence`
- `severity_reasoning`
- `severity_flags`
- `severity_model`
- `severity_decision_source`
- `confidence_score`
- `claim_match_confidence`
- `legitimacy_score`
- `legitimacy_label`
- `legitimacy_reasoning`
- `source_validation_summary`
- `duplicate_status`

### Duplicate Candidate Fields

- `embedding_score`
- `llm_verdict`
- `confidence`
- `reasoning`
- `status`

## Launch Readiness Thresholds

Current launch-readiness thresholds are:

- Category accuracy: `>= 75%`
- Severity exact agreement: `>= 75%`
- Severity within-1 agreement: `>= 95%`
- Claim-match precision: `>= 85%`
- Summary acceptability: `>= 90%`

Important interpretation:

- these are model-quality thresholds, not publication permissions
- good severity agreement does not bypass the editorial gate for Severity 3+
- the current gold sample is still too small to justify public launch on its own

## Current Non-Goals

The current product does not yet provide:

- full review audit history
- mature override analytics
- launch-scale operations proof
- broad open ingestion from low-accountability sources
