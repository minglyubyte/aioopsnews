from __future__ import annotations

from fastapi.testclient import TestClient

from app.app_factory import create_app
from tests.fakes import InMemoryIncidentRepository

FUTURESTACK_CLAIM = "Our copilots will eliminate tier-one support queues."


def _build_repository() -> InMemoryIncidentRepository:
    return InMemoryIncidentRepository(
        claims=[
            {
                "id": "claim-1",
                "claimant_name": "FutureStack",
                "company_involved": "FutureStack",
                "original_claim": FUTURESTACK_CLAIM,
                "claim_date": "2026-01-10",
                "claim_topic": "job automation",
                "status": "approved",
                "notes": "Imported from launch blog.",
            }
        ],
        incidents=[
            {
                "id": "incident-4",
                "headline": "May escalation shows archive filters can narrow results",
                "headline_en": (
                    "May escalation shows archive filters can narrow results"
                ),
                "headline_zh": None,
                "date_logged": "2026-05-03",
                "company_involved": "MayOps",
                "incident_topic": "model governance",
                "claimant_name": "MayOps",
                "categories": ["Model Governance"],
                "severity_score": 2,
                "reality_summary": (
                    "A separate approved May incident supports archive "
                    "filtering coverage."
                ),
                "reality_summary_en": (
                    "A separate approved May incident supports archive "
                    "filtering coverage."
                ),
                "reality_summary_zh": None,
                "status": "approved",
                "translation_status": "not_requested",
                "matched_claim_id": None,
                "claim_match_confidence": None,
                "review_notes": "editor reviewed",
                "sources": [],
            },
            {
                "id": "incident-1",
                "headline": "Database-backed feed shows a reviewed privacy incident",
                "headline_en": "Database-backed feed shows a reviewed privacy incident",
                "headline_zh": "数据库支持的隐私事件已完成审核",
                "date_logged": "2026-04-30",
                "company_involved": "FutureStack",
                "incident_topic": "privacy",
                "claimant_name": "FutureStack",
                "categories": ["Privacy/Security"],
                "severity_score": 4,
                "reality_summary": (
                    "A reviewed database record leaked internal notes into replies."
                ),
                "reality_summary_en": (
                    "A reviewed database record leaked internal notes into replies."
                ),
                "reality_summary_zh": "经审核的数据库记录将内部备注泄露到回复中。",
                "status": "approved",
                "translation_status": "completed",
                "matched_claim_id": "claim-1",
                "claim_match_confidence": 0.88,
                "review_notes": "editor reviewed",
                "sources": [
                    {
                        "id": "source-1",
                        "source_url": "https://example.com/privacy",
                        "source_type": "primary",
                        "publisher": "Example News",
                        "title": (
                            "Database-backed feed shows a reviewed privacy incident"
                        ),
                    }
                ],
            },
            {
                "id": "incident-2",
                "headline": "Warehouse robot rollback follows navigation failures",
                "headline_en": "Warehouse robot rollback follows navigation failures",
                "headline_zh": None,
                "date_logged": "2026-04-24",
                "company_involved": "RoboOps",
                "incident_topic": "autonomous systems",
                "claimant_name": "RoboOps",
                "categories": ["Autonomous Systems"],
                "severity_score": 3,
                "reality_summary": (
                    "Operators paused a pilot after repeated pathing failures."
                ),
                "reality_summary_en": (
                    "Operators paused a pilot after repeated pathing failures."
                ),
                "reality_summary_zh": None,
                "status": "approved",
                "translation_status": "not_requested",
                "matched_claim_id": None,
                "claim_match_confidence": None,
                "review_notes": "editor reviewed",
                "sources": [
                    {
                        "id": "source-2",
                        "source_url": "https://example.com/robotics",
                        "source_type": "primary",
                        "publisher": "City Ledger",
                        "title": "Warehouse robot rollback follows navigation failures",
                    }
                ],
            },
            {
                "id": "incident-5",
                "headline": (
                    "Prior-year incident proves year archives can narrow results"
                ),
                "headline_en": (
                    "Prior-year incident proves year archives can narrow results"
                ),
                "headline_zh": None,
                "date_logged": "2025-12-18",
                "company_involved": "ArchiveAI",
                "incident_topic": "model governance",
                "claimant_name": "ArchiveAI",
                "categories": ["Model Governance"],
                "severity_score": 2,
                "reality_summary": (
                    "An older approved incident should only appear for matching "
                    "archive years."
                ),
                "reality_summary_en": (
                    "An older approved incident should only appear for matching "
                    "archive years."
                ),
                "reality_summary_zh": None,
                "status": "approved",
                "translation_status": "not_requested",
                "matched_claim_id": None,
                "claim_match_confidence": None,
                "review_notes": "editor reviewed",
                "sources": [],
            },
            {
                "id": "incident-3",
                "headline": "Draft incident should not be public",
                "headline_en": "Draft incident should not be public",
                "headline_zh": None,
                "date_logged": "2026-04-20",
                "company_involved": "HiddenCo",
                "incident_topic": "missed timelines",
                "claimant_name": "HiddenCo",
                "categories": ["Missed Timelines"],
                "severity_score": 2,
                "reality_summary": "Draft only.",
                "reality_summary_en": "Draft only.",
                "reality_summary_zh": None,
                "status": "pending_review",
                "translation_status": "not_requested",
                "matched_claim_id": None,
                "claim_match_confidence": None,
                "review_notes": "awaiting editor",
                "sources": [],
            },
        ],
    )


