from __future__ import annotations

from datetime import date

from app.models.claim import ClaimRecord
from app.services.claim_matcher import match_incident_to_claim


def test_match_incident_to_claim_returns_curated_match_for_support_failure() -> None:
    claims = [
        ClaimRecord(
            id="claim-support",
            claimant_name="AssistCo",
            company_involved="AssistCo",
            original_claim=(
                "Our assistant will eliminate repetitive support escalations."
            ),
            claim_date=date(2026, 1, 15),
            claim_topic="job automation",
            status="approved",
        ),
        ClaimRecord(
            id="claim-robotics",
            claimant_name="RoboFleet",
            company_involved="RoboFleet",
            original_claim=(
                "Our fleet will operate safely without sidewalk supervisors."
            ),
            claim_date=date(2026, 2, 20),
            claim_topic="autonomous operations",
            status="approved",
        ),
    ]

    match = match_incident_to_claim(
        claims=claims,
        headline="AssistCo support bot leaks internal notes",
        source_summary=(
            "A customer support assistant exposed private account notes in "
            "user-facing replies before the feature was disabled."
        ),
        company_involved="AssistCo",
        categories=["Privacy/Security"],
        incident_date=date(2026, 4, 30),
    )

    assert match is not None
    assert match.claim.id == "claim-support"
    assert match.confidence >= 0.85


def test_match_incident_to_claim_returns_none_when_no_curated_claim_fits() -> None:
    claims = [
        ClaimRecord(
            id="claim-robotics",
            claimant_name="RoboFleet",
            company_involved="RoboFleet",
            original_claim=(
                "Our fleet will operate safely without sidewalk supervisors."
            ),
            claim_date=date(2026, 2, 20),
            claim_topic="autonomous operations",
            status="approved",
        )
    ]

    match = match_incident_to_claim(
        claims=claims,
        headline="SignalLoop dashboard outage follows vendor billing delay",
        source_summary=(
            "A reporting dashboard remained unavailable while the company "
            "resolved an external billing dispute."
        ),
        company_involved="SignalLoop",
        categories=["Operational Failure"],
        incident_date=date(2026, 4, 30),
    )

    assert match is None
