from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

DetailQuality = Literal["not_applicable", "insufficient", "sufficient"]

_TEMPLATE_MARKERS = (
    "california dmv published an autonomous vehicle collision report",
    "dmv published an autonomous vehicle collision report",
)
_GENERIC_FAILURE_MARKERS = (
    "autonomous vehicle system failed",
    "autonomous driving system failed",
    "autonomous system failed",
)
_ROAD_SUFFIX = (
    r"(?:Street|St\.|Avenue|Ave\.|Road|Rd\.|Boulevard|Blvd\.|Drive|Dr\.|"
    r"Lane|Ln\.)"
)
_COLLISION_OBJECT_PATTERNS = (
    r"\bwhen (?:a |an |the )?(?P<object>[a-z][a-z -]{2,40}) entered\b",
    r"\bin a collision involving (?:a |an |the )?(?P<object>[a-z][a-z -]{2,40}) on\b",
    r"\bwas rear ended by (?:a |an |the )?(?P<object>[a-z][a-z -]{2,40})",
    r"\bwas hit [^.]{0,80}\bby (?:a |an |the )?(?P<object>[a-z][a-z -]{2,40})",
    r"\b(?P<object>passenger car|suv|pickup truck|motorcycle|motorcyclist|van|cargo van|heavy truck|parked vehicle|vehicle)\s+lightly swiped\b",
    r"\b(?P<object>motorcyclist|motorcycle|passenger vehicle|passenger car|suv|pickup truck|pickup|van|cargo van|garbage can|vehicle)\b[^.]{0,140}\b(?:clipped|hit|swiped|rear ended|made contact)\b",
    r"\b(?:a|an|the)\s+(?P<object>passenger car|suv|pickup truck|motorcycle|van|heavy truck|parked vehicle|vehicle)\b[^.]{0,100}\b(?:made contact|struck|swiped|rear ended)\b",
    r"\bmade contact with (?:a |an |the )?(?P<object>[a-z][a-z -]{2,40})",
    r"\bcollided with (?:a |an |the )?(?P<object>[a-z][a-z -]{2,40})",
    r"\bstruck (?:a |an |the )?(?P<object>[a-z][a-z -]{2,40})",
)
_LOCATION_PATTERNS = (
    rf"\b(?:on|onto|at)\s+(?P<location>[A-Z][A-Za-z0-9 .'-]+{_ROAD_SUFFIX}"
    rf"(?:\s+near\s+[A-Z0-9][A-Za-z0-9 .'-]+{_ROAD_SUFFIX})?)",
    rf"\bnear\s+(?P<location>[A-Z0-9][A-Za-z0-9 .'-]+"
    rf"(?:{_ROAD_SUFFIX}|intersection))",
)


@dataclass(frozen=True)
class AutonomousVehicleFacts:
    collision_object: str | None = None
    location_context: str | None = None
    automation_state: str | None = None
    human_takeover: str | None = None
    injury_or_damage: str | None = None
    narrative_excerpt: str | None = None
    uncertainty_notes: list[str] | None = None


@dataclass(frozen=True)
class DetailQualityAssessment:
    detail_quality: DetailQuality
    detail_quality_reasons: list[str]
    source_fact_summary: str | None


@dataclass(frozen=True)
class AutonomousVehicleDetailCopy:
    incident_summary_en: str
    what_happened_en: str
    ai_failure_point_en: str
    why_it_matters_en: str
    evidence_summary_en: str

    def as_dict(self) -> dict[str, str]:
        return {
            "incident_summary_en": self.incident_summary_en,
            "what_happened_en": self.what_happened_en,
            "ai_failure_point_en": self.ai_failure_point_en,
            "why_it_matters_en": self.why_it_matters_en,
            "evidence_summary_en": self.evidence_summary_en,
        }


