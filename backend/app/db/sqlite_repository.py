from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

_SQLITE_SCHEMA = """
create table if not exists claims (
    id text primary key,
    claimant_name text not null,
    company_involved text not null,
    original_claim text not null,
    claim_date text not null,
    claim_topic text not null,
    status text not null,
    created_at text default current_timestamp,
    updated_at text default current_timestamp
);

create table if not exists incident_logs (
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
    claim_match_confidence real,
    created_at text default current_timestamp,
    updated_at text default current_timestamp
);

create table if not exists incident_sources (
    id text primary key,
    incident_id text not null references incident_logs(id) on delete cascade,
    source_url text not null,
    source_type text not null,
    publisher text,
    title text,
    published_at text,
    is_primary integer not null default 0,
    created_at text default current_timestamp
);
"""

_SEED_CLAIMS: list[tuple[str, str, str, str, str, str, str]] = [
    (
        "claim-1",
        "AssistCo",
        "AssistCo",
        "Our assistant will eliminate repetitive support escalations.",
        "2026-01-15",
        "job automation",
        "approved",
    ),
]

_SEED_INCIDENTS: list[tuple[Any, ...]] = [
    (
        "incident-1",
        "Customer support bot exposes private account notes",
        "2026-04-29",
        "AssistCo",
        "AssistCo",
        json.dumps(["Privacy/Security"]),
        4,
        (
            "A support automation rollout leaked internal notes into user-facing "
            "replies before the company disabled the feature."
        ),
        "approved",
        "run-seed-1",
        0.91,
        "reviewed",
        "claim-1",
        0.88,
    ),
    (
        "incident-2",
        "Delivery robot pilot stalls after safety interventions",
        "2026-04-21",
        "RoboFleet",
        "RoboFleet",
        json.dumps(["Autonomous Systems"]),
        3,
        (
            "Repeated sidewalk interventions forced the company to pause the "
            "pilot and return to supervised operations."
        ),
        "approved",
        "run-seed-1",
        0.84,
        "reviewed",
        None,
        None,
    ),
    (
        "incident-3",
        "Internal classifier disagreement flagged for review",
        "2026-04-20",
        "SignalLoop",
        "SignalLoop",
        json.dumps(["Missed Timelines"]),
        2,
        "This draft incident is not public yet.",
        "pending_review",
        "run-seed-2",
        0.51,
        "awaiting review",
        None,
        None,
    ),
]

_SEED_SOURCES: list[tuple[Any, ...]] = [
    (
        "source-1",
        "incident-1",
        "https://example.com/privacy-story",
        "primary",
        "Example News",
        "Customer support bot exposes private account notes",
        "2026-04-29T08:00:00",
        1,
    ),
    (
        "source-2",
        "incident-2",
        "https://example.com/robot-pilot",
        "primary",
        "City Ledger",
        "Delivery robot pilot stalls after safety interventions",
        "2026-04-21T08:00:00",
        1,
    ),
]


class SQLiteIncidentRepository:
    def __init__(self, database_url: str) -> None:
        if not database_url.startswith("sqlite:///"):
            raise ValueError(
                "Only sqlite:/// DATABASE_URL values are supported right now."
            )

        self._database_path = Path(database_url.removeprefix("sqlite:///"))
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def list_public_incidents(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            incident_rows = connection.execute(
                """
                select
                    id,
                    headline,
                    date_logged,
                    company_involved,
                    claimant_name,
                    categories,
                    severity_score,
                    reality_summary,
                    status
                from incident_logs
                where status = ?
                order by date_logged desc
                """,
                ("approved",),
            ).fetchall()

            source_rows = connection.execute(
                """
                select
                    id,
                    incident_id,
                    source_url,
                    source_type,
                    publisher,
                    title
                from incident_sources
                order by published_at desc, id asc
                """
            ).fetchall()

        sources_by_incident: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in source_rows:
            sources_by_incident[row["incident_id"]].append(
                {
                    "id": row["id"],
                    "source_url": row["source_url"],
                    "source_type": row["source_type"],
                    "publisher": row["publisher"],
                    "title": row["title"],
                }
            )

        return [
            {
                "id": row["id"],
                "headline": row["headline"],
                "date_logged": row["date_logged"],
                "company_involved": row["company_involved"],
                "claimant_name": row["claimant_name"],
                "categories": json.loads(row["categories"]),
                "severity_score": row["severity_score"],
                "reality_summary": row["reality_summary"],
                "status": row["status"],
                "sources": sources_by_incident[row["id"]],
            }
            for row in incident_rows
        ]

    def get_filter_values(self) -> dict[str, list[str]]:
        incidents = self.list_public_incidents()

        categories = sorted(
            {category for incident in incidents for category in incident["categories"]}
        )
        claimants = sorted(
            {
                incident["claimant_name"]
                for incident in incidents
                if incident["claimant_name"]
            }
        )
        companies = sorted({incident["company_involved"] for incident in incidents})

        return {
            "categories": categories,
            "claimants": claimants,
            "companies": companies,
        }

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SQLITE_SCHEMA)

            incident_count = connection.execute(
                "select count(*) from incident_logs"
            ).fetchone()[0]
            if incident_count:
                return

            connection.executemany(
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
                _SEED_CLAIMS,
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
                _SEED_INCIDENTS,
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
                _SEED_SOURCES,
            )
            connection.commit()
