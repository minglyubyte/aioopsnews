from __future__ import annotations

from app.workflows.autonomous_vehicle_detail_backfill import (
    select_autonomous_vehicle_detail_backfill_candidates,
)
from tests.support.fakes import InMemoryIncidentRepository


def test_select_candidates_only_returns_approved_thin_autonomous_records() -> None:
    repository = InMemoryIncidentRepository(
        incidents=[
            {
                "id": "thin-av",
                "headline": "DMV published Waymo collision report",
                "date_logged": "2026-04-12",
                "company_involved": "Waymo",
                "claimant_name": None,
                "categories": ["Autonomous Systems"],
                "severity_score": 2,
                "reality_summary": (
                    "California DMV published an autonomous vehicle collision "
                    "report for Waymo dated 2026-04-12."
                ),
                "status": "approved",
                "source_family": "autonomous_vehicle",
                "publication_track": "verified_accident",
                "evidence_tier": "official_documented",
                "verification_summary": "Official DMV report.",
                "sources": [
                    {
                        "id": "source-thin",
                        "source_url": "https://www.dmv.ca.gov/thin.pdf",
                        "evidence_text": None,
                    }
                ],
            },
            {
                "id": "rich-av",
                "headline": "Waymo report describes bicyclist collision",
                "date_logged": "2026-04-13",
                "company_involved": "Waymo",
                "claimant_name": None,
                "categories": ["Autonomous Systems"],
                "severity_score": 2,
                "reality_summary": "A fact-rich official report.",
                "status": "approved",
                "source_family": "autonomous_vehicle",
                "publication_track": "verified_accident",
                "evidence_tier": "official_documented",
                "verification_summary": "Official DMV report.",
                "what_happened_en": (
                    "The vehicle was traveling westbound on Market Street near "
                    "5th Street when a bicyclist entered the intersection and "
                    "the vehicle made contact with the bicycle."
                ),
                "ai_failure_point_en": (
                    "The autonomy stack did not avoid a bicyclist entering the "
                    "vehicle path, and manual control occurred after impact."
                ),
                "why_it_matters_en": (
                    "The incident matters because it exposes a vulnerable road "
                    "user edge case in a city intersection."
                ),
                "sources": [
                        {
                            "id": "source-rich",
                            "source_url": "https://www.dmv.ca.gov/rich.pdf",
                            "evidence_text": (
                            "Waymo autonomous vehicle operating in autonomous "
                            "mode was traveling westbound on Market Street near "
                            "5th Street when a bicyclist entered the intersection. "
                            "The AV made contact with the bicycle. The autonomous "
                            "vehicle specialist took manual control after impact. "
                            "No injuries were reported."
                        ),
                    }
                ],
            },
            {
                "id": "thin-legal",
                "headline": "Court noted hallucinated filing",
                "date_logged": "2026-04-14",
                "company_involved": "Legal filing",
                "claimant_name": None,
                "categories": ["Hallucinations"],
                "severity_score": 2,
                "reality_summary": "A court order noted hallucinated citations.",
                "status": "approved",
                "source_family": "legal_hallucination",
                "publication_track": "verified_accident",
                "evidence_tier": "court_or_regulator",
                "verification_summary": "Court document.",
                "sources": [
                    {
                        "id": "source-legal",
                        "source_url": "https://example.com/legal.pdf",
                        "evidence_text": None,
                    }
                ],
            },
        ]
    )

    candidates = select_autonomous_vehicle_detail_backfill_candidates(repository)

    assert [candidate["id"] for candidate in candidates] == ["thin-av"]
