from __future__ import annotations

from app.services.autonomous_vehicle_details import (
    assess_autonomous_vehicle_detail_quality,
    extract_autonomous_vehicle_facts,
)


def test_extract_autonomous_vehicle_facts_from_dmv_style_text() -> None:
    text = (
        "Waymo autonomous vehicle operating in autonomous mode was traveling "
        "westbound on Market Street near 5th Street when a bicyclist entered "
        "the intersection. The AV made contact with the bicycle. The autonomous "
        "vehicle specialist took manual control after impact. No injuries were "
        "reported and minor vehicle damage was noted."
    )

    facts = extract_autonomous_vehicle_facts(text)

    assert facts.collision_object == "bicyclist"
    assert facts.location_context == "Market Street near 5th Street"
    assert facts.automation_state == "autonomous mode"
    assert facts.human_takeover == "manual control after impact"
    assert facts.injury_or_damage == "No injuries were reported"
    assert "bicyclist entered the intersection" in facts.narrative_excerpt
    assert facts.uncertainty_notes == []


def test_assess_av_detail_quality_marks_template_records_insufficient() -> None:
    incident = {
        "source_family": "autonomous_vehicle",
        "what_happened_en": "California DMV published a collision report.",
        "ai_failure_point_en": "An autonomous vehicle system failed.",
        "why_it_matters_en": "This shows autonomous vehicle risk.",
        "sources": [
            {
                "evidence_text": (
                    "California DMV published an autonomous vehicle collision "
                    "report for Waymo dated 2026-04-12."
                )
            }
        ],
    }

    assessment = assess_autonomous_vehicle_detail_quality(incident)

    assert assessment.detail_quality == "insufficient"
    assert "missing_collision_object" in assessment.detail_quality_reasons
    assert "template_forensic_copy" in assessment.detail_quality_reasons
    assert assessment.source_fact_summary is None


def test_assess_autonomous_vehicle_detail_quality_accepts_fact_rich_records() -> None:
    incident = {
        "source_family": "autonomous_vehicle",
        "what_happened_en": (
            "The vehicle was traveling westbound on Market Street near 5th "
            "Street when a bicyclist entered the intersection and the vehicle "
            "made contact with the bicycle before the specialist intervened."
        ),
        "ai_failure_point_en": (
            "The autonomy stack did not avoid a bicyclist entering the vehicle "
            "path, and the report indicates manual control came only after the "
            "impact rather than preventing contact."
        ),
        "why_it_matters_en": (
            "The incident matters because it exposes a vulnerable-road-user "
            "edge case in a city intersection, even though the report says no "
            "injuries were recorded."
        ),
        "sources": [
            {
                "evidence_text": (
                    "Waymo autonomous vehicle operating in autonomous mode was "
                    "traveling westbound on Market Street near 5th Street when "
                    "a bicyclist entered the intersection. The AV made contact "
                    "with the bicycle. The autonomous vehicle specialist took "
                    "manual control after impact. No injuries were reported."
                )
            }
        ],
    }

    assessment = assess_autonomous_vehicle_detail_quality(incident)

    assert assessment.detail_quality == "sufficient"
    assert assessment.detail_quality_reasons == []
    assert assessment.source_fact_summary is not None
    assert "bicyclist" in assessment.source_fact_summary
    assert "Market Street near 5th Street" in assessment.source_fact_summary
