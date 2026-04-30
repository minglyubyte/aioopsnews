from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.app_factory import create_app
from app.scrapers.rss import RSSArticle
from tests.fakes import InMemoryIncidentRepository

ASSISTCO_CLAIM = "Our assistant will eliminate repetitive support escalations."


def _build_review_queue_client(
    *,
    admin_api_token: str = "dev-admin-token",
) -> tuple[TestClient, InMemoryIncidentRepository]:
    repository = InMemoryIncidentRepository(
        claims=[
            {
                "id": "claim-1",
                "claimant_name": "AssistCo",
                "company_involved": "AssistCo",
                "original_claim": ASSISTCO_CLAIM,
                "claim_date": "2026-01-15",
                "claim_topic": "job automation",
                "status": "approved",
                "notes": None,
            }
        ]
    )
    repository.ingest_rss_article(
        article=RSSArticle(
            source_key="test-source",
            publisher="Example News",
            title="AssistCo assistant exposes billing notes",
            url="https://example.com/articles/assistco-billing-notes",
            summary=(
                "A support assistant exposed private billing notes in "
                "customer-facing replies."
            ),
            published_at=datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc),
            source_type="secondary",
        ),
        ingestion_run_id="run-2026-05-01",
    )
    client = TestClient(
        create_app(
            admin_api_token=admin_api_token,
            incident_repository=repository,
        )
    )
    return client, repository


def test_get_admin_review_queue_requires_admin_token() -> None:
    client, _repository = _build_review_queue_client(admin_api_token="secret-token")

    response = client.get("/admin/incidents")

    assert response.status_code == 401
    assert response.json()["detail"] == "Admin access required"


def test_get_admin_review_queue_rejects_wrong_admin_token() -> None:
    client, _repository = _build_review_queue_client(admin_api_token="secret-token")

    response = client.get(
        "/admin/incidents",
        headers={"X-Admin-Token": "wrong-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Admin access required"


def test_get_admin_review_queue_returns_pending_incidents() -> None:
    client, _repository = _build_review_queue_client(admin_api_token="secret-token")

    response = client.get(
        "/admin/incidents",
        headers={"X-Admin-Token": "secret-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert all(item["status"] == "pending_review" for item in payload["items"])
    assert payload["items"][0]["headline"] == "AssistCo assistant exposes billing notes"
    assert payload["items"][0]["sources"][0]["source_url"].endswith(
        "/assistco-billing-notes"
    )


def test_patch_admin_incident_applies_editor_overrides() -> None:
    client, repository = _build_review_queue_client(admin_api_token="secret-token")
    incident_id = repository.list_review_queue()[0]["id"]

    response = client.patch(
        f"/admin/incidents/{incident_id}",
        headers={"X-Admin-Token": "secret-token"},
        json={
            "status": "approved",
            "company_involved": "AssistCo",
            "claimant_name": "AssistCo",
            "categories": ["Privacy/Security"],
            "severity_score": 5,
            "reality_summary": "Editors confirmed the leak and approved the item.",
            "matched_claim_id": "claim-1",
            "claim_match_confidence": 0.95,
            "review_notes": "Approved after editor verification.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "approved"
    assert payload["matched_claim_id"] == "claim-1"
    assert repository.incidents[incident_id]["review_notes"] == (
        "Approved after editor verification."
    )
