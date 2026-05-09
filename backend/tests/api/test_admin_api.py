from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.app_factory import create_app
from app.scrapers.rss import RSSArticle
from app.services.incident_translation import IncidentTranslation
from tests.support.fakes import InMemoryIncidentRepository

ASSISTCO_CLAIM = "Our assistant will eliminate repetitive support escalations."


class StaticTranslationClient:
    def translate(
        self,
        *,
        headline_en: str,
        reality_summary_en: str,
        legitimacy_reasoning_en: str,
        source_validation_summary_en: str,
        company_involved_en: str,
        incident_summary_en: str = "",
        what_happened_en: str = "",
        ai_failure_point_en: str = "",
        why_it_matters_en: str = "",
        evidence_summary_en: str = "",
    ) -> IncidentTranslation:
        return IncidentTranslation(
            headline_zh=f"ZH:{headline_en}",
            reality_summary_zh=f"ZH:{reality_summary_en}",
            legitimacy_reasoning_zh=f"ZH:{legitimacy_reasoning_en}",
            source_validation_summary_zh=f"ZH:{source_validation_summary_en}",
            company_involved_zh=f"ZH:{company_involved_en}",
            incident_summary_zh=f"ZH:{incident_summary_en}",
            what_happened_zh=f"ZH:{what_happened_en}",
            ai_failure_point_zh=f"ZH:{ai_failure_point_en}",
            why_it_matters_zh=f"ZH:{why_it_matters_en}",
            evidence_summary_zh=f"ZH:{evidence_summary_en}",
        )


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
            incident_translation_client=StaticTranslationClient(),
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
    assert payload["items"][0]["translation_status"] == "not_requested"
    assert payload["items"][0]["legitimacy_score"] is None
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
    assert payload["translation_status"] == "completed"
    assert payload["company_involved_zh"] == "ZH:AssistCo"
    assert payload["headline_zh"] == "ZH:AssistCo assistant exposes billing notes"
    assert repository.incidents[incident_id]["review_notes"] == (
        "Approved after editor verification."
    )


def test_patch_admin_incident_translates_forensic_analysis_fields() -> None:
    client, repository = _build_review_queue_client(admin_api_token="secret-token")
    incident_id = repository.list_review_queue()[0]["id"]
    repository.incidents[incident_id].update(
        {
            "incident_summary_en": "The support assistant leaked billing notes.",
            "what_happened_en": "The assistant inserted private billing notes.",
            "ai_failure_point_en": "The model failed to separate internal context.",
            "why_it_matters_en": "Customers saw information meant for staff.",
            "evidence_summary_en": "The incident was confirmed by source logs.",
        }
    )

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
    assert payload["translation_status"] == "completed"
    assert payload["analysis"]["incident_summary_zh"] == (
        "ZH:The support assistant leaked billing notes."
    )
    assert payload["analysis"]["what_happened_zh"] == (
        "ZH:The assistant inserted private billing notes."
    )
    assert payload["analysis"]["ai_failure_point_zh"] == (
        "ZH:The model failed to separate internal context."
    )
    assert payload["analysis"]["why_it_matters_zh"] == (
        "ZH:Customers saw information meant for staff."
    )
    assert payload["analysis"]["evidence_summary_zh"] == (
        "ZH:The incident was confirmed by source logs."
    )


def test_patch_admin_incident_retranslates_already_approved_incident() -> None:
    client, repository = _build_review_queue_client(admin_api_token="secret-token")
    incident_id = repository.list_review_queue()[0]["id"]

    first_response = client.patch(
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
    assert first_response.status_code == 200

    response = client.patch(
        f"/admin/incidents/{incident_id}",
        headers={"X-Admin-Token": "secret-token"},
        json={
            "status": "approved",
            "company_involved": "AssistCo Labs",
            "claimant_name": "AssistCo Labs",
            "categories": ["Privacy/Security"],
            "severity_score": 4,
            "reality_summary": "Editors revised the summary after a follow-up check.",
            "matched_claim_id": "claim-1",
            "claim_match_confidence": 0.96,
            "review_notes": "Approved after a second editor pass.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "approved"
    assert payload["company_involved"] == "AssistCo Labs"
    assert payload["company_involved_zh"] == "ZH:AssistCo Labs"
    assert payload["reality_summary"] == (
        "Editors revised the summary after a follow-up check."
    )
    assert payload["reality_summary_zh"] == (
        "ZH:Editors revised the summary after a follow-up check."
    )


def test_upgrade_watch_news_to_accident_moves_same_record_into_llm_review() -> None:
    repository = InMemoryIncidentRepository(
        incidents=[
            {
                "id": "incident-news",
                "external_id": "news:https://example.com/ai-news",
                "headline": "AI news item from search discovery",
                "headline_en": "AI news item from search discovery",
                "headline_zh": None,
                "date_logged": "2026-05-06",
                "company_involved": "Pending classification",
                "incident_topic": "coding_failure",
                "claimant_name": None,
                "categories": [],
                "severity_score": 1,
                "reality_summary": "Search found a fresh report about an AI failure.",
                "reality_summary_en": (
                    "Search found a fresh report about an AI failure."
                ),
                "reality_summary_zh": None,
                "status": "approved",
                "translation_status": "not_requested",
                "publication_track": "accident_watch",
                "evidence_tier": "reported_unconfirmed",
                "source_family": "coding_failure",
                "verification_summary": (
                    "Search discovery found a fresh AI news signal; it is not "
                    "a verified accident."
                ),
                "matched_claim_id": None,
                "claim_match_confidence": None,
                "review_notes": "Auto-published from daily news discovery.",
                "sources": [
                    {
                        "id": "source-news",
                        "source_url": "https://example.com/ai-news",
                        "source_type": "secondary",
                        "source_origin": "search_discovery",
                        "source_registry_key": "brave_news_search",
                        "raw_source_payload": {
                            "query": "AI coding failure production outage"
                        },
                        "publisher": "Example News",
                        "title": "AI news item from search discovery",
                    }
                ],
            }
        ]
    )
    client = TestClient(
        create_app(
            admin_api_token="secret-token",
            incident_repository=repository,
            incident_translation_client=StaticTranslationClient(),
        )
    )

    response = client.post(
        "/admin/incidents/incident-news/upgrade-to-accident",
        headers={"X-Admin-Token": "secret-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "incident-news"
    assert payload["status"] == "pending_llm_review"
    assert payload["publication_track"] == "verified_accident"
    assert payload["evidence_tier"] == "developing"
    assert payload["source_family"] == "coding_failure"
    assert payload["sources"][0]["source_origin"] == "search_discovery"
    assert payload["sources"][0]["source_registry_key"] == "brave_news_search"
    assert repository.get_public_incident("incident-news") is None
    assert repository.list_incidents_pending_llm_review()[0]["id"] == "incident-news"


def test_upgrade_watch_news_to_accident_requires_admin_token() -> None:
    client, _repository = _build_review_queue_client(admin_api_token="secret-token")

    response = client.post("/admin/incidents/incident-1/upgrade-to-accident")

    assert response.status_code == 401
