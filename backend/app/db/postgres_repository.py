from __future__ import annotations

import json
from collections import defaultdict
from typing import Any
from uuid import uuid4

from app.models.claim import ClaimRecord
from app.scrapers.rss import RSSArticle
from app.services.claim_matcher import PUBLIC_CLAIM_MATCH_THRESHOLD
from app.services.incident_query import IncidentQueryFilters

try:
    from psycopg.rows import dict_row
except ModuleNotFoundError:
    dict_row = None

try:
    from psycopg_pool import ConnectionPool
except ModuleNotFoundError:
    ConnectionPool = None

_POSTGRES_SCHEMA = """
create table if not exists claims (
    id text primary key,
    claimant_name text not null,
    company_involved text not null,
    original_claim text not null,
    claim_date text not null,
    claim_topic text not null,
    status text not null,
    notes text,
    created_at timestamptz default current_timestamp,
    updated_at timestamptz default current_timestamp
);

alter table claims
    add column if not exists notes text;

create table if not exists claim_sources (
    id text primary key,
    claim_id text not null references claims(id) on delete cascade,
    source_url text not null,
    source_kind text not null,
    display_order integer not null default 0,
    created_at timestamptz default current_timestamp
);

create table if not exists incident_logs (
    id text primary key,
    external_id text,
    headline text not null,
    headline_en text,
    headline_zh text,
    date_logged text not null,
    company_involved text not null,
    company_involved_zh text,
    incident_topic text,
    claimant_name text,
    categories text not null,
    severity_score integer not null,
    suggested_severity_score integer,
    reality_summary text not null,
    reality_summary_en text,
    reality_summary_zh text,
    status text not null,
    ingestion_run_id text,
    confidence_score double precision,
    severity_confidence double precision,
    severity_reasoning text,
    severity_flags text,
    severity_model text,
    severity_decision_source text,
    review_notes text,
    matched_claim_id text references claims(id),
    claim_match_confidence double precision,
    legitimacy_score double precision,
    legitimacy_label text,
    legitimacy_reasoning text,
    legitimacy_reasoning_zh text,
    source_validation_summary text,
    source_validation_summary_zh text,
    legitimacy_flag text,
    confidence_level text,
    import_notes text,
    translation_status text,
    review_batch_id text,
    review_model text,
    duplicate_status text,
    duplicate_of_incident_id text references incident_logs(id),
    canonical_incident_id text references incident_logs(id),
    embedding_model text,
    embedding_vector text,
    reviewed_at timestamptz,
    severity_suggested_at timestamptz,
    translated_at timestamptz,
    created_at timestamptz default current_timestamp,
    updated_at timestamptz default current_timestamp
);

alter table incident_logs
    add column if not exists external_id text;

alter table incident_logs
    add column if not exists suggested_severity_score integer;

alter table incident_logs
    add column if not exists severity_confidence double precision;

alter table incident_logs
    add column if not exists severity_reasoning text;

alter table incident_logs
    add column if not exists severity_flags text;

alter table incident_logs
    add column if not exists severity_model text;

alter table incident_logs
    add column if not exists severity_decision_source text;

alter table incident_logs
    add column if not exists headline_en text;

alter table incident_logs
    add column if not exists headline_zh text;

alter table incident_logs
    add column if not exists company_involved_zh text;

alter table incident_logs
    add column if not exists incident_topic text;

alter table incident_logs
    add column if not exists reality_summary_en text;

alter table incident_logs
    add column if not exists reality_summary_zh text;

alter table incident_logs
    add column if not exists legitimacy_score double precision;

alter table incident_logs
    add column if not exists legitimacy_label text;

alter table incident_logs
    add column if not exists legitimacy_reasoning text;

alter table incident_logs
    add column if not exists legitimacy_reasoning_zh text;

alter table incident_logs
    add column if not exists source_validation_summary text;

alter table incident_logs
    add column if not exists source_validation_summary_zh text;

alter table incident_logs
    add column if not exists legitimacy_flag text;

alter table incident_logs
    add column if not exists confidence_level text;

alter table incident_logs
    add column if not exists import_notes text;

alter table incident_logs
    add column if not exists translation_status text;

alter table incident_logs
    add column if not exists review_batch_id text;

alter table incident_logs
    add column if not exists review_model text;

alter table incident_logs
    add column if not exists duplicate_status text;

alter table incident_logs
    add column if not exists duplicate_of_incident_id text references incident_logs(id);

alter table incident_logs
    add column if not exists canonical_incident_id text references incident_logs(id);

alter table incident_logs
    add column if not exists embedding_model text;

alter table incident_logs
    add column if not exists embedding_vector text;

alter table incident_logs
    add column if not exists reviewed_at timestamptz;

alter table incident_logs
    add column if not exists severity_suggested_at timestamptz;

alter table incident_logs
    add column if not exists translated_at timestamptz;

create table if not exists incident_sources (
    id text primary key,
    incident_id text not null references incident_logs(id) on delete cascade,
    source_url text not null,
    canonical_url text,
    source_type text not null,
    publisher text,
    title text,
    published_at text,
    fetch_status text,
    http_status integer,
    evidence_text text,
    fetch_error text,
    fetched_at timestamptz,
    is_primary integer not null default 0,
    created_at timestamptz default current_timestamp
);

alter table incident_sources
    add column if not exists canonical_url text;

alter table incident_sources
    add column if not exists fetch_status text;

alter table incident_sources
    add column if not exists http_status integer;

alter table incident_sources
    add column if not exists evidence_text text;

alter table incident_sources
    add column if not exists fetch_error text;

alter table incident_sources
    add column if not exists fetched_at timestamptz;

create table if not exists incident_duplicate_candidates (
    id text primary key,
    incident_id text not null references incident_logs(id) on delete cascade,
    candidate_incident_id text not null references incident_logs(id) on delete cascade,
    embedding_score double precision not null,
    llm_verdict text not null,
    confidence double precision not null,
    reasoning text,
    status text not null,
    created_at timestamptz default current_timestamp
);

create unique index if not exists claim_sources_claim_url_unique_idx
    on claim_sources (claim_id, source_url);

create index if not exists claim_sources_claim_id_idx
    on claim_sources (claim_id);

create index if not exists claim_sources_source_kind_idx
    on claim_sources (source_kind);

create unique index if not exists incident_logs_external_id_unique_idx
    on incident_logs (external_id)
    where external_id is not null;

create unique index if not exists incident_duplicate_candidates_unique_idx
    on incident_duplicate_candidates (incident_id, candidate_incident_id);
"""

