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
        "Database-backed feed shows a reviewed privacy incident",
        "Warehouse robot rollback follows navigation failures",
    ]
    assert all(item["status"] == "approved" for item in payload["items"])
    assert (
        payload["items"][0]["sources"][0]["source_url"] == "https://example.com/privacy"
    )


def test_get_filters_reads_distinct_values_from_database(tmp_path: Path) -> None:
    database_path = tmp_path / "filters.db"
    _build_test_database(database_path)
    client = TestClient(create_app(database_url=f"sqlite:///{database_path}"))

    response = client.get("/filters")

    assert response.status_code == 200
    assert response.json() == {
        "categories": [
            "Autonomous Systems",
            "Privacy/Security",
        ],
        "claimants": [
            "FutureStack",
            "RoboOps",
        ],
        "companies": [
            "FutureStack",
            "RoboOps",
        ],
    }


def test_empty_sqlite_database_bootstraps_seed_data(tmp_path: Path) -> None:
    database_path = tmp_path / "bootstrap.db"
    client = TestClient(create_app(database_url=f"sqlite:///{database_path}"))

    response = client.get("/incidents")

    assert response.status_code == 200
    assert response.json()["items"]