def extract_autonomous_vehicle_facts(text: str | None) -> AutonomousVehicleFacts:
    normalized = _normalize_text(text)
    if not normalized:
        return AutonomousVehicleFacts(uncertainty_notes=["missing_evidence_text"])

    collision_object = _first_match(normalized, _COLLISION_OBJECT_PATTERNS, "object")
    location_context = _first_match(normalized, _LOCATION_PATTERNS, "location")
    automation_state = _extract_automation_state(normalized)
    human_takeover = _extract_human_takeover(normalized)
    injury_or_damage = _extract_injury_or_damage(normalized)
    narrative_excerpt = _extract_narrative_excerpt(normalized)
    uncertainty_notes = []
    if collision_object is None:
        uncertainty_notes.append("missing_collision_object")
    if location_context is None:
        uncertainty_notes.append("missing_location_context")
    if automation_state is None:
        uncertainty_notes.append("missing_automation_state")
    if narrative_excerpt is None:
        uncertainty_notes.append("missing_narrative_excerpt")

    return AutonomousVehicleFacts(
        collision_object=collision_object,
        location_context=location_context,
        automation_state=automation_state,
        human_takeover=human_takeover,
        injury_or_damage=injury_or_damage,
        narrative_excerpt=narrative_excerpt,
        uncertainty_notes=uncertainty_notes,
    )


def summarize_autonomous_vehicle_facts(facts: AutonomousVehicleFacts) -> str | None:
    parts: list[str] = []
    if facts.collision_object:
        parts.append(f"collision object: {facts.collision_object}")
    if facts.location_context:
        parts.append(f"location: {facts.location_context}")
    if facts.automation_state:
        parts.append(f"automation state: {facts.automation_state}")
    if facts.human_takeover:
        parts.append(f"human takeover: {facts.human_takeover}")
    if facts.injury_or_damage:
        parts.append(f"impact: {facts.injury_or_damage}")
    if facts.narrative_excerpt:
        parts.append(f"narrative: {facts.narrative_excerpt}")
    return "; ".join(parts) if parts else None


def assess_autonomous_vehicle_detail_quality(
    incident: dict[str, Any],
) -> DetailQualityAssessment:
    if incident.get("source_family") != "autonomous_vehicle":
        return DetailQualityAssessment(
            detail_quality="not_applicable",
            detail_quality_reasons=[],
            source_fact_summary=None,
        )

    facts = _best_facts_from_sources(incident.get("sources", []))
    fact_reasons = list(facts.uncertainty_notes or [])
    field_reasons = []
    if _has_template_forensic_copy(incident):
        field_reasons.append("template_forensic_copy")
    if not _has_specific_field(incident.get("what_happened_en"), min_words=18):
        field_reasons.append("missing_what_happened")
    if not _has_specific_field(incident.get("ai_failure_point_en"), min_words=14):
        field_reasons.append("missing_ai_failure_point")
    if not _has_specific_field(incident.get("why_it_matters_en"), min_words=12):
        field_reasons.append("missing_why_it_matters")

    summary = summarize_autonomous_vehicle_facts(facts)
    reasons = field_reasons
    if field_reasons or summary is None:
        reasons = fact_reasons + field_reasons

    deduped_reasons = list(dict.fromkeys(reasons))
    if deduped_reasons:
        return DetailQualityAssessment(
            detail_quality="insufficient",
            detail_quality_reasons=deduped_reasons,
            source_fact_summary=summary,
        )
    return DetailQualityAssessment(
        detail_quality="sufficient",
        detail_quality_reasons=[],
        source_fact_summary=summary,
    )


def build_autonomous_vehicle_detail_copy(
    incident: dict[str, Any],
) -> AutonomousVehicleDetailCopy | None:
    if incident.get("source_family") != "autonomous_vehicle":
        return None

    facts = _best_facts_from_sources(incident.get("sources", []))
    if not summarize_autonomous_vehicle_facts(facts):
        return None

    company = str(incident.get("company_involved") or "The operator")
    incident_date = str(incident.get("date_logged") or "the reported date")
    location = facts.location_context or "the reported roadway location"
    impact = facts.injury_or_damage or "the report records the collision outcome"
    narrative = facts.narrative_excerpt or (
        f"The DMV report describes a collision involving {company} at {location}."
    )
    automation_state = facts.automation_state or "autonomous vehicle operation"

    return AutonomousVehicleDetailCopy(
        incident_summary_en=(
            f"California DMV records document a {company} autonomous-vehicle "
            f"collision on {incident_date} at {location}, with {impact}."
        ),
        what_happened_en=(
            f"According to the California DMV collision report, at {location}, "
            f"{narrative} "
            f"The filing identifies the vehicle as operating in {automation_state} "
            f"and records {impact}."
        ),
        ai_failure_point_en=(
            "The DMV filing does not establish a confirmed software defect; the "
            f"relevant automation question is how the autonomous vehicle handled "
            f"this road interaction at {location} while operating in "
            f"{automation_state}."
        ),
        why_it_matters_en=(
            "California DMV collision reports matter because they turn individual "
            "autonomous-vehicle road contacts into comparable public evidence for "
            "monitoring operator patterns, road-user interactions, locations, and "
            "real-world deployment edge cases."
        ),
        evidence_summary_en=(
            "Official California DMV autonomous vehicle collision report with "
            "date, time, location, involved-vehicle fields, damage or injury "
            "indicators, and a narrative description of the contact."
        ),
    )


