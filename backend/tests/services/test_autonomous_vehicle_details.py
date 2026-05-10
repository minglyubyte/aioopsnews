from __future__ import annotations

from app.services.autonomous_vehicle_details import (
    assess_autonomous_vehicle_detail_quality,
    build_autonomous_vehicle_detail_copy,
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


def test_extract_autonomous_vehicle_facts_from_dmv_form_narrative() -> None:
    text = (
        "MANUFACTURERS NAME: Zoox, Inc. DATE OF ACCIDENT: 03/14/2026 "
        "0: Howard Street, past 7th Street 0: San Francisco 1: "
        "An occupied Zoox vehicle operating in autonomous mode, after turning "
        "right onto Howard Street from 7th Street in San Francisco, pulled "
        "over to the right to drop off a passenger. Shortly after the "
        "passenger exited and while the now-unoccupied Zoox vehicle was "
        "attempting to re-enter the travel lane in heavy traffic, a van "
        "lightly swiped the left rear fender while attempting to pass the "
        "Zoox vehicle on the left. No injuries were reported."
    )

    facts = extract_autonomous_vehicle_facts(text)

    assert facts.collision_object == "van"
    assert facts.location_context == "Howard Street from 7th Street"
    assert facts.automation_state == "autonomous mode"
    assert facts.injury_or_damage == "No injuries were reported"
    assert "van lightly swiped the left rear fender" in facts.narrative_excerpt
    assert facts.uncertainty_notes == []


def test_extract_autonomous_vehicle_facts_from_dmv_clipped_narrative() -> None:
    text = (
        "0: Eastbound on Martin Ave, near De La Cruz Blvd 1: On April 3, "
        "2026, Nuro was operating a Prius test vehicle in auto mode on "
        "Martin Avenue, when a motorcycle attempted to overtake the Nuro "
        "vehicle from behind. In so doing, the motorcyclist clipped the side "
        "of the Nuro vehicle, causing some minor property damage to the Nuro "
        "vehicle. Neither the motorcyclist nor the occupants were injured."
    )

    facts = extract_autonomous_vehicle_facts(text)

    assert facts.collision_object == "motorcyclist"
    assert facts.automation_state == "autonomous mode"
    assert "motorcyclist clipped the side" in facts.narrative_excerpt
    assert "missing_collision_object" not in facts.uncertainty_notes
    assert "missing_narrative_excerpt" not in facts.uncertainty_notes


def test_extract_autonomous_vehicle_facts_from_dmv_hit_by_narrative() -> None:
    text = (
        "0: Broadway and 2nd St 1: A Zoox vehicle (Vehicle 1) in autonomous "
        "mode was traveling southeast on 2nd Street, preparing to change "
        "lanes to the right to turn onto Broadway in Santa Monica, when it "
        "was hit on the right rear corner by an SUV (Vehicle 2). The Zoox "
        "vehicle sustained severe rear damage."
    )

    facts = extract_autonomous_vehicle_facts(text)

    assert facts.collision_object == "SUV"
    assert "hit on the right rear corner by an SUV" in facts.narrative_excerpt
    assert "missing_collision_object" not in facts.uncertainty_notes
    assert "missing_narrative_excerpt" not in facts.uncertainty_notes


def test_build_autonomous_vehicle_detail_copy_from_evidence() -> None:
    incident = {
        "company_involved": "Waymo",
        "date_logged": "2026-04-01",
        "source_family": "autonomous_vehicle",
        "sources": [
            {
                "evidence_text": (
                    "MANUFACTURERS NAME: Waymo LLC DATE OF ACCIDENT: 04/01/2026 "
                    "0: Electric Avenue near Milwood Avenue 0: Venice 1: "
                    "On April 1, 2026 at 12:20 PM PT a Waymo Autonomous Vehicle "
                    "operating in autonomous mode was stopped facing west on "
                    "Electric Avenue near Milwood Avenue to yield to a pickup "
                    "truck. While the Waymo AV was stopped, the pickup truck "
                    "proceeded to pass to the left, and the left side of the "
                    "pickup truck made contact with the rear left side of the "
                    "stationary Waymo AV. No injuries were reported."
                )
            }
        ],
    }

    detail_copy = build_autonomous_vehicle_detail_copy(incident)

    assert detail_copy is not None
    assert "Electric Avenue near Milwood Avenue" in detail_copy.what_happened_en
    assert "does not establish a confirmed software defect" in (
        detail_copy.ai_failure_point_en
    )
    assert "California DMV" in detail_copy.evidence_summary_en
    enriched = {**incident, **detail_copy.as_dict()}
    assert assess_autonomous_vehicle_detail_quality(enriched).detail_quality == (
        "sufficient"
    )


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


def test_assess_av_detail_quality_ignores_template_summary_for_specific_fields(
) -> None:
    incident = {
        "source_family": "autonomous_vehicle",
        "reality_summary": (
            "California DMV published an autonomous vehicle collision report "
            "for Waymo dated 2026-04-12."
        ),
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
    assert "template_forensic_copy" not in assessment.detail_quality_reasons


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


def test_assess_av_detail_quality_accepts_specific_copy_with_partial_fact_summary(
) -> None:
    incident = {
        "source_family": "autonomous_vehicle",
        "what_happened_en": (
            "According to the California DMV collision report, a Zoox vehicle "
            "was traveling on Harrison Street when another vehicle interaction "
            "led to contact and reported vehicle damage at the scene."
        ),
        "ai_failure_point_en": (
            "The DMV filing does not establish a confirmed software defect, "
            "but the relevant automation question is how the vehicle handled "
            "traffic interaction while operating in autonomous mode."
        ),
        "why_it_matters_en": (
            "The incident matters because DMV collision reports provide public "
            "evidence about autonomous vehicle behavior in real traffic."
        ),
        "sources": [
            {
                "evidence_text": (
                    "A Zoox vehicle operating in autonomous mode was on "
                    "Harrison Street. PROPERTY DAMAGE: None."
                )
            }
        ],
    }

    assessment = assess_autonomous_vehicle_detail_quality(incident)

    assert assessment.detail_quality == "sufficient"
    assert assessment.source_fact_summary is not None
