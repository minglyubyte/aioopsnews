from __future__ import annotations

from datetime import date
from typing import Any

_PUBLIC_INCIDENTS: list[dict[str, Any]] = [
    {
        "id": "incident-1",
        "headline": "Customer support bot exposes private account notes",
        "date_logged": date(2026, 4, 29),
        "company_involved": "AssistCo",
        "claimant_name": "AssistCo",
        "categories": ["Privacy/Security"],
        "severity_score": 4,
        "reality_summary": (
            "A support automation rollout leaked internal notes into user-facing "
            "replies before the company disabled the feature."
        ),
        "status": "approved",
        "sources": [
            {
                "id": "source-1",
                "source_url": "https://example.com/privacy-story",
                "source_type": "primary",
                "publisher": "Example News",
                "title": "Customer support bot exposes private account notes",
            }
        ],
    },
    {
        "id": "incident-2",
        "headline": "Delivery robot pilot stalls after safety interventions",
        "date_logged": date(2026, 4, 21),
        "company_involved": "RoboFleet",
        "claimant_name": "RoboFleet",
        "categories": ["Autonomous Systems"],
        "severity_score": 3,
        "reality_summary": (
            "Repeated sidewalk interventions forced the company to pause the pilot "
            "and return to supervised operations."
        ),
        "status": "approved",
        "sources": [
            {
                "id": "source-2",
                "source_url": "https://example.com/robot-pilot",
                "source_type": "primary",
                "publisher": "City Ledger",
                "title": "Delivery robot pilot stalls after safety interventions",
            }
        ],
    },
    {
        "id": "incident-3",
        "headline": "Internal classifier disagreement flagged for review",
        "date_logged": date(2026, 4, 20),
        "company_involved": "SignalLoop",
        "claimant_name": "SignalLoop",
        "categories": ["Missed Timelines"],
        "severity_score": 2,
        "reality_summary": "This draft incident is not public yet.",
        "status": "pending_review",
        "sources": [],
    },
]


def list_public_incidents() -> list[dict[str, Any]]:
    public_items = [item for item in _PUBLIC_INCIDENTS if item["status"] == "approved"]
    public_items.sort(key=lambda item: item["date_logged"], reverse=True)

    return [
        {
            **item,
            "date_logged": item["date_logged"].isoformat(),
        }
        for item in public_items
    ]


def get_filter_values() -> dict[str, list[str]]:
    incidents = list_public_incidents()

    categories = sorted(
        {category for item in incidents for category in item["categories"]}
    )
    claimants = sorted(
        {item["claimant_name"] for item in incidents if item["claimant_name"]}
    )
    companies = sorted({item["company_involved"] for item in incidents})

    return {
        "categories": categories,
        "claimants": claimants,
        "companies": companies,
    }
