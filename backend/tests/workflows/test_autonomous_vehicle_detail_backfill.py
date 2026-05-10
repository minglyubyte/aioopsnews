from __future__ import annotations

from app.services.incident_translation import IncidentTranslation
from app.workflows.autonomous_vehicle_detail_backfill import (
    backfill_autonomous_vehicle_details,
    select_autonomous_vehicle_detail_backfill_candidates,
)
from tests.support.fakes import InMemoryIncidentRepository


class RecordingTranslationClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def translate(self, **kwargs: str) -> IncidentTranslation:
        self.calls.append(kwargs)
        return IncidentTranslation(
            company_involved_zh="Waymo",
            headline_zh="ZH headline",
            reality_summary_zh="ZH summary",
            legitimacy_reasoning_zh="ZH legitimacy",
            source_validation_summary_zh="ZH source validation",
            incident_summary_zh="ZH incident summary",
            what_happened_zh="ZH what happened",
            ai_failure_point_zh="ZH ai failure point",
            why_it_matters_zh="ZH why it matters",
            evidence_summary_zh="ZH evidence summary",
            status="completed",
        )


class PublicDetailRepository:
    def list_public_incidents(self, filters: object) -> list[dict[str, str]]:
        return [{"id": "already-rich"}]

    def get_public_incident(self, incident_id: str) -> dict[str, object] | None:
        return {
            "id": incident_id,
            "status": "approved",
            "source_family": "autonomous_vehicle",
            "analysis": {
                "detail_quality": "sufficient",
                "detail_quality_reasons": [],
            },
            "sources": [],
        }


def test_select_candidates_uses_public_detail_quality_when_available() -> None:
    candidates = select_autonomous_vehicle_detail_backfill_candidates(
        PublicDetailRepository()
    )

    assert candidates == []


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


def test_backfill_autonomous_vehicle_details_updates_public_detail_fields() -> None:
    repository = InMemoryIncidentRepository(
        incidents=[
            {
                "id": "dmv-av",
                "headline": "Waymo DMV collision report",
                "headline_en": "Waymo DMV collision report",
                "date_logged": "2026-04-01",
                "company_involved": "Waymo",
                "claimant_name": None,
                "categories": ["Autonomous Systems"],
                "severity_score": 2,
                "reality_summary": "California DMV published a report.",
                "reality_summary_en": "California DMV published a report.",
                "status": "approved",
                "source_family": "autonomous_vehicle",
                "publication_track": "verified_accident",
                "evidence_tier": "official_documented",
                "verification_summary": "Official DMV report.",
                "legitimacy_reasoning": "Official DMV source.",
                "source_validation_summary": "Official DMV collision report.",
                "translation_status": "completed",
                "sources": [
                    {
                        "id": "source-dmv-av",
                        "source_url": "https://www.dmv.ca.gov/portal/file/waymo_040126-pdf/",
                        "is_primary": True,
                        "fetch_status": "fetched",
                        "source_registry_key": "ca_dmv_av_collisions",
                        "evidence_text": (
                            "MANUFACTURERS NAME: Waymo LLC DATE OF ACCIDENT: "
                            "04/01/2026 0: Electric Avenue near Milwood Avenue "
                            "0: Venice 1: On April 1, 2026 at 12:20 PM PT a "
                            "Waymo Autonomous Vehicle operating in autonomous "
                            "mode was stopped facing west on Electric Avenue "
                            "near Milwood Avenue to yield to a pickup truck. "
                            "While the Waymo AV was stopped, the pickup truck "
                            "proceeded to pass to the left, and the left side "
                            "of the pickup truck made contact with the rear "
                            "left side of the stationary Waymo AV. No injuries "
                            "were reported."
                        ),
                    }
                ],
            }
        ]
    )
    translation_client = RecordingTranslationClient()

    summary = backfill_autonomous_vehicle_details(
        repository,
        translation_client=translation_client,
    )

    assert summary == {
        "candidates": 1,
        "updated": 1,
        "translated": 1,
        "skipped": 0,
        "translation_failed": 0,
    }
    incident = repository.incidents["dmv-av"]
    assert "Electric Avenue near Milwood Avenue" in incident["what_happened_en"]
    assert "does not establish a confirmed software defect" in (
        incident["ai_failure_point_en"]
    )
    assert incident["translation_status"] == "completed"
    assert incident["what_happened_zh"] == "ZH what happened"
    assert len(translation_client.calls) == 1
    detail = repository.get_public_incident("dmv-av")
    assert detail is not None
    assert detail["analysis"]["detail_quality"] == "sufficient"
