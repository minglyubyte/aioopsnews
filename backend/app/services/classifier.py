from __future__ import annotations

import re
from dataclasses import dataclass


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
            categories=["Privacy/Security"],
            severity_score=4,
            confidence_score=0.87,
        )

    if any(
        keyword in combined_text
        for keyword in ["robot", "pilot", "sidewalk", "autonomous"]
    ):
        return IncidentClassification(
            company_involved=company_involved,
            categories=["Autonomous Systems"],
            severity_score=3,
            confidence_score=0.82,
        )

    if any(keyword in combined_text for keyword in ["timeline", "delay", "late"]):
        return IncidentClassification(
            company_involved=company_involved,
            categories=["Missed Timelines"],
            severity_score=2,
            confidence_score=0.74,
        )

    return IncidentClassification(
        company_involved=company_involved,
        categories=["Hallucinations"],
        severity_score=2,
        confidence_score=0.61,
    )
