from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models.claim import ClaimRecord
from app.scrapers.rss import RSSArticle
from app.services.claim_matcher import PUBLIC_CLAIM_MATCH_THRESHOLD
from app.services.incident_query import IncidentQueryFilters

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
    (
        "claim-2",
        "RoboFleet",
        "RoboFleet",
        "Our fleet will operate safely without sidewalk supervisors.",
        "2026-02-20",
        "autonomous operations",
        "approved",
    ),
    (
        "claim-3",
        "CodeForge",
        "CodeForge",
        "Our coding agent can replace most junior QA workflows end to end.",
        "2026-03-10",
        "coding automation",
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

    def list_public_incidents(
        self,
        filters: IncidentQueryFilters,
    ) -> list[dict[str, Any]]:
        where_clauses = ["incident_logs.status = ?"]
        params: list[Any] = ["approved"]

        if filters.category:
            where_clauses.append("incident_logs.categories like ?")
            params.append(f"%{json.dumps(filters.category).strip('"')}%")
        if filters.company:
            where_clauses.append("incident_logs.company_involved = ?")
            params.append(filters.company)
        if filters.claimant:
            where_clauses.append("incident_logs.claimant_name = ?")
            params.append(filters.claimant)
        if filters.severity_min is not None:
            where_clauses.append("incident_logs.severity_score >= ?")
            params.append(filters.severity_min)
        if filters.severity_max is not None:
            where_clauses.append("incident_logs.severity_score <= ?")
            params.append(filters.severity_max)

        offset = (filters.page - 1) * filters.page_size

        with self._connect() as connection:
            incident_rows = connection.execute(
                f"""
                select
                    incident_logs.id,
                    incident_logs.headline,
                    incident_logs.date_logged,
                    incident_logs.company_involved,
                    incident_logs.claimant_name,
                    incident_logs.categories,
                    incident_logs.severity_score,
                    incident_logs.reality_summary,
                    incident_logs.status,
                    incident_logs.claim_match_confidence,
                    claims.id as claim_id,
                    claims.claimant_name as claim_claimant_name,
                    claims.company_involved as claim_company_involved,
                    claims.original_claim,
                    claims.claim_date,
                    claims.claim_topic,
                    claims.status as claim_status
                from incident_logs
                left join claims
                    on claims.id = incident_logs.matched_claim_id
                where {" and ".join(where_clauses)}
                order by incident_logs.date_logged desc
                limit ? offset ?
                """,
                (*params, filters.page_size, offset),
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

        sources_by_incident = self._group_sources_by_incident(source_rows)

        return [
            self._serialize_public_incident_row(row, sources_by_incident[row["id"]])
            for row in incident_rows
        ]

    def get_public_incident(self, incident_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            incident_row = connection.execute(
                """
                select
                    incident_logs.id,
                    incident_logs.headline,
                    incident_logs.date_logged,
                    incident_logs.company_involved,
                    incident_logs.claimant_name,
                    incident_logs.categories,
                    incident_logs.severity_score,
                    incident_logs.reality_summary,
                    incident_logs.status,
                    incident_logs.claim_match_confidence,
                    claims.id as claim_id,
                    claims.claimant_name as claim_claimant_name,
                    claims.company_involved as claim_company_involved,
                    claims.original_claim,
                    claims.claim_date,
                    claims.claim_topic,
                    claims.status as claim_status
                from incident_logs
                left join claims
                    on claims.id = incident_logs.matched_claim_id
                where incident_logs.id = ? and incident_logs.status = ?
                limit 1
                """,
                (incident_id, "approved"),
            ).fetchone()

            if incident_row is None:
                return None

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
                where incident_id = ?
                order by published_at desc, id asc
                """,
                (incident_id,),
            ).fetchall()

        sources_by_incident = self._group_sources_by_incident(source_rows)
        return self._serialize_public_incident_row(
            incident_row,
            sources_by_incident[incident_id],
        )

    def list_review_queue(self) -> list[dict[str, Any]]:
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
                    status,
                    matched_claim_id,
                    claim_match_confidence,
                    review_notes
                from incident_logs
                where status = ?
                order by date_logged desc, id asc
                """,
                ("pending_review",),
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

        sources_by_incident = self._group_sources_by_incident(source_rows)

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
                "matched_claim_id": row["matched_claim_id"],
                "claim_match_confidence": row["claim_match_confidence"],
                "review_notes": row["review_notes"],
                "sources": sources_by_incident[row["id"]],
            }
            for row in incident_rows
        ]

    def get_filter_values(self) -> dict[str, list[str]]:
        incidents = self.list_public_incidents(IncidentQueryFilters())

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

    def ingest_rss_article(
        self,
        article: RSSArticle,
        *,
        ingestion_run_id: str,
    ) -> bool:
        with self._connect() as connection:
            existing_row = connection.execute(
                """
                select incident_id
                from incident_sources
                where source_url = ?
                limit 1
                """,
                (article.url,),
            ).fetchone()
            if existing_row is not None:
                return False

            incident_id = f"incident-{uuid4()}"
            source_id = f"source-{uuid4()}"

            connection.execute(
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
                (
                    incident_id,
                    article.title,
                    article.published_at.date().isoformat(),
                    "Pending classification",
                    None,
                    json.dumps([]),
                    1,
                    article.summary,
                    "pending_review",
                    ingestion_run_id,
                    None,
                    (
                        f"Ingested from {article.publisher} RSS feed; "
                        "awaiting enrichment and editorial review."
                    ),
                    None,
                    None,
                ),
            )
            connection.execute(
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
                (
                    source_id,
                    incident_id,
                    article.url,
                    article.source_type,
                    article.publisher,
                    article.title,
                    article.published_at.isoformat(),
                    0,
                ),
            )
            connection.commit()

        return True

    def list_pending_incidents(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            incident_rows = connection.execute(
                """
                select
                    incident_logs.id,
                    incident_logs.headline,
                    incident_logs.date_logged,
                    incident_logs.reality_summary,
                    incident_sources.publisher,
                    incident_sources.title,
                    incident_sources.source_url
                from incident_logs
                left join incident_sources
                    on incident_sources.incident_id = incident_logs.id
                where incident_logs.status = ?
                order by incident_logs.date_logged desc, incident_logs.id asc
                """,
                ("pending_review",),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "headline": row["headline"],
                "date_logged": row["date_logged"],
                "source_summary": row["reality_summary"],
                "publisher": row["publisher"],
                "source_title": row["title"],
                "source_url": row["source_url"],
            }
            for row in incident_rows
        ]

    def list_claims(self) -> list[ClaimRecord]:
        with self._connect() as connection:
            claim_rows = connection.execute(
                """
                select
                    id,
                    claimant_name,
                    company_involved,
                    original_claim,
                    claim_date,
                    claim_topic,
                    status
                from claims
                where status in ('seeded', 'approved')
                order by claim_date desc, id asc
                """
            ).fetchall()

        return [
            ClaimRecord(
                id=row["id"],
                claimant_name=row["claimant_name"],
                company_involved=row["company_involved"],
                original_claim=row["original_claim"],
                claim_date=row["claim_date"],
                claim_topic=row["claim_topic"],
                status=row["status"],
            )
            for row in claim_rows
        ]

    def update_incident_enrichment(
        self,
        *,
        incident_id: str,
        company_involved: str,
        claimant_name: str | None,
        categories: list[str],
        severity_score: int,
        reality_summary: str,
        confidence_score: float,
        review_notes: str,
        matched_claim_id: str | None = None,
        claim_match_confidence: float | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                update incident_logs
                set
                    company_involved = ?,
                    claimant_name = ?,
                    categories = ?,
                    severity_score = ?,
                    reality_summary = ?,
                    confidence_score = ?,
                    review_notes = ?,
                    matched_claim_id = ?,
                    claim_match_confidence = ?,
                    updated_at = current_timestamp
                where id = ?
                """,
                (
                    company_involved,
                    claimant_name,
                    json.dumps(categories),
                    severity_score,
                    reality_summary,
                    confidence_score,
                    review_notes,
                    matched_claim_id,
                    claim_match_confidence,
                    incident_id,
                ),
            )
            connection.commit()

    def apply_admin_review(
        self,
        *,
        incident_id: str,
        status: str,
        company_involved: str,
        claimant_name: str | None,
        categories: list[str],
        severity_score: int,
        reality_summary: str,
        matched_claim_id: str | None,
        claim_match_confidence: float | None,
        review_notes: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                update incident_logs
                set
                    status = ?,
                    company_involved = ?,
                    claimant_name = ?,
                    categories = ?,
                    severity_score = ?,
                    reality_summary = ?,
                    matched_claim_id = ?,
                    claim_match_confidence = ?,
                    review_notes = ?,
                    updated_at = current_timestamp
                where id = ?
                """,
                (
                    status,
                    company_involved,
                    claimant_name,
                    json.dumps(categories),
                    severity_score,
                    reality_summary,
                    matched_claim_id,
                    claim_match_confidence,
                    review_notes,
                    incident_id,
                ),
            )
            if cursor.rowcount == 0:
                return None

            incident_row = connection.execute(
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
                    status,
                    matched_claim_id,
                    claim_match_confidence,
                    review_notes
                from incident_logs
                where id = ?
                """,
                (incident_id,),
            ).fetchone()
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
                where incident_id = ?
                order by published_at desc, id asc
                """,
                (incident_id,),
            ).fetchall()
            connection.commit()

        sources_by_incident = self._group_sources_by_incident(source_rows)
        row = incident_row
        assert row is not None
        return {
            "id": row["id"],
            "headline": row["headline"],
            "date_logged": row["date_logged"],
            "company_involved": row["company_involved"],
            "claimant_name": row["claimant_name"],
            "categories": json.loads(row["categories"]),
            "severity_score": row["severity_score"],
            "reality_summary": row["reality_summary"],
            "status": row["status"],
            "matched_claim_id": row["matched_claim_id"],
            "claim_match_confidence": row["claim_match_confidence"],
            "review_notes": row["review_notes"],
            "sources": sources_by_incident[row["id"]],
        }

    def _group_sources_by_incident(
        self,
        source_rows: list[sqlite3.Row],
    ) -> dict[str, list[dict[str, Any]]]:
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

        return sources_by_incident

    def _serialize_public_incident_row(
        self,
        row: sqlite3.Row,
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "id": row["id"],
            "headline": row["headline"],
            "date_logged": row["date_logged"],
            "company_involved": row["company_involved"],
            "claimant_name": row["claimant_name"],
            "categories": json.loads(row["categories"]),
            "severity_score": row["severity_score"],
            "reality_summary": row["reality_summary"],
            "status": row["status"],
            "matched_claim": _build_public_claim_payload(row),
            "sources": sources,
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


def _build_public_claim_payload(row: sqlite3.Row) -> dict[str, Any] | None:
    if row["claim_id"] is None:
        return None
    if row["claim_status"] != "approved":
        return None
    if row["claim_match_confidence"] is None:
        return None
    if row["claim_match_confidence"] < PUBLIC_CLAIM_MATCH_THRESHOLD:
        return None

    return {
        "id": row["claim_id"],
        "claimant_name": row["claim_claimant_name"],
        "company_involved": row["claim_company_involved"],
        "original_claim": row["original_claim"],
        "claim_date": row["claim_date"],
        "claim_topic": row["claim_topic"],
        "match_confidence": row["claim_match_confidence"],
    }