def _best_facts_from_sources(sources: Any) -> AutonomousVehicleFacts:
    best = AutonomousVehicleFacts(uncertainty_notes=["missing_evidence_text"])
    best_score = -1
    for source in sources or []:
        if not isinstance(source, dict):
            continue
        facts = extract_autonomous_vehicle_facts(source.get("evidence_text"))
        score = sum(
            1
            for value in (
                facts.collision_object,
                facts.location_context,
                facts.automation_state,
                facts.human_takeover,
                facts.injury_or_damage,
                facts.narrative_excerpt,
            )
            if value
        )
        if score > best_score:
            best = facts
            best_score = score
    return best


def _normalize_text(text: str | None) -> str:
    return " ".join((text or "").replace("\x00", " ").split())


def _first_match(text: str, patterns: tuple[str, ...], group: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_phrase(match.group(group))
    return None


def _extract_automation_state(text: str) -> str | None:
    lowered = text.lower()
    if "autonomous mode" in lowered:
        return "autonomous mode"
    if "auto mode" in lowered:
        return "autonomous mode"
    if "automation engaged" in lowered:
        return "automation engaged"
    if "ads engaged" in lowered:
        return "ADS engaged"
    return None


def _extract_human_takeover(text: str) -> str | None:
    lowered = text.lower()
    if "manual control after impact" in lowered:
        return "manual control after impact"
    match = re.search(
        r"(?:took|assumed)\s+manual control(?:\s+[^.]{0,80})?",
        text,
        flags=re.IGNORECASE,
    )
    return _clean_phrase(match.group(0)) if match else None


def _extract_injury_or_damage(text: str) -> str | None:
    match = re.search(
        r"(No injuries were reported|no injuries reported|"
        r"minor vehicle damage(?: was noted)?|property damage[^.]{0,80})",
        text,
        flags=re.IGNORECASE,
    )
    return _clean_phrase(match.group(0)) if match else None


def _extract_narrative_excerpt(text: str) -> str | None:
    dmv_narrative = _extract_dmv_form_narrative(text)
    if dmv_narrative:
        return dmv_narrative

    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sentence in sentences:
        lowered = sentence.lower()
        if any(
            marker in lowered
            for marker in (
                "made contact",
                "collided with",
                "struck",
                "entered",
                "rear ended",
                "swiped",
                "clipped",
                "was hit",
            )
        ):
            return _clean_phrase(sentence)
    return None


def _extract_dmv_form_narrative(text: str) -> str | None:
    match = re.search(
        r"\b1:\s+(?P<narrative>(?:On|A|An|While|After)\b.+?)(?=\s+(?:2:|STATE_2|"
        r"INSURANCE|$))",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    narrative = _clean_phrase(match.group("narrative"))
    if not _looks_like_collision_narrative(narrative):
        return None

    sentences = re.split(r"(?<=[.!?])\s+", narrative)
    selected: list[str] = []
    for sentence in sentences:
        selected.append(sentence)
        if _looks_like_collision_narrative(" ".join(selected)):
            break
    return _clean_phrase(" ".join(selected))


def _looks_like_collision_narrative(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "made contact",
            "collided",
            "struck",
            "entered",
            "rear ended",
            "swiped",
            "clipped",
            "was hit",
            "collision",
        )
    )


def _has_template_forensic_copy(incident: dict[str, Any]) -> bool:
    text = " ".join(
        str(incident.get(key) or "")
        for key in (
            "what_happened_en",
            "ai_failure_point_en",
            "why_it_matters_en",
        )
    ).lower()
    return any(marker in text for marker in _TEMPLATE_MARKERS) or any(
        marker in text for marker in _GENERIC_FAILURE_MARKERS
    )


def _has_specific_field(value: Any, *, min_words: int) -> bool:
    text = _normalize_text(str(value or ""))
    if len(text.split()) < min_words:
        return False
    lowered = text.lower()
    return not any(marker in lowered for marker in _GENERIC_FAILURE_MARKERS)


def _clean_phrase(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .;:")
