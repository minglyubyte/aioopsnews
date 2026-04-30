from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def _build_test_database(database_path: Path) -> None:
    connection = sqlite3.connect(database_path)

    connection.executescript(
        """
        create table claims (
            id text primary key,
            claimant_name text not null,
            company_involved text not null,
            original_claim text not null,
            claim_date text not null,
            claim_topic text not null,
            status text not null
        );

        create table incident_logs (
            id text primary key,
            headline text not null,
            date_logged text not null,
            company_involved text not null,
            claimant_name text,
            categories text not null,
            severity_score integer not null,
            reality_summary text not null,
            status text not null,
            ingestion_run_id text,
            confidence_score real,
            review_notes text,
            matched_claim_id text references claims(id),
            claim_match_confidence real
        );

        create table incident_sources (
            id text primary key,
            incident_id text not null references incident_logs(id),
            source_url text not null,
            source_type text not null,
            publisher text,
            title text,
            published_at text,
            is_primary integer not null default 0
        );
        """
    )

    connection.execute(
        """
        insert into claims (
            id,
            claimant_name,
            company_involved,
            original_claim,
            claim_date,
            claim_topic,
            status
        ) values (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "claim-1",
            "FutureStack",
            "FutureStack",
            "Our copilots will eliminate tier-one support queues.",
            "2026-01-10",
            "job automation",
            "approved",
        ),
    )

    connection.executemany(
        """
        insert into incident_logs (
            id,
            headline,
            date_logged,
            company_involved,
            claimant_name,
            categories,
            severity_score,
            reality_summary,
            status,
            ingestion_run_id,
            confidence_score,
            review_notes,
            matched_claim_id,
            claim_match_confidence
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "incident-4",
                "May escalation shows archive filters can narrow results",
                "2026-05-03",
                "MayOps",
                "MayOps",
                json.dumps(["Model Governance"]),
                2,
                "A separate approved May incident supports archive filtering coverage.",
                "approved",
                "run-3",
                0.72,
                "editor reviewed",
                None,
                None,
            ),
            (
                "incident-1",
                "Database-backed feed shows a reviewed privacy incident",
                "2026-04-30",
                "FutureStack",
                "FutureStack",
                json.dumps(["Privacy/Security"]),
                4,
                "A reviewed database record leaked internal notes into replies.",
                "approved",
                "run-1",
                0.91,
                "editor reviewed",
                "claim-1",
                0.88,
            ),
            (
                "incident-2",
                "Warehouse robot rollback follows navigation failures",
                "2026-04-24",
                "RoboOps",
                "RoboOps",
                json.dumps(["Autonomous Systems"]),
                3,
                "Operators paused a pilot after repeated pathing failures.",
                "approved",
                "run-1",
                0.84,
                "editor reviewed",
                None,
                None,
            ),
            (
                "incident-5",
                "Prior-year incident proves year archives can narrow results",
                "2025-12-18",
                "ArchiveAI",
                "ArchiveAI",
                json.dumps(["Model Governance"]),
                2,
                (
                    "An older approved incident should only appear when the "
                    "matching archive year is selected."
                ),
                "approved",
                "run-0",
                0.66,
                "editor reviewed",
                None,
                None,
            ),
            (
                "incident-3",
                "Draft incident should not be public",
                "2026-04-20",
                "HiddenCo",
                "HiddenCo",
                json.dumps(["Missed Timelines"]),
                2,
                "Draft only.",
                "pending_review",
                "run-2",
                0.51,
                "awaiting editor",
                None,
                None,
            ),
        ],
    )

    connection.executemany(
        """
        insert into incident_sources (
            id,
            incident_id,
            source_url,
            source_type,
            publisher,
            title,
            published_at,
            is_primary
        ) values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "source-1",
                "incident-1",
                "https://example.com/privacy",
                "primary",
                "Example News",
                "Database-backed feed shows a reviewed privacy incident",
                "2026-04-30T08:00:00",
                1,
            ),
            (
                "source-2",
                "incident-2",
                "https://example.com/robotics",
                "primary",
                "City Ledger",
                "Warehouse robot rollback follows navigation failures",
                "2026-04-24T08:00:00",
                1,
            ),
        ],
    )

    connection.commit()
    connection.close()


def test_get_incidents_reads_from_database_records(tmp_path: Path) -> None:
    database_path = tmp_path / "incidents.db"
    _build_test_database(database_path)
    client = TestClient(create_app(database_url=f"sqlite:///{database_path}"))

    response = client.get("/incidents")

    assert response.status_code == 200

    payload = response.json()

    assert [item["headline"] for item in payload["items"]] == [
        "May escalation shows archive filters can narrow results",
        "Database-backed feed shows a reviewed privacy incident",
        "Warehouse robot rollback follows navigation failures",
        "Prior-year incident proves year archives can narrow results",
    ]
    assert all(item["status"] == "approved" for item in payload["items"])
    assert (
        payload["items"][1]["sources"][0]["source_url"] == "https://example.com/privacy"
    )
    assert payload["items"][1]["matched_claim"] == {
        "id": "claim-1",
        "claimant_name": "FutureStack",
        "company_involved": "FutureStack",
        "original_claim": "Our copilots will eliminate tier-one support queues.",
        "claim_date": "2026-01-10",
        "claim_topic": "job automation",
        "match_confidence": 0.88,
    }
    assert payload["items"][0]["matched_claim"] is None


def test_get_incidents_supports_filters_and_pagination(tmp_path: Path) -> None:
    database_path = tmp_path / "filtered-incidents.db"
    _build_test_database(database_path)
    client = TestClient(create_app(database_url=f"sqlite:///{database_path}"))

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


def test_get_incidents_supports_year_and_month_archives(tmp_path: Path) -> None:
    database_path = tmp_path / "archived-incidents.db"
    _build_test_database(database_path)
    client = TestClient(create_app(database_url=f"sqlite:///{database_path}"))

    yearly_response = client.get("/incidents", params={"year": 2026})
    monthly_response = client.get("/incidents", params={"year": 2026, "month": 4})
    category_archive_response = client.get(
        "/incidents",
        params={"year": 2026, "month": 4, "category": "Privacy/Security"},
    )

    assert yearly_response.status_code == 200
    assert [item["headline"] for item in yearly_response.json()["items"]] == [
        "May escalation shows archive filters can narrow results",
        "Database-backed feed shows a reviewed privacy incident",
        "Warehouse robot rollback follows navigation failures",
    ]

    assert monthly_response.status_code == 200
    assert [item["headline"] for item in monthly_response.json()["items"]] == [
        "Database-backed feed shows a reviewed privacy incident",
        "Warehouse robot rollback follows navigation failures",
    ]

    assert category_archive_response.status_code == 200
    assert [item["headline"] for item in category_archive_response.json()["items"]] == [
        "Database-backed feed shows a reviewed privacy incident",
    ]


def test_get_incidents_rejects_month_without_year_or_invalid_month(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "invalid-archive-incidents.db"
    _build_test_database(database_path)
    client = TestClient(create_app(database_url=f"sqlite:///{database_path}"))

    month_only_response = client.get("/incidents", params={"month": 4})
    invalid_month_response = client.get(
        "/incidents",
        params={"year": 2026, "month": 13},
    )

    assert month_only_response.status_code == 422
    assert invalid_month_response.status_code == 422


def test_get_incident_detail_returns_public_record_with_sources(tmp_path: Path) -> None:
    database_path = tmp_path / "incident-detail.db"
    _build_test_database(database_path)
    client = TestClient(create_app(database_url=f"sqlite:///{database_path}"))

    detail_response = client.get("/incidents/incident-1")
    hidden_response = client.get("/incidents/incident-3")

    assert detail_response.status_code == 200
    assert detail_response.json()["headline"] == (
        "Database-backed feed shows a reviewed privacy incident"
    )
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


def test_get_filters_reads_distinct_values_from_database(tmp_path: Path) -> None:
    database_path = tmp_path / "filters.db"
    _build_test_database(database_path)
    client = TestClient(create_app(database_url=f"sqlite:///{database_path}"))

    response = client.get("/filters")

    assert response.status_code == 200
    assert response.json() == {
        "categories": [
            "Autonomous Systems",
            "Model Governance",
            "Privacy/Security",
        ],
        "claimants": [
            "ArchiveAI",
            "FutureStack",
            "MayOps",
            "RoboOps",
        ],
        "companies": [
            "ArchiveAI",
            "FutureStack",
            "MayOps",
            "RoboOps",
        ],
        "years": [2026, 2025],
        "months_by_year": {
            "2026": [5, 4],
            "2025": [12],
        },
    }


def test_empty_sqlite_database_bootstraps_seed_data(tmp_path: Path) -> None:
    database_path = tmp_path / "bootstrap.db"
    client = TestClient(create_app(database_url=f"sqlite:///{database_path}"))

    response = client.get("/incidents")

    assert response.status_code == 200
    assert response.json()["items"]
