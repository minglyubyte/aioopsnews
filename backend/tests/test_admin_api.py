from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.db.sqlite_repository import SQLiteIncidentRepository
from app.main import create_app
from app.scrapers.rss import RSSArticle


def _build_review_queue_client(
    database_path: Path,
    *,
    admin_api_token: str = "dev-admin-token",
) -> TestClient:
    repository = SQLiteIncidentRepository(f"sqlite:///{database_path}")
    repository.ingest_rss_article(
        RSSArticle(
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
    return TestClient(
        create_app(
            database_url=f"sqlite:///{database_path}",
            admin_api_token=admin_api_token,
        )
    )


def test_get_admin_review_queue_requires_admin_token(tmp_path: Path) -> None:
    client = _build_review_queue_client(
        tmp_path / "admin-auth-required.db",
        admin_api_token="secret-token",
    )

    response = client.get("/admin/incidents")

    assert response.status_code == 401
    assert response.json()["detail"] == "Admin access required"


def test_get_admin_review_queue_rejects_wrong_admin_token(tmp_path: Path) -> None:
    client = _build_review_queue_client(
        tmp_path / "admin-auth-invalid.db",
        admin_api_token="secret-token",
    )

    response = client.get(
        "/admin/incidents",
        headers={"X-Admin-Token": "wrong-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Admin access required"


def test_get_admin_review_queue_returns_pending_incidents(tmp_path: Path) -> None:
    client = _build_review_queue_client(
        tmp_path / "admin-queue.db",
        admin_api_token="secret-token",
    )

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


def test_patch_admin_incident_applies_editor_overrides(tmp_path: Path) -> None:
    database_path = tmp_path / "admin-update.db"
    client = _build_review_queue_client(
        database_path,
        admin_api_token="secret-token",
    )

    queue_response = client.get(
        "/admin/incidents",
        headers={"X-Admin-Token": "secret-token"},
    )
    incident_id = queue_response.json()["items"][0]["id"]

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
    assert payload["severity_score"] == 5
    assert payload["matched_claim_id"] == "claim-1"
    assert payload["review_notes"] == "Approved after editor verification."

    connection = sqlite3.connect(database_path)
    row = connection.execute(
        """
        select
            status,
            company_involved,
            claimant_name,
            categories,
            severity_score,
            reality_summary,
            matched_claim_id,
            claim_match_confidence,
            review_notes
        from incident_logs
        where id = ?
        """,
        (incident_id,),
    ).fetchone()
    connection.close()

    assert row == (
        "approved",
        "AssistCo",
        "AssistCo",
        '["Privacy/Security"]',
        5,
        "Editors confirmed the leak and approved the item.",
        "claim-1",
        0.95,
        "Approved after editor verification.",
    )
