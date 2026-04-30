from __future__ import annotations

from datetime import date

from app.db.repository_protocol import IncidentRepository
from app.services.claim_matcher import match_incident_to_claim
from app.services.classifier import classify_incident
from app.services.summarizer import summarize_incident


def enrich_pending_incidents(
    *,
    repository: IncidentRepository,
) -> dict[str, int]:
    pending_incidents = repository.list_pending_incidents()
    claims = repository.list_claims()
    enriched = 0
    skipped = 0

    for incident in pending_incidents:
        source_summary = incident["source_summary"]
        if not source_summary:
            skipped += 1
            continue

        classification = classify_incident(
            headline=incident["headline"],
            source_summary=source_summary,
        )
        summary = summarize_incident(
            headline=incident["headline"],
            source_summary=source_summary,
        )
        claim_match = match_incident_to_claim(
            claims=claims,
            headline=incident["headline"],
            source_summary=source_summary,
            company_involved=classification.company_involved,
            categories=classification.categories,
            incident_date=date.fromisoformat(incident["date_logged"]),
        )

        repository.update_incident_enrichment(
            incident_id=incident["id"],
            company_involved=classification.company_involved,
            claimant_name=classification.company_involved,
            categories=classification.categories,
            severity_score=classification.severity_score,
            reality_summary=summary,
            confidence_score=classification.confidence_score,
            review_notes=(
                "Automatically enriched from source headline and summary; "
                "manual review still required."
            ),
            matched_claim_id=claim_match.claim.id if claim_match else None,
            claim_match_confidence=claim_match.confidence if claim_match else None,
        )
        enriched += 1

    return {
        "pending_found": len(pending_incidents),
        "enriched": enriched,
        "skipped": skipped,
    }
