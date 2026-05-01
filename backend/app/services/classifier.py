from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.incident_taxonomy import (
    CATEGORY_AUTONOMOUS_SYSTEMS,
    CATEGORY_HALLUCINATIONS,
    CATEGORY_MISSED_TIMELINES,
    CATEGORY_PRIVACY_SECURITY,
)


@dataclass(frozen=True)
class IncidentClassification:
    company_involved: str
    categories: list[str]
    severity_score: int
    confidence_score: float


def classify_incident(*, headline: str, source_summary: str) -> IncidentClassification:
    combined_text = f"{headline} {source_summary}".lower()

    company_match = re.match(r"([A-Z][A-Za-z0-9]+)", headline)
    company_involved = (
        company_match.group(1)
        if company_match is not None
        else "Pending classification"
    )

    if any(
        keyword in combined_text
        for keyword in ["privacy", "private", "leak", "account notes"]
    ):
        return IncidentClassification(
            company_involved=company_involved,
            categories=[CATEGORY_PRIVACY_SECURITY],
            severity_score=4,
            confidence_score=0.87,
        )

    if any(
        keyword in combined_text
        for keyword in ["robot", "pilot", "sidewalk", "autonomous"]
    ):
        return IncidentClassification(
            company_involved=company_involved,
            categories=[CATEGORY_AUTONOMOUS_SYSTEMS],
            severity_score=3,
            confidence_score=0.82,
        )

    if any(keyword in combined_text for keyword in ["timeline", "delay", "late"]):
        return IncidentClassification(
            company_involved=company_involved,
            categories=[CATEGORY_MISSED_TIMELINES],
            severity_score=2,
            confidence_score=0.74,
        )

    return IncidentClassification(
        company_involved=company_involved,
        categories=[CATEGORY_HALLUCINATIONS],
        severity_score=2,
        confidence_score=0.61,
    )