def test_get_incidents_reads_from_repository_records() -> None:
    repository = _build_repository()
    client = TestClient(create_app(incident_repository=repository))

    response = client.get("/incidents")

    assert response.status_code == 200
    payload = response.json()
    assert [item["headline"] for item in payload["items"]] == [
        "May escalation shows archive filters can narrow results",
        "Database-backed feed shows a reviewed privacy incident",
        "Warehouse robot rollback follows navigation failures",
        "Prior-year incident proves year archives can narrow results",
    ]
    assert payload["items"][1]["matched_claim"] == {
        "id": "claim-1",
        "claimant_name": "FutureStack",
        "company_involved": "FutureStack",
        "original_claim": "Our copilots will eliminate tier-one support queues.",
        "claim_date": "2026-01-10",
        "claim_topic": "job automation",
        "match_confidence": 0.88,
    }
    assert payload["items"][1]["headline_en"] == (
        "Database-backed feed shows a reviewed privacy incident"
    )
    assert payload["items"][1]["headline_zh"] == "数据库支持的隐私事件已完成审核"
    assert payload["items"][1]["translation_status"] == "completed"


def test_get_incidents_supports_filters_and_pagination() -> None:
    repository = _build_repository()
    client = TestClient(create_app(incident_repository=repository))

    filtered_response = client.get(
        "/incidents",
        params={
            "category": "Privacy/Security",
            "company": "FutureStack",
            "claimant": "FutureStack",
            "severity_min": 4,
            "severity_max": 5,
        },
    )
    paged_response = client.get("/incidents", params={"page": 2, "page_size": 1})

    assert filtered_response.status_code == 200
    assert [item["headline"] for item in filtered_response.json()["items"]] == [
        "Database-backed feed shows a reviewed privacy incident",
    ]
    assert paged_response.status_code == 200
    assert [item["headline"] for item in paged_response.json()["items"]] == [
        "Database-backed feed shows a reviewed privacy incident",
    ]


def test_get_incidents_supports_year_and_month_archives() -> None:
    repository = _build_repository()
    client = TestClient(create_app(incident_repository=repository))

    yearly_response = client.get("/incidents", params={"year": 2026})
    monthly_response = client.get("/incidents", params={"year": 2026, "month": 4})
    category_archive_response = client.get(
        "/incidents",
        params={"year": 2026, "month": 4, "category": "Privacy/Security"},
    )

    assert [item["headline"] for item in yearly_response.json()["items"]] == [
        "May escalation shows archive filters can narrow results",
        "Database-backed feed shows a reviewed privacy incident",
        "Warehouse robot rollback follows navigation failures",
    ]
    assert [item["headline"] for item in monthly_response.json()["items"]] == [
        "Database-backed feed shows a reviewed privacy incident",
        "Warehouse robot rollback follows navigation failures",
    ]
    assert [item["headline"] for item in category_archive_response.json()["items"]] == [
        "Database-backed feed shows a reviewed privacy incident",
    ]


def test_get_incidents_rejects_month_without_year_or_invalid_month() -> None:
    repository = _build_repository()
    client = TestClient(create_app(incident_repository=repository))

    assert client.get("/incidents", params={"month": 4}).status_code == 422
    assert (
        client.get("/incidents", params={"year": 2026, "month": 13}).status_code == 422
    )


def test_get_incident_detail_returns_public_record_with_sources() -> None:
    repository = _build_repository()
    client = TestClient(create_app(incident_repository=repository))

    detail_response = client.get("/incidents/incident-1")
    hidden_response = client.get("/incidents/incident-3")

    assert detail_response.status_code == 200
    assert detail_response.json()["headline_en"] == (
        "Database-backed feed shows a reviewed privacy incident"
    )
    assert detail_response.json()["headline_zh"] == "数据库支持的隐私事件已完成审核"
    assert detail_response.json()["sources"] == [
        {
            "id": "source-1",
            "source_url": "https://example.com/privacy",
            "source_type": "primary",
            "publisher": "Example News",
            "title": "Database-backed feed shows a reviewed privacy incident",
        }
    ]
    assert hidden_response.status_code == 404


def test_get_filters_reads_distinct_values_from_repository() -> None:
    repository = _build_repository()
    client = TestClient(create_app(incident_repository=repository))

    response = client.get("/filters")

    assert response.status_code == 200
    assert response.json() == {
        "categories": [
            "Autonomous Systems",
            "Model Governance",
            "Privacy/Security",
        ],
        "claimants": ["ArchiveAI", "FutureStack", "MayOps", "RoboOps"],
        "companies": ["ArchiveAI", "FutureStack", "MayOps", "RoboOps"],
        "years": [2026, 2025],
        "months_by_year": {
            "2026": [5, 4],
            "2025": [12],
        },
    }