class PostgresIncidentRepository:
    def __init__(self, database_url: str) -> None:
        if not database_url.startswith(("postgresql://", "postgres://")):
            raise ValueError(
                "Only postgresql:// or postgres:// DATABASE_URL values are supported."
            )

        self._database_url = database_url
        self._pool = self._build_pool()
        self._initialize_database()

    def close(self) -> None:
        self._pool.close()

    def list_public_incidents(
        self,
        filters: IncidentQueryFilters,
    ) -> list[dict[str, Any]]:
        where_sql, params = self._build_public_incident_where(filters)
        offset = (filters.page - 1) * filters.page_size

        with self._connect() as connection:
            incident_rows = connection.execute(
                f"""
                select
                    incident_logs.id,
                    incident_logs.headline,
                    incident_logs.headline_en,
                    incident_logs.headline_zh,
                    incident_logs.date_logged,
                    incident_logs.company_involved,
                    incident_logs.company_involved_zh,
                    incident_logs.incident_topic,
                    incident_logs.claimant_name,
                    incident_logs.categories,
                    incident_logs.severity_score,
                    incident_logs.reality_summary,
                    incident_logs.reality_summary_en,
                    incident_logs.reality_summary_zh,
                    incident_logs.status,
                    incident_logs.translation_status
                from incident_logs
                where {where_sql}
                order by incident_logs.date_logged desc
                limit %s offset %s
                """,
                (*params, filters.page_size, offset),
            ).fetchall()

        return [
            self._serialize_public_archive_row(row)
            for row in incident_rows
        ]

    def list_public_incident_feed(
        self,
        filters: IncidentQueryFilters,
    ) -> dict[str, Any]:
        where_sql, params = self._build_public_incident_where(filters)
        offset = (filters.page - 1) * filters.page_size

        with self._connect() as connection:
            count_row = connection.execute(
                f"""
                select count(*) as total_count
                from incident_logs
                where {where_sql}
                """,
                params,
            ).fetchone()
            summary_row = connection.execute(
                f"""
                select
                    max(incident_logs.date_logged) as newest_logged,
                    min(incident_logs.date_logged) as oldest_logged,
                    max(incident_logs.severity_score) as highest_severity
                from incident_logs
                where {where_sql}
                """,
                params,
            ).fetchone()
            category_rows = connection.execute(
                f"""
                select
                    category.value as category,
                    count(*) as count
                from incident_logs
                cross join lateral jsonb_array_elements_text(
                    incident_logs.categories::jsonb
                ) as category(value)
                where {where_sql}
                group by category.value
                order by count(*) desc, category.value asc
                """,
                params,
            ).fetchall()
            company_rows = connection.execute(
                f"""
                select
                    incident_logs.company_involved as company,
                    max(incident_logs.company_involved_zh) as company_zh,
                    count(*) as count
                from incident_logs
                where {where_sql}
                group by incident_logs.company_involved
                order by count(*) desc, incident_logs.company_involved asc
                """,
                params,
            ).fetchall()
            incident_rows = connection.execute(
                f"""
                select
                    incident_logs.id,
                    incident_logs.headline,
                    incident_logs.headline_en,
                    incident_logs.headline_zh,
                    incident_logs.date_logged,
                    incident_logs.company_involved,
                    incident_logs.company_involved_zh,
                    incident_logs.incident_topic,
                    incident_logs.claimant_name,
                    incident_logs.categories,
                    incident_logs.severity_score,
                    incident_logs.reality_summary,
                    incident_logs.reality_summary_en,
                    incident_logs.reality_summary_zh,
                    incident_logs.status,
                    incident_logs.translation_status
                from incident_logs
                where {where_sql}
                order by incident_logs.date_logged desc
                limit %s offset %s
                """,
                (*params, filters.page_size, offset),
            ).fetchall()

        total_count = int(count_row["total_count"])
        total_pages = max((total_count + filters.page_size - 1) // filters.page_size, 1)
        return {
            "items": [
                self._serialize_public_archive_row(row)
                for row in incident_rows
            ],
            "page": filters.page,
            "page_size": filters.page_size,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_next_page": filters.page < total_pages,
            "has_previous_page": filters.page > 1,
            "slice_summary": {
                "total_matches": total_count,
                "newest_logged": summary_row["newest_logged"] if summary_row else None,
                "oldest_logged": summary_row["oldest_logged"] if summary_row else None,
                "highest_severity": (
                    summary_row["highest_severity"] if summary_row else None
                ),
                "top_categories": [
                    {"category": row["category"], "count": row["count"]}
                    for row in category_rows
                ],
                "top_companies": [
                    {
                        "company": row["company"],
                        "company_zh": row.get("company_zh"),
                        "count": row["count"],
                    }
                    for row in company_rows
                ],
            },
        }

    def get_public_incident(self, incident_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            incident_row = connection.execute(
                """
                select
                    incident_logs.id,
                    incident_logs.external_id,
                    incident_logs.headline,
                    incident_logs.headline_en,
                    incident_logs.headline_zh,
                    incident_logs.date_logged,
                    incident_logs.company_involved,
                    incident_logs.company_involved_zh,
                    incident_logs.incident_topic,
                    incident_logs.claimant_name,
                    incident_logs.categories,
                    incident_logs.severity_score,
                    incident_logs.reality_summary,
                    incident_logs.reality_summary_en,
                    incident_logs.reality_summary_zh,
                    incident_logs.status,
                    incident_logs.translation_status,
                    incident_logs.legitimacy_reasoning,
                    incident_logs.legitimacy_reasoning_zh,
                    incident_logs.source_validation_summary,
                    incident_logs.source_validation_summary_zh,
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
                where incident_logs.id = %s and incident_logs.status = %s
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
                where incident_id = %s
                order by published_at desc, id asc
                """,
                (incident_id,),
            ).fetchall()

        sources_by_incident = self._group_sources_by_incident(source_rows)
        return self._serialize_public_detail_row(
            incident_row,
            sources_by_incident[incident_id],
        )

    def list_review_queue(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            incident_rows = connection.execute(
                """
                select
                    id,
                    external_id,
                    headline,
                    headline_en,
                    headline_zh,
                    date_logged,
                    company_involved,
                    incident_topic,
                    claimant_name,
                    categories,
                    severity_score,
                    suggested_severity_score,
                    reality_summary,
                    reality_summary_en,
                    reality_summary_zh,
                    status,
                    matched_claim_id,
                    claim_match_confidence,
                    review_notes,
                    legitimacy_score,
                    legitimacy_label,
                    severity_confidence,
                    severity_reasoning,
                    severity_flags,
                    severity_model,
                    severity_decision_source,
                    legitimacy_reasoning,
                    legitimacy_reasoning_zh,
                    source_validation_summary,
                    source_validation_summary_zh,
                    translation_status,
                    review_batch_id,
                    review_model,
                    duplicate_status,
                    duplicate_of_incident_id,
                    canonical_incident_id
                from incident_logs
                where status in (%s, %s, %s, %s)
                order by date_logged desc, id asc
                """,
                (
                    "pending_review",
                    "pending_editor_review",
                    "pending_llm_escalation",
                    "pending_duplicate_review",
                ),
            ).fetchall()

            source_rows = connection.execute(
                """
                select
                    id,
                    incident_id,
                    source_url,
                    canonical_url,
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
                "headline_en": row["headline_en"],
                "headline_zh": row["headline_zh"],
                "date_logged": row["date_logged"],
                "company_involved": row["company_involved"],
                "incident_topic": row["incident_topic"],
                "claimant_name": row["claimant_name"],
                "categories": json.loads(row["categories"]),
                "severity_score": row["severity_score"],
                "suggested_severity_score": row["suggested_severity_score"],
                "reality_summary": row["reality_summary"],
                "reality_summary_en": row["reality_summary_en"],
                "reality_summary_zh": row["reality_summary_zh"],
                "status": row["status"],
                "matched_claim_id": row["matched_claim_id"],
                "claim_match_confidence": row["claim_match_confidence"],
                "review_notes": row["review_notes"],
                "legitimacy_score": row["legitimacy_score"],
                "legitimacy_label": row["legitimacy_label"],
                "severity_confidence": row["severity_confidence"],
                "severity_reasoning": row["severity_reasoning"],
                "severity_flags": _parse_text_array(row["severity_flags"]),
                "severity_model": row["severity_model"],
                "severity_decision_source": row["severity_decision_source"],
                "legitimacy_reasoning": row["legitimacy_reasoning"],
                "source_validation_summary": row["source_validation_summary"],
                "translation_status": row["translation_status"],
                "review_batch_id": row["review_batch_id"],
                "review_model": row["review_model"],
                "duplicate_status": row["duplicate_status"],
                "duplicate_of_incident_id": row["duplicate_of_incident_id"],
                "canonical_incident_id": row["canonical_incident_id"],
                "duplicate_candidates": self._list_duplicate_candidates(row["id"]),
                "sources": sources_by_incident[row["id"]],
            }
            for row in incident_rows
        ]

    def list_incidents_pending_llm_review(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            incident_rows = connection.execute(
                """
                select
                    id,
                    external_id,
                    headline,
                    headline_en,
                    headline_zh,
                    date_logged,
                    company_involved,
                    incident_topic,
                    claimant_name,
                    categories,
                    severity_score,
                    suggested_severity_score,
                    reality_summary,
                    reality_summary_en,
                    reality_summary_zh,
                    status,
                    review_notes,
                    severity_confidence,
                    severity_reasoning,
                    severity_flags,
                    severity_model,
                    severity_decision_source,
                    legitimacy_flag,
                    confidence_level,
                    import_notes,
                    review_batch_id,
                    review_model,
                    duplicate_status,
                    duplicate_of_incident_id,
                    canonical_incident_id,
                    embedding_model,
                    embedding_vector,
                    translation_status
                from incident_logs
                where status = %s
                order by date_logged desc, id asc
                """,
                ("pending_llm_review",),
            ).fetchall()
            source_rows = connection.execute(
                """
                select
                    id,
                    incident_id,
                    source_url,
                    canonical_url,
                    source_type,
                    publisher,
                    title,
                    fetch_status,
                    http_status,
                    evidence_text,
                    fetch_error
                from incident_sources
                order by published_at desc, id asc
                """
            ).fetchall()

        sources_by_incident = self._group_sources_by_incident(source_rows)
        return [
            {
                "id": row["id"],
                "external_id": row["external_id"],
                "headline": row["headline"],
                "headline_en": row["headline_en"],
                "headline_zh": row["headline_zh"],
                "date_logged": row["date_logged"],
                "company_involved": row["company_involved"],
                "incident_topic": row["incident_topic"],
                "claimant_name": row["claimant_name"],
                "categories": json.loads(row["categories"]),
                "severity_score": row["severity_score"],
                "suggested_severity_score": row["suggested_severity_score"],
                "reality_summary": row["reality_summary"],
                "reality_summary_en": row["reality_summary_en"],
                "reality_summary_zh": row["reality_summary_zh"],
                "status": row["status"],
                "review_notes": row["review_notes"],
                "severity_confidence": row["severity_confidence"],
                "severity_reasoning": row["severity_reasoning"],
                "severity_flags": _parse_text_array(row["severity_flags"]),
                "severity_model": row["severity_model"],
                "severity_decision_source": row["severity_decision_source"],
                "legitimacy_flag": row["legitimacy_flag"],
                "confidence_level": row["confidence_level"],
                "import_notes": row["import_notes"],
                "review_batch_id": row["review_batch_id"],
                "review_model": row["review_model"],
                "translation_status": row["translation_status"],
                "sources": sources_by_incident[row["id"]],
                "duplicate_status": row["duplicate_status"],
                "duplicate_of_incident_id": row["duplicate_of_incident_id"],
                "canonical_incident_id": row["canonical_incident_id"],
                "embedding_model": row["embedding_model"],
                "embedding_vector": json.loads(row["embedding_vector"])
                if row.get("embedding_vector")
                else None,
            }
            for row in incident_rows
        ]

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            incident_row = connection.execute(
                """
                select
                    id,
                    external_id,
                    headline,
                    headline_en,
                    headline_zh,
                    date_logged,
                    company_involved,
                    incident_topic,
                    claimant_name,
                    categories,
                    severity_score,
                    suggested_severity_score,
                    reality_summary,
                    reality_summary_en,
                    reality_summary_zh,
                    status,
                    review_notes,
                    legitimacy_score,
                    legitimacy_label,
                    severity_confidence,
                    severity_reasoning,
                    severity_flags,
                    severity_model,
                    severity_decision_source,
                    legitimacy_reasoning,
                    source_validation_summary,
                    legitimacy_flag,
                    confidence_level,
                    import_notes,
                    translation_status,
                    review_batch_id,
                    review_model,
                    duplicate_status,
                    duplicate_of_incident_id,
                    canonical_incident_id,
                    embedding_model,
                    embedding_vector
                from incident_logs
                where id = %s
                limit 1
                """,
                (incident_id,),
            ).fetchone()
            if incident_row is None:
                return None
            source_rows = connection.execute(
                """
                select
                    id,
                    incident_id,
                    source_url,
                    canonical_url,
                    source_type,
                    publisher,
                    title,
                    fetch_status,
                    http_status,
                    evidence_text,
                    fetch_error
                from incident_sources
                where incident_id = %s
                order by is_primary desc, id asc
                """,
                (incident_id,),
            ).fetchall()

        sources_by_incident = self._group_sources_by_incident(source_rows)
        return {
            "id": incident_row["id"],
            "external_id": incident_row["external_id"],
            "headline": incident_row["headline"],
            "headline_en": incident_row["headline_en"],
            "headline_zh": incident_row["headline_zh"],
            "date_logged": incident_row["date_logged"],
            "company_involved": incident_row["company_involved"],
            "incident_topic": incident_row["incident_topic"],
            "claimant_name": incident_row["claimant_name"],
            "categories": json.loads(incident_row["categories"]),
            "severity_score": incident_row["severity_score"],
            "suggested_severity_score": incident_row["suggested_severity_score"],
            "reality_summary": incident_row["reality_summary"],
            "reality_summary_en": incident_row["reality_summary_en"],
            "reality_summary_zh": incident_row["reality_summary_zh"],
            "status": incident_row["status"],
            "review_notes": incident_row["review_notes"],
            "legitimacy_score": incident_row["legitimacy_score"],
            "legitimacy_label": incident_row["legitimacy_label"],
            "severity_confidence": incident_row["severity_confidence"],
            "severity_reasoning": incident_row["severity_reasoning"],
            "severity_flags": _parse_text_array(incident_row["severity_flags"]),
            "severity_model": incident_row["severity_model"],
            "severity_decision_source": incident_row["severity_decision_source"],
            "legitimacy_reasoning": incident_row["legitimacy_reasoning"],
            "source_validation_summary": incident_row["source_validation_summary"],
            "legitimacy_flag": incident_row["legitimacy_flag"],
            "confidence_level": incident_row["confidence_level"],
            "import_notes": incident_row["import_notes"],
            "translation_status": incident_row["translation_status"],
            "review_batch_id": incident_row["review_batch_id"],
            "review_model": incident_row["review_model"],
            "duplicate_status": incident_row["duplicate_status"],
            "duplicate_of_incident_id": incident_row["duplicate_of_incident_id"],
            "canonical_incident_id": incident_row["canonical_incident_id"],
            "embedding_model": incident_row["embedding_model"],
            "embedding_vector": json.loads(incident_row["embedding_vector"])
            if incident_row.get("embedding_vector")
            else None,
            "duplicate_candidates": self._list_duplicate_candidates(incident_id),
            "sources": sources_by_incident[incident_id],
        }

    def list_duplicate_search_pool(
        self,
        *,
        incident_id: str,
        date_logged: str,
        date_window_days: int,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            incident_rows = connection.execute(
                """
                select
                    id,
                    external_id,
                    headline,
                    headline_en,
                    headline_zh,
                    date_logged,
                    company_involved,
                    incident_topic,
                    claimant_name,
                    categories,
                    severity_score,
                    reality_summary,
                    reality_summary_en,
                    reality_summary_zh,
                    status,
                    review_notes,
                    legitimacy_score,
                    legitimacy_label,
                    legitimacy_reasoning,
                    source_validation_summary,
                    legitimacy_flag,
                    confidence_level,
                    import_notes,
                    translation_status,
                    review_batch_id,
                    review_model,
                    duplicate_status,
                    duplicate_of_incident_id,
                    canonical_incident_id,
                    embedding_model,
                    embedding_vector
                from incident_logs
                where id <> %s
                  and status <> %s
                  and abs((date_logged::date - %s::date)) <= %s
                order by date_logged desc, id asc
                """,
                (incident_id, "duplicate_confirmed", date_logged, date_window_days),
            ).fetchall()
            source_rows = connection.execute(
                """
                select
                    id,
                    incident_id,
                    source_url,
                    canonical_url,
                    source_type,
                    publisher,
                    title,
                    fetch_status,
                    http_status,
                    evidence_text,
                    fetch_error
                from incident_sources
                where incident_id in (
                    select id
                    from incident_logs
                    where id <> %s
                      and status <> %s
                      and abs((date_logged::date - %s::date)) <= %s
                )
                order by is_primary desc, id asc
                """,
                (incident_id, "duplicate_confirmed", date_logged, date_window_days),
            ).fetchall()

        sources_by_incident = self._group_sources_by_incident(source_rows)
        return [
            {
                "id": row["id"],
                "external_id": row["external_id"],
                "headline": row["headline"],
                "headline_en": row["headline_en"],
                "headline_zh": row["headline_zh"],
                "date_logged": row["date_logged"],
                "company_involved": row["company_involved"],
                "incident_topic": row["incident_topic"],
                "claimant_name": row["claimant_name"],
                "categories": json.loads(row["categories"]),
                "severity_score": row["severity_score"],
                "reality_summary": row["reality_summary"],
                "reality_summary_en": row["reality_summary_en"],
                "reality_summary_zh": row["reality_summary_zh"],
                "status": row["status"],
                "review_notes": row["review_notes"],
                "legitimacy_score": row["legitimacy_score"],
                "legitimacy_label": row["legitimacy_label"],
                "legitimacy_reasoning": row["legitimacy_reasoning"],
                "source_validation_summary": row["source_validation_summary"],
                "legitimacy_flag": row["legitimacy_flag"],
                "confidence_level": row["confidence_level"],
                "import_notes": row["import_notes"],
                "translation_status": row["translation_status"],
                "review_batch_id": row["review_batch_id"],
                "review_model": row["review_model"],
                "duplicate_status": row["duplicate_status"],
                "duplicate_of_incident_id": row["duplicate_of_incident_id"],
                "canonical_incident_id": row["canonical_incident_id"],
                "embedding_model": row["embedding_model"],
                "embedding_vector": json.loads(row["embedding_vector"])
                if row.get("embedding_vector")
                else None,
                "sources": sources_by_incident[row["id"]],
            }
            for row in incident_rows
        ]

    def get_filter_values(self) -> dict[str, object]:
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
        company_labels_zh = {
            company: next(
                (
                    incident.get("company_involved_zh")
                    for incident in incidents
                    if incident["company_involved"] == company
                    and incident.get("company_involved_zh")
                ),
                None,
            )
            for company in companies
        }
        archive_pairs = sorted(
            {
                tuple(map(int, str(incident["date_logged"]).split("-")[:2]))
                for incident in incidents
            },
            reverse=True,
        )
        years = sorted({year for year, _month in archive_pairs}, reverse=True)
        months_by_year = {
            str(year): sorted(
                {month for pair_year, month in archive_pairs if pair_year == year},
                reverse=True,
            )
            for year in years
        }

        return {
            "categories": categories,
            "claimants": claimants,
            "companies": companies,
            "company_labels_zh": company_labels_zh,
            "years": years,
            "months_by_year": months_by_year,
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
                where source_url = %s
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
                    external_id,
                    headline,
                    headline_en,
                    date_logged,
                    company_involved,
                    incident_topic,
                    claimant_name,
                    categories,
                    severity_score,
                    reality_summary,
                    reality_summary_en,
                    status,
                    ingestion_run_id,
                    confidence_score,
                    review_notes,
                    matched_claim_id,
                    claim_match_confidence,
                    translation_status
                ) values (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                """,
                (
                    incident_id,
                    None,
                    article.title,
                    article.title,
                    article.published_at.date().isoformat(),
                    "Pending classification",
                    None,
                    None,
                    json.dumps([]),
                    1,
                    article.summary,
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
                    "not_requested",
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
                ) values (%s, %s, %s, %s, %s, %s, %s, %s)
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
                where incident_logs.status = %s
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
                    status,
                    notes
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
                notes=row["notes"],
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
                    company_involved = %s,
                    claimant_name = %s,
                    categories = %s,
                    reality_summary = %s,
                    confidence_score = %s,
                    review_notes = %s,
                    matched_claim_id = %s,
                    claim_match_confidence = %s,
                    updated_at = current_timestamp
                where id = %s
                """,
                (
                    company_involved,
                    claimant_name,
                    json.dumps(categories),
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
                    status = %s,
                    company_involved = %s,
                    claimant_name = %s,
                    categories = %s,
                    severity_score = %s,
                    severity_decision_source = case
                        when suggested_severity_score is not null
                         and suggested_severity_score <> %s
                        then 'editor'
                        else severity_decision_source
                    end,
                    reality_summary = %s,
                    matched_claim_id = %s,
                    claim_match_confidence = %s,
                    review_notes = %s,
                    updated_at = current_timestamp
                where id = %s
                """,
                (
                    status,
                    company_involved,
                    claimant_name,
                    json.dumps(categories),
                    severity_score,
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
                    external_id,
                    headline,
                    headline_en,
                    headline_zh,
                    date_logged,
                    company_involved,
                    company_involved_zh,
                    incident_topic,
                    claimant_name,
                    categories,
                    severity_score,
                    suggested_severity_score,
                    reality_summary,
                    reality_summary_en,
                    reality_summary_zh,
                    status,
                    matched_claim_id,
                    claim_match_confidence,
                    review_notes,
                    legitimacy_score,
                    legitimacy_label,
                    severity_confidence,
                    severity_reasoning,
                    severity_flags,
                    severity_model,
                    severity_decision_source,
                    legitimacy_reasoning,
                    legitimacy_reasoning_zh,
                    source_validation_summary,
                    source_validation_summary_zh,
                    translation_status,
                    review_batch_id,
                    review_model,
                    duplicate_status,
                    duplicate_of_incident_id,
                    canonical_incident_id
                from incident_logs
                where id = %s
                """,
                (incident_id,),
            ).fetchone()
            source_rows = connection.execute(
                """
                select
                    id,
                    incident_id,
                    source_url,
                    canonical_url,
                    source_type,
                    publisher,
                    title
                from incident_sources
                where incident_id = %s
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
            "headline_en": row["headline_en"],
            "headline_zh": row["headline_zh"],
            "date_logged": row["date_logged"],
            "company_involved": row["company_involved"],
            "company_involved_zh": row["company_involved_zh"],
            "incident_topic": row["incident_topic"],
            "claimant_name": row["claimant_name"],
            "categories": json.loads(row["categories"]),
            "severity_score": row["severity_score"],
            "suggested_severity_score": row["suggested_severity_score"],
            "reality_summary": row["reality_summary"],
            "reality_summary_en": row["reality_summary_en"],
            "reality_summary_zh": row["reality_summary_zh"],
            "status": row["status"],
            "matched_claim_id": row["matched_claim_id"],
            "claim_match_confidence": row["claim_match_confidence"],
            "review_notes": row["review_notes"],
            "legitimacy_score": row["legitimacy_score"],
            "legitimacy_label": row["legitimacy_label"],
            "severity_confidence": row["severity_confidence"],
            "severity_reasoning": row["severity_reasoning"],
            "severity_flags": _parse_text_array(row["severity_flags"]),
            "severity_model": row["severity_model"],
            "severity_decision_source": row["severity_decision_source"],
            "legitimacy_reasoning": row["legitimacy_reasoning"],
            "legitimacy_reasoning_zh": row["legitimacy_reasoning_zh"],
            "source_validation_summary": row["source_validation_summary"],
            "source_validation_summary_zh": row["source_validation_summary_zh"],
            "translation_status": row["translation_status"],
            "review_batch_id": row["review_batch_id"],
            "review_model": row["review_model"],
            "duplicate_status": row["duplicate_status"],
            "duplicate_of_incident_id": row["duplicate_of_incident_id"],
            "canonical_incident_id": row["canonical_incident_id"],
            "duplicate_candidates": self._list_duplicate_candidates(row["id"]),
            "sources": sources_by_incident[row["id"]],
        }

    def upsert_claim_import_row(
        self,
        *,
        claim_id: str,
        claimant_name: str,
        company_involved: str,
        original_claim: str,
        claim_date: str,
        claim_topic: str,
        status: str,
        notes: str | None,
        primary_source_links: list[str],
        secondary_source_links: list[str],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                insert into claims (
                    id,
                    claimant_name,
                    company_involved,
                    original_claim,
                    claim_date,
                    claim_topic,
                    status,
                    notes
                ) values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (id) do update
                set
                    claimant_name = excluded.claimant_name,
                    company_involved = excluded.company_involved,
                    original_claim = excluded.original_claim,
                    claim_date = excluded.claim_date,
                    claim_topic = excluded.claim_topic,
                    status = excluded.status,
                    notes = excluded.notes,
                    updated_at = current_timestamp
                """,
                (
                    claim_id,
                    claimant_name,
                    company_involved,
                    original_claim,
                    claim_date,
                    claim_topic,
                    status,
                    notes,
                ),
            )
            connection.execute(
                "delete from claim_sources where claim_id = %s",
                (claim_id,),
            )

            source_rows: list[tuple[str, str, str, str, int]] = []
            for display_order, source_url in enumerate(primary_source_links):
                source_rows.append(
                    (
                        f"claim-source-{uuid4()}",
                        claim_id,
                        source_url,
                        "primary",
                        display_order,
                    )
                )
            for display_order, source_url in enumerate(secondary_source_links):
                source_rows.append(
                    (
                        f"claim-source-{uuid4()}",
                        claim_id,
                        source_url,
                        "secondary",
                        display_order,
                    )
                )

            self._execute_many(
                connection,
                """
                insert into claim_sources (
                    id,
                    claim_id,
                    source_url,
                    source_kind,
                    display_order
                ) values (%s, %s, %s, %s, %s)
                """,
                source_rows,
            )
            connection.commit()

    def upsert_incident_import_row(
        self,
        *,
        external_id: str,
        headline: str,
        date_logged: str,
        company_involved: str,
        incident_topic: str,
        reality_summary: str,
        status: str,
        source_links: list[str],
        legitimacy_score: float | None,
        legitimacy_label: str | None,
        legitimacy_reasoning: str | None,
        source_validation_summary: str,
        legitimacy_flag: str,
        confidence_level: str,
        import_notes: str | None,
        matched_claim_id: str | None,
        headline_zh: str | None,
        reality_summary_zh: str | None,
        translation_status: str,
    ) -> None:
        with self._connect() as connection:
            incident_id = connection.execute(
                """
                select id
                from incident_logs
                where external_id = %s
                limit 1
                """,
                (external_id,),
            ).fetchone()
            resolved_incident_id = (
                incident_id["id"] if incident_id is not None else f"incident-{uuid4()}"
            )
            connection.execute(
                """
                insert into incident_logs (
                    id,
                    external_id,
                    headline,
                    headline_en,
                    headline_zh,
                    date_logged,
                    company_involved,
                    incident_topic,
                    claimant_name,
                    categories,
                    severity_score,
                    reality_summary,
                    reality_summary_en,
                    reality_summary_zh,
                    status,
                    confidence_score,
                    review_notes,
                    matched_claim_id,
                    legitimacy_score,
                    legitimacy_label,
                    legitimacy_reasoning,
                    source_validation_summary,
                    legitimacy_flag,
                    confidence_level,
                    import_notes,
                    translation_status,
                    review_batch_id,
                    review_model,
                    reviewed_at,
                    translated_at
                ) values (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                on conflict (id) do update
                set
                    external_id = excluded.external_id,
                    headline = excluded.headline,
                    headline_en = excluded.headline_en,
                    headline_zh = excluded.headline_zh,
                    date_logged = excluded.date_logged,
                    company_involved = excluded.company_involved,
                    incident_topic = excluded.incident_topic,
                    reality_summary = excluded.reality_summary,
                    reality_summary_en = excluded.reality_summary_en,
                    reality_summary_zh = excluded.reality_summary_zh,
                    status = excluded.status,
                    confidence_score = excluded.confidence_score,
                    review_notes = excluded.review_notes,
                    matched_claim_id = excluded.matched_claim_id,
                    legitimacy_score = excluded.legitimacy_score,
                    legitimacy_label = excluded.legitimacy_label,
                    legitimacy_reasoning = excluded.legitimacy_reasoning,
                    source_validation_summary = excluded.source_validation_summary,
                    legitimacy_flag = excluded.legitimacy_flag,
                    confidence_level = excluded.confidence_level,
                    import_notes = excluded.import_notes,
                    translation_status = excluded.translation_status,
                    review_batch_id = excluded.review_batch_id,
                    review_model = excluded.review_model,
                    reviewed_at = excluded.reviewed_at,
                    translated_at = excluded.translated_at,
                    updated_at = current_timestamp
                """,
                (
                    resolved_incident_id,
                    external_id,
                    headline,
                    headline,
                    headline_zh,
                    date_logged,
                    company_involved,
                    incident_topic,
                    None,
                    json.dumps([]),
                    3,
                    reality_summary,
                    reality_summary,
                    reality_summary_zh,
                    status,
                    None,
                    legitimacy_reasoning,
                    matched_claim_id,
                    legitimacy_score,
                    legitimacy_label,
                    legitimacy_reasoning,
                    source_validation_summary,
                    legitimacy_flag,
                    confidence_level,
                    import_notes,
                    translation_status,
                    None,
                    None,
                    None,
                    None,
                ),
            )
            connection.execute(
                "delete from incident_sources where incident_id = %s",
                (resolved_incident_id,),
            )
            source_rows: list[tuple[object, ...]] = []
            for display_order, source_url in enumerate(source_links):
                source_rows.append(
                    (
                        f"source-{uuid4()}",
                        resolved_incident_id,
                        source_url,
                        None,
                        "imported",
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        1 if display_order == 0 else 0,
                    )
                )
            self._execute_many(
                connection,
                """
                insert into incident_sources (
                    id,
                    incident_id,
                    source_url,
                    canonical_url,
                    source_type,
                    publisher,
                    title,
                    published_at,
                    fetch_status,
                    http_status,
                    evidence_text,
                    fetch_error,
                    is_primary
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                source_rows,
            )
            connection.commit()

    def update_incident_source_evidence(
        self,
        *,
        source_id: str,
        canonical_url: str | None,
        fetch_status: str,
        http_status: int | None,
        evidence_text: str | None,
        fetch_error: str | None,
        fetched_at: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                update incident_sources
                set
                    canonical_url = %s,
                    fetch_status = %s,
                    http_status = %s,
                    evidence_text = %s,
                    fetch_error = %s,
                    fetched_at = %s
                where id = %s
                """,
                (
                    canonical_url,
                    fetch_status,
                    http_status,
                    evidence_text,
                    fetch_error,
                    fetched_at,
                    source_id,
                ),
            )
            connection.commit()

    def update_incident_embedding(
        self,
        *,
        incident_id: str,
        embedding_model: str,
        embedding_vector: list[float],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                update incident_logs
                set
                    embedding_model = %s,
                    embedding_vector = %s,
                    updated_at = current_timestamp
                where id = %s
                """,
                (embedding_model, json.dumps(embedding_vector), incident_id),
            )
            connection.commit()

    def replace_duplicate_candidates(
        self,
        *,
        incident_id: str,
        candidates: list[dict[str, Any]],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "delete from incident_duplicate_candidates where incident_id = %s",
                (incident_id,),
            )
            for candidate in candidates:
                connection.execute(
                    """
                    insert into incident_duplicate_candidates (
                        id,
                        incident_id,
                        candidate_incident_id,
                        embedding_score,
                        llm_verdict,
                        confidence,
                        reasoning,
                        status
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        f"duplicate-candidate-{uuid4()}",
                        incident_id,
                        candidate["candidate_incident_id"],
                        candidate["embedding_score"],
                        candidate["llm_verdict"],
                        candidate["confidence"],
                        candidate["reasoning"],
                        candidate["status"],
                    ),
                )
            connection.commit()

    def merge_duplicate_incident(
        self,
        *,
        duplicate_incident_id: str,
        canonical_incident_id: str,
        duplicate_status: str,
        reasoning: str,
        confidence: float,
    ) -> None:
        with self._connect() as connection:
            duplicate_row = connection.execute(
                """
                select import_notes
                from incident_logs
                where id = %s
                limit 1
                """,
                (duplicate_incident_id,),
            ).fetchone()
            canonical_row = connection.execute(
                """
                select import_notes
                from incident_logs
                where id = %s
                limit 1
                """,
                (canonical_incident_id,),
            ).fetchone()
            if duplicate_row is None or canonical_row is None:
                raise ValueError("Duplicate or canonical incident not found")

            duplicate_note = duplicate_row["import_notes"]
            if duplicate_note:
                merged_note = (
                    f"Merged duplicate {duplicate_incident_id}: {duplicate_note}"
                )
                canonical_note = canonical_row["import_notes"]
                merged_canonical_note = (
                    f"{canonical_note}\n{merged_note}"
                    if canonical_note
                    else merged_note
                )
                connection.execute(
                    """
                    update incident_logs
                    set
                        import_notes = %s,
                        updated_at = current_timestamp
                    where id = %s
                    """,
                    (merged_canonical_note, canonical_incident_id),
                )

            existing_source_rows = connection.execute(
                """
                select source_url
                from incident_sources
                where incident_id = %s
                """,
                (canonical_incident_id,),
            ).fetchall()
            existing_source_urls = {
                row["source_url"] for row in existing_source_rows
            }
            duplicate_source_rows = connection.execute(
                """
                select
                    source_url,
                    canonical_url,
                    source_type,
                    publisher,
                    title,
                    published_at,
                    fetch_status,
                    http_status,
                    evidence_text,
                    fetch_error,
                    fetched_at,
                    is_primary
                from incident_sources
                where incident_id = %s
                order by id asc
                """,
                (duplicate_incident_id,),
            ).fetchall()
            for row in duplicate_source_rows:
                if row["source_url"] in existing_source_urls:
                    continue
                connection.execute(
                    """
                    insert into incident_sources (
                        id,
                        incident_id,
                        source_url,
                        canonical_url,
                        source_type,
                        publisher,
                        title,
                        published_at,
                        fetch_status,
                        http_status,
                        evidence_text,
                        fetch_error,
                        fetched_at,
                        is_primary
                    ) values (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        f"source-{uuid4()}",
                        canonical_incident_id,
                        row["source_url"],
                        row["canonical_url"],
                        row["source_type"],
                        row["publisher"],
                        row["title"],
                        row["published_at"],
                        row["fetch_status"],
                        row["http_status"],
                        row["evidence_text"],
                        row["fetch_error"],
                        row["fetched_at"],
                        row["is_primary"],
                    ),
                )
                existing_source_urls.add(row["source_url"])

            connection.execute(
                """
                update incident_logs
                set
                    status = %s,
                    duplicate_status = %s,
                    duplicate_of_incident_id = %s,
                    canonical_incident_id = %s,
                    translation_status = %s,
                    review_notes = %s,
                    legitimacy_score = %s,
                    updated_at = current_timestamp
                where id = %s
                """,
                (
                    "duplicate_confirmed",
                    duplicate_status,
                    canonical_incident_id,
                    canonical_incident_id,
                    "not_requested",
                    reasoning,
                    confidence,
                    duplicate_incident_id,
                ),
            )
            connection.commit()

    def mark_incidents_review_batch(
        self,
        *,
        incident_ids: list[str],
        review_batch_id: str,
        review_model: str,
    ) -> None:
        with self._connect() as connection:
            for incident_id in incident_ids:
                connection.execute(
                    """
                    update incident_logs
                    set
                        review_batch_id = %s,
                        review_model = %s,
                        updated_at = current_timestamp
                    where id = %s
                    """,
                    (review_batch_id, review_model, incident_id),
                )
            connection.commit()

    def apply_incident_review_result(
        self,
        *,
        incident_id: str,
        status: str,
        legitimacy_score: float,
        legitimacy_label: str,
        legitimacy_reasoning: str,
        source_validation_summary: str,
        headline_en: str,
        reality_summary_en: str,
        categories: list[str],
        severity_score: int,
        suggested_severity_score: int | None,
        severity_confidence: float | None,
        severity_reasoning: str | None,
        severity_flags: list[str],
        severity_model: str,
        severity_decision_source: str | None,
        severity_suggested_at: str,
        review_model: str,
        review_batch_id: str | None,
        reviewed_at: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                update incident_logs
                set
                    status = %s,
                    headline = %s,
                    headline_en = %s,
                    reality_summary = %s,
                    reality_summary_en = %s,
                    categories = %s,
                    severity_score = %s,
                    suggested_severity_score = %s,
                    severity_confidence = %s,
                    severity_reasoning = %s,
                    severity_flags = %s,
                    severity_model = %s,
                    severity_decision_source = %s,
                    legitimacy_score = %s,
                    legitimacy_label = %s,
                    legitimacy_reasoning = %s,
                    source_validation_summary = %s,
                    review_model = %s,
                    review_batch_id = %s,
                    reviewed_at = %s,
                    severity_suggested_at = %s,
                    updated_at = current_timestamp
                where id = %s
                """,
                (
                    status,
                    headline_en,
                    headline_en,
                    reality_summary_en,
                    reality_summary_en,
                    json.dumps(categories),
                    severity_score,
                    suggested_severity_score,
                    severity_confidence,
                    severity_reasoning,
                    json.dumps(severity_flags),
                    severity_model,
                    severity_decision_source,
                    legitimacy_score,
                    legitimacy_label,
                    legitimacy_reasoning,
                    source_validation_summary,
                    review_model,
                    review_batch_id,
                    reviewed_at,
                    severity_suggested_at,
                    incident_id,
                ),
            )
            if cursor.rowcount == 0:
                return None
            incident_row = connection.execute(
                """
                select
                    id,
                    external_id,
                    headline,
                    headline_en,
                    headline_zh,
                    date_logged,
                    company_involved,
                    incident_topic,
                    claimant_name,
                    categories,
                    severity_score,
                    suggested_severity_score,
                    reality_summary,
                    reality_summary_en,
                    reality_summary_zh,
                    status,
                    matched_claim_id,
                    claim_match_confidence,
                    review_notes,
                    legitimacy_score,
                    legitimacy_label,
                    severity_confidence,
                    severity_reasoning,
                    severity_flags,
                    severity_model,
                    severity_decision_source,
                    legitimacy_reasoning,
                    source_validation_summary,
                    translation_status,
                    review_batch_id,
                    review_model,
                    duplicate_status,
                    duplicate_of_incident_id,
                    canonical_incident_id
                from incident_logs
                where id = %s
                """,
                (incident_id,),
            ).fetchone()
            source_rows = connection.execute(
                """
                select
                    id,
                    incident_id,
                    source_url,
                    canonical_url,
                    source_type,
                    publisher,
                    title,
                    fetch_status,
                    http_status,
                    evidence_text,
                    fetch_error
                from incident_sources
                where incident_id = %s
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
            "headline_en": row["headline_en"],
            "headline_zh": row["headline_zh"],
            "date_logged": row["date_logged"],
            "company_involved": row["company_involved"],
            "incident_topic": row["incident_topic"],
            "claimant_name": row["claimant_name"],
            "categories": json.loads(row["categories"]),
            "severity_score": row["severity_score"],
            "suggested_severity_score": row["suggested_severity_score"],
            "reality_summary": row["reality_summary"],
            "reality_summary_en": row["reality_summary_en"],
            "reality_summary_zh": row["reality_summary_zh"],
            "status": row["status"],
            "matched_claim_id": row["matched_claim_id"],
            "claim_match_confidence": row["claim_match_confidence"],
            "review_notes": row["review_notes"],
            "legitimacy_score": row["legitimacy_score"],
            "legitimacy_label": row["legitimacy_label"],
            "severity_confidence": row["severity_confidence"],
            "severity_reasoning": row["severity_reasoning"],
            "severity_flags": _parse_text_array(row["severity_flags"]),
            "severity_model": row["severity_model"],
            "severity_decision_source": row["severity_decision_source"],
            "legitimacy_reasoning": row["legitimacy_reasoning"],
            "source_validation_summary": row["source_validation_summary"],
            "translation_status": row["translation_status"],
            "review_batch_id": row["review_batch_id"],
            "review_model": row["review_model"],
            "duplicate_status": row["duplicate_status"],
            "duplicate_of_incident_id": row["duplicate_of_incident_id"],
            "canonical_incident_id": row["canonical_incident_id"],
            "duplicate_candidates": self._list_duplicate_candidates(row["id"]),
            "sources": sources_by_incident[row["id"]],
        }

    def update_incident_translation(
        self,
        *,
        incident_id: str,
        company_involved_zh: str,
        headline_zh: str,
        reality_summary_zh: str,
        legitimacy_reasoning_zh: str,
        source_validation_summary_zh: str,
        translation_status: str,
        translated_at: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                update incident_logs
                set
                    company_involved_zh = %s,
                    headline_zh = %s,
                    reality_summary_zh = %s,
                    legitimacy_reasoning_zh = %s,
                    source_validation_summary_zh = %s,
                    translation_status = %s,
                    translated_at = %s,
                    updated_at = current_timestamp
                where id = %s
                """,
                (
                    company_involved_zh,
                    headline_zh,
                    reality_summary_zh,
                    legitimacy_reasoning_zh,
                    source_validation_summary_zh,
                    translation_status,
                    translated_at,
                    incident_id,
                ),
            )
            if cursor.rowcount == 0:
                return None
            incident_row = connection.execute(
                """
                select
                    id,
                    external_id,
                    headline,
                    headline_en,
                    headline_zh,
                    date_logged,
                    company_involved,
                    company_involved_zh,
                    incident_topic,
                    claimant_name,
                    categories,
                    severity_score,
                    suggested_severity_score,
                    reality_summary,
                    reality_summary_en,
                    reality_summary_zh,
                    status,
                    matched_claim_id,
                    claim_match_confidence,
                    review_notes,
                    legitimacy_score,
                    legitimacy_label,
                    severity_confidence,
                    severity_reasoning,
                    severity_flags,
                    severity_model,
                    severity_decision_source,
                    legitimacy_reasoning,
                    legitimacy_reasoning_zh,
                    source_validation_summary,
                    source_validation_summary_zh,
                    translation_status,
                    review_batch_id,
                    review_model,
                    duplicate_status,
                    duplicate_of_incident_id,
                    canonical_incident_id
                from incident_logs
                where id = %s
                """,
                (incident_id,),
            ).fetchone()
            source_rows = connection.execute(
                """
                select
                    id,
                    incident_id,
                    source_url,
                    canonical_url,
                    source_type,
                    publisher,
                    title
                from incident_sources
                where incident_id = %s
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
            "headline_en": row["headline_en"],
            "headline_zh": row["headline_zh"],
            "date_logged": row["date_logged"],
            "company_involved": row["company_involved"],
            "company_involved_zh": row["company_involved_zh"],
            "incident_topic": row["incident_topic"],
            "claimant_name": row["claimant_name"],
            "categories": json.loads(row["categories"]),
            "severity_score": row["severity_score"],
            "suggested_severity_score": row["suggested_severity_score"],
            "reality_summary": row["reality_summary"],
            "reality_summary_en": row["reality_summary_en"],
            "reality_summary_zh": row["reality_summary_zh"],
            "status": row["status"],
            "matched_claim_id": row["matched_claim_id"],
            "claim_match_confidence": row["claim_match_confidence"],
            "review_notes": row["review_notes"],
            "legitimacy_score": row["legitimacy_score"],
            "legitimacy_label": row["legitimacy_label"],
            "severity_confidence": row["severity_confidence"],
            "severity_reasoning": row["severity_reasoning"],
            "severity_flags": _parse_text_array(row["severity_flags"]),
            "severity_model": row["severity_model"],
            "severity_decision_source": row["severity_decision_source"],
            "legitimacy_reasoning": row["legitimacy_reasoning"],
            "source_validation_summary": row["source_validation_summary"],
            "translation_status": row["translation_status"],
            "review_batch_id": row["review_batch_id"],
            "review_model": row["review_model"],
            "duplicate_status": row["duplicate_status"],
            "duplicate_of_incident_id": row["duplicate_of_incident_id"],
            "canonical_incident_id": row["canonical_incident_id"],
            "duplicate_candidates": self._list_duplicate_candidates(row["id"]),
            "sources": sources_by_incident[row["id"]],
        }

    def _group_sources_by_incident(
        self,
        source_rows: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        sources_by_incident: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in source_rows:
            sources_by_incident[row["incident_id"]].append(
                {
                    "id": row["id"],
                    "source_url": row["source_url"],
                    "canonical_url": row.get("canonical_url"),
                    "source_type": row["source_type"],
                    "publisher": row["publisher"],
                    "title": row["title"],
                    "fetch_status": row.get("fetch_status"),
                    "http_status": row.get("http_status"),
                    "evidence_text": row.get("evidence_text"),
                    "fetch_error": row.get("fetch_error"),
                }
            )

        return sources_by_incident

    def _list_duplicate_candidates(self, incident_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                select
                    candidate_incident_id,
                    embedding_score,
                    llm_verdict,
                    confidence,
                    reasoning,
                    status
                from incident_duplicate_candidates
                where incident_id = %s
                order by embedding_score desc, candidate_incident_id asc
                """,
                (incident_id,),
            ).fetchall()
        return [
            {
                "candidate_incident_id": row["candidate_incident_id"],
                "embedding_score": row["embedding_score"],
                "llm_verdict": row["llm_verdict"],
                "confidence": row["confidence"],
                "reasoning": row["reasoning"],
                "status": row["status"],
            }
            for row in rows
        ]

    def _serialize_public_archive_row(
        self,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "id": row["id"],
            "headline": row["headline"],
            "headline_en": row.get("headline_en") or row["headline"],
            "headline_zh": row.get("headline_zh"),
            "date_logged": row["date_logged"],
            "company_involved": row["company_involved"],
            "company_involved_zh": row.get("company_involved_zh"),
            "incident_topic": row.get("incident_topic"),
            "claimant_name": row["claimant_name"],
            "categories": json.loads(row["categories"]),
            "severity_score": row["severity_score"],
            "archive_summary": row["reality_summary"],
            "archive_summary_en": row.get("reality_summary_en")
            or row["reality_summary"],
            "archive_summary_zh": row.get("reality_summary_zh"),
            "status": row["status"],
            "translation_status": row.get("translation_status"),
        }

    def _serialize_public_detail_row(
        self,
        row: dict[str, Any],
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "id": row["id"],
            "headline": row["headline"],
            "headline_en": row.get("headline_en") or row["headline"],
            "headline_zh": row.get("headline_zh"),
            "date_logged": row["date_logged"],
            "company_involved": row["company_involved"],
            "company_involved_zh": row.get("company_involved_zh"),
            "incident_topic": row.get("incident_topic"),
            "claimant_name": row["claimant_name"],
            "categories": json.loads(row["categories"]),
            "severity_score": row["severity_score"],
            "reality_summary": row["reality_summary"],
            "reality_summary_en": row.get("reality_summary_en")
            or row["reality_summary"],
            "reality_summary_zh": row.get("reality_summary_zh"),
            "status": row["status"],
            "translation_status": row.get("translation_status"),
            "analysis": {
                "what_happened_en": row.get("reality_summary_en")
                or row["reality_summary"],
                "what_happened_zh": _sanitize_reader_text(
                    row.get("reality_summary_zh"),
                ),
                "why_it_matters_en": _sanitize_reader_text(
                    row.get("legitimacy_reasoning"),
                ),
                "why_it_matters_zh": _sanitize_reader_text(
                    row.get("legitimacy_reasoning_zh"),
                ),
                "evidence_summary_en": _sanitize_reader_text(
                    row.get("source_validation_summary"),
                )
                or _fallback_public_evidence_summary(sources, locale="en"),
                "evidence_summary_zh": _sanitize_reader_text(
                    row.get("source_validation_summary_zh"),
                )
                or _fallback_public_evidence_summary(sources, locale="zh"),
            },
            "matched_claim": _build_public_claim_payload(row),
            "sources": sources,
        }

    def _connect(self):
        return self._pool.connection()

    def _build_pool(self):
        if ConnectionPool is None or dict_row is None:
            raise ModuleNotFoundError(
                "psycopg and psycopg_pool are required for "
                "PostgreSQL DATABASE_URL values."
            )

        return ConnectionPool(
            self._database_url,
            kwargs={"row_factory": dict_row},
        )

    def _build_public_incident_where(
        self,
        filters: IncidentQueryFilters,
    ) -> tuple[str, list[Any]]:
        where_clauses = ["incident_logs.status = %s"]
        params: list[Any] = ["approved"]

        if filters.category:
            where_clauses.append("incident_logs.categories like %s")
            category_pattern = json.dumps(filters.category).strip('"')
            params.append(f"%{category_pattern}%")
        if filters.company:
            where_clauses.append("incident_logs.company_involved = %s")
            params.append(filters.company)
        if filters.claimant:
            where_clauses.append("incident_logs.claimant_name = %s")
            params.append(filters.claimant)
        if filters.severity_min is not None:
            where_clauses.append("incident_logs.severity_score >= %s")
            params.append(filters.severity_min)
        if filters.severity_max is not None:
            where_clauses.append("incident_logs.severity_score <= %s")
            params.append(filters.severity_max)
        if filters.year is not None:
            where_clauses.append(
                "extract(year from incident_logs.date_logged::date) = %s"
            )
            params.append(filters.year)
        if filters.month is not None:
            where_clauses.append(
                "extract(month from incident_logs.date_logged::date) = %s"
            )
            params.append(filters.month)

        return " and ".join(where_clauses), params

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(_POSTGRES_SCHEMA)
            connection.commit()

    def _execute_many(
        self,
        connection,
        query: str,
        rows: list[tuple[Any, ...]],
    ) -> None:
        for row in rows:
            connection.execute(query, row)


def _build_public_claim_payload(row: dict[str, Any]) -> dict[str, Any] | None:
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


def _parse_text_array(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item)]


def _sanitize_reader_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def _fallback_public_evidence_summary(
    sources: list[dict[str, Any]],
    *,
    locale: str,
) -> str | None:
    source_count = len(sources)
    if source_count == 0:
        return None

    if locale == "zh":
        if source_count == 1:
            return "已通过 1 个已链接来源核实。"

        return f"已通过 {source_count} 个已链接来源核实。"

    if source_count == 1:
        return "Supported by 1 linked source."

    return f"Supported by {source_count} linked sources."
