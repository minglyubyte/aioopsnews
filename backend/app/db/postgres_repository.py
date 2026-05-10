from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from app.db._serializers import (
    group_sources_by_incident,
    serialize_duplicate_candidate_row,
    serialize_duplicate_search_row,
    serialize_internal_incident,
    serialize_llm_pending_row,
    serialize_public_archive_row,
    serialize_public_detail_row,
    serialize_review_queue_row,
    serialize_review_result_row,
    serialize_translation_result_row,
)
from app.models.claim import ClaimRecord
from app.scrapers.rss import RSSArticle
from app.services.claim_matcher import PUBLIC_CLAIM_MATCH_THRESHOLD
from app.services.incident_query import IncidentQueryFilters

try:
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except ModuleNotFoundError:
    dict_row = None
    Jsonb = None

try:
    from psycopg_pool import ConnectionPool
except ModuleNotFoundError:
    ConnectionPool = None

_POSTGRES_SCHEMA = (Path(__file__).parent / "_schema.sql").read_text()


def _jsonb_or_none(value: object | None) -> object | None:
    if value is None or Jsonb is None:
        return value
    return Jsonb(value)


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
                    incident_logs.translation_status,
                    incident_logs.publication_track,
                    incident_logs.evidence_tier,
                    incident_logs.source_family,
                    incident_logs.verification_summary
                from incident_logs
                where {where_sql}
                order by incident_logs.date_logged desc, incident_logs.id asc
                limit %s offset %s
                """,
                (*params, filters.page_size, offset),
            ).fetchall()

        return [serialize_public_archive_row(row) for row in incident_rows]

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
                cross join lateral unnest(incident_logs.categories) as category(value)
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
                    incident_logs.translation_status,
                    incident_logs.publication_track,
                    incident_logs.evidence_tier,
                    incident_logs.source_family,
                    incident_logs.verification_summary
                from incident_logs
                where {where_sql}
                order by incident_logs.date_logged desc, incident_logs.id asc
                limit %s offset %s
                """,
                (*params, filters.page_size, offset),
            ).fetchall()

        total_count = int(count_row["total_count"])
        total_pages = max((total_count + filters.page_size - 1) // filters.page_size, 1)
        return {
            "items": [serialize_public_archive_row(row) for row in incident_rows],
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
                    incident_logs.incident_summary_en,
                    incident_logs.incident_summary_zh,
                    incident_logs.what_happened_en,
                    incident_logs.what_happened_zh,
                    incident_logs.ai_failure_point_en,
                    incident_logs.ai_failure_point_zh,
                    incident_logs.why_it_matters_en,
                    incident_logs.why_it_matters_zh,
                    incident_logs.evidence_summary_en,
                    incident_logs.evidence_summary_zh,
                    incident_logs.legitimacy_reasoning,
                    incident_logs.legitimacy_reasoning_zh,
                    incident_logs.source_validation_summary,
                    incident_logs.source_validation_summary_zh,
                    incident_logs.publication_track,
                    incident_logs.evidence_tier,
                    incident_logs.source_family,
                    incident_logs.verification_summary,
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
                    source_origin,
                    source_registry_key,
                    raw_source_payload,
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

        sources_by_incident = group_sources_by_incident(source_rows)
        return serialize_public_detail_row(
            incident_row,
            sources_by_incident[incident_id],
            match_threshold=PUBLIC_CLAIM_MATCH_THRESHOLD,
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
                    publication_track,
                    evidence_tier,
                    source_family,
                    verification_summary,
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
                    incident_summary_en,
                    incident_summary_zh,
                    what_happened_en,
                    what_happened_zh,
                    ai_failure_point_en,
                    ai_failure_point_zh,
                    why_it_matters_en,
                    why_it_matters_zh,
                    evidence_summary_en,
                    evidence_summary_zh,
                    publication_track,
                    evidence_tier,
                    source_family,
                    verification_summary,
                    translation_status,
                    review_batch_id,
                    review_model,
                    duplicate_status,
                    duplicate_of_incident_id,
                    canonical_incident_id
                from incident_logs
                where status in (%s, %s, %s)
                order by date_logged desc, id asc
                """,
                (
                    "pending_review",
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
                    title,
                    fetch_status,
                    http_status,
                    evidence_text,
                    fetch_error,
                    source_origin,
                    source_registry_key,
                    raw_source_payload
                from incident_sources
                order by published_at desc, id asc
                """
            ).fetchall()

        sources_by_incident = group_sources_by_incident(source_rows)

        return [
            serialize_review_queue_row(
                row,
                sources=sources_by_incident[str(row["id"])],
                duplicate_candidates=self._list_duplicate_candidates(row["id"]),
            )
            for row in incident_rows
        ]

    def list_incidents_pending_llm_review(
        self,
        *,
        source_registry_keys: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        where_sql = "status = %s"
        params: list[object] = ["pending_llm_review"]
        if source_registry_keys:
            where_sql += """
                and exists (
                    select 1
                    from incident_sources
                    where incident_sources.incident_id = incident_logs.id
                    and incident_sources.source_registry_key = any(%s)
                )
            """
            params.append(source_registry_keys)

        with self._connect() as connection:
            incident_rows = connection.execute(
                f"""
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
                    translation_status,
                    publication_track,
                    evidence_tier,
                    source_family,
                    verification_summary
                from incident_logs
                where {where_sql}
                order by date_logged desc, id asc
                """,
                tuple(params),
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
                    fetch_error,
                    source_origin,
                    source_registry_key,
                    raw_source_payload
                from incident_sources
                order by published_at desc, id asc
                """
            ).fetchall()

        sources_by_incident = group_sources_by_incident(source_rows)
        return [
            serialize_llm_pending_row(
                row,
                sources=sources_by_incident[str(row["id"])],
            )
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
                    embedding_vector,
                    publication_track,
                    evidence_tier,
                    source_family,
                    verification_summary
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

        sources_by_incident = group_sources_by_incident(source_rows)
        return serialize_internal_incident(
            incident_row,
            sources=sources_by_incident[incident_id],
            duplicate_candidates=self._list_duplicate_candidates(incident_id),
        )

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
                    embedding_vector,
                    publication_track,
                    evidence_tier,
                    source_family,
                    verification_summary
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

        sources_by_incident = group_sources_by_incident(source_rows)
        return [
            serialize_duplicate_search_row(
                row,
                    sources=sources_by_incident[str(row["id"])],
            )
            for row in incident_rows
        ]

    def get_filter_values(self) -> dict[str, object]:
        with self._connect() as connection:
            category_rows = connection.execute(
                """
                select distinct category.value as category
                from incident_logs
                cross join lateral unnest(incident_logs.categories) as category(value)
                where incident_logs.status = %s
                order by category.value asc
                """,
                ("approved",),
            ).fetchall()
            claimant_rows = connection.execute(
                """
                select distinct incident_logs.claimant_name
                from incident_logs
                where incident_logs.status = %s
                  and incident_logs.claimant_name is not null
                order by incident_logs.claimant_name asc
                """,
                ("approved",),
            ).fetchall()
            company_rows = connection.execute(
                """
                select
                    incident_logs.company_involved as company,
                    max(incident_logs.company_involved_zh) as company_zh
                from incident_logs
                where incident_logs.status = %s
                  and incident_logs.company_involved is not null
                group by incident_logs.company_involved
                order by incident_logs.company_involved asc
                """,
                ("approved",),
            ).fetchall()
            track_rows = connection.execute(
                """
                select distinct incident_logs.publication_track
                from incident_logs
                where incident_logs.status = %s
                  and incident_logs.publication_track is not null
                order by incident_logs.publication_track asc
                """,
                ("approved",),
            ).fetchall()
            family_rows = connection.execute(
                """
                select distinct incident_logs.source_family
                from incident_logs
                where incident_logs.status = %s
                  and incident_logs.source_family is not null
                order by incident_logs.source_family asc
                """,
                ("approved",),
            ).fetchall()
            date_rows = connection.execute(
                """
                select incident_logs.date_logged
                from incident_logs
                where incident_logs.status = %s
                  and incident_logs.date_logged is not null
                """,
                ("approved",),
            ).fetchall()

        categories = [row["category"] for row in category_rows]
        claimants = [row["claimant_name"] for row in claimant_rows]
        companies = [row["company"] for row in company_rows]
        company_labels_zh = {
            row["company"]: row.get("company_zh") for row in company_rows
        }
        publication_tracks = [row["publication_track"] for row in track_rows]
        source_families = [row["source_family"] for row in family_rows]
        archive_pairs = sorted(
            {
                tuple(map(int, str(row["date_logged"]).split("-")[:2]))
                for row in date_rows
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
            "publication_tracks": publication_tracks,
            "source_families": source_families,
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

            incident_id = str(uuid4())
            source_id = str(uuid4())

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
                    translation_status,
                    publication_track,
                    evidence_tier,
                    source_family,
                    verification_summary
                ) values (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s
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
                    [],
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
                    "accident_watch",
                    "reported_unconfirmed",
                    "other",
                    (
                        "RSS discovery found reporting that needs source "
                        "verification before publication."
                    ),
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
                    source_origin,
                    source_registry_key,
                    raw_source_payload,
                    is_primary
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    source_id,
                    incident_id,
                    article.url,
                    article.source_type,
                    article.publisher,
                    article.title,
                    article.published_at.isoformat(),
                    "search_discovery",
                    article.source_key,
                    {"source_key": article.source_key},
                    False,
                ),
            )
            connection.commit()

        return True

    def incident_exists_by_external_id(self, external_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                select 1
                from incident_logs
                where external_id = %s
                limit 1
                """,
                (external_id,),
            ).fetchone()
        return row is not None

    def source_url_exists(self, source_url: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                select 1
                from incident_sources
                where source_url = %s
                limit 1
                """,
                (source_url,),
            ).fetchone()
        return row is not None

    def count_incidents_by_source_registry_keys(
        self,
        source_registry_keys: list[str],
    ) -> int:
        if not source_registry_keys:
            return 0
        placeholders = ", ".join(["%s"] * len(source_registry_keys))
        with self._connect() as connection:
            row = connection.execute(
                f"""
                select count(distinct incident_logs.id) as count
                from incident_logs
                join incident_sources
                    on incident_sources.incident_id = incident_logs.id
                where incident_sources.source_registry_key in ({placeholders})
                """,
                tuple(source_registry_keys),
            ).fetchone()
        return int(row["count"] if row else 0)

    def upgrade_watch_incident_to_verified_accident(
        self,
        incident_id: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            result = connection.execute(
                """
                update incident_logs
                set
                    status = %s,
                    publication_track = %s,
                    evidence_tier = %s,
                    translation_status = %s,
                    review_batch_id = null,
                    review_model = null,
                    reviewed_at = null,
                    verification_summary = %s,
                    review_notes = trim(concat(coalesce(review_notes, ''), ' ', %s)),
                    updated_at = current_timestamp
                where id = %s
                  and publication_track = %s
                """,
                (
                    "pending_llm_review",
                    "verified_accident",
                    "developing",
                    "not_requested",
                    (
                        "Manually upgraded from AI news discovery into AI accident "
                        "review; source metadata is preserved, and accident "
                        "verification is pending."
                    ),
                    "Manually upgraded from AI news discovery.",
                    incident_id,
                    "accident_watch",
                ),
            )
            connection.commit()

        if result.rowcount == 0:
            return None
        return self.get_incident(incident_id)

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
                    categories,
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
                    categories,
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
                    incident_summary_en,
                    incident_summary_zh,
                    what_happened_en,
                    what_happened_zh,
                    ai_failure_point_en,
                    ai_failure_point_zh,
                    why_it_matters_en,
                    why_it_matters_zh,
                    evidence_summary_en,
                    evidence_summary_zh,
                    publication_track,
                    evidence_tier,
                    source_family,
                    verification_summary,
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

        sources_by_incident = group_sources_by_incident(source_rows)
        row = incident_row
        assert row is not None
        return serialize_review_queue_row(
            row,
            sources=sources_by_incident[str(row["id"])],
            duplicate_candidates=self._list_duplicate_candidates(row["id"]),
        )

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
                        str(uuid4()),
                        claim_id,
                        source_url,
                        "primary",
                        display_order,
                    )
                )
            for display_order, source_url in enumerate(secondary_source_links):
                source_rows.append(
                    (
                        str(uuid4()),
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
        publication_track: str | None = None,
        evidence_tier: str | None = None,
        source_family: str | None = None,
        verification_summary: str | None = None,
        source_origin: str | None = None,
        source_registry_key: str | None = None,
        source_evidence_texts: list[str | None] | None = None,
        raw_source_payloads: list[dict[str, object] | None] | None = None,
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
                incident_id["id"] if incident_id is not None else str(uuid4())
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
                    translated_at,
                    publication_track,
                    evidence_tier,
                    source_family,
                    verification_summary
                ) values (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                on conflict (id) do update
                set
                    external_id = excluded.external_id,
                    headline = excluded.headline,
                    headline_en = excluded.headline_en,
                    headline_zh = coalesce(
                        incident_logs.headline_zh,
                        excluded.headline_zh
                    ),
                    date_logged = excluded.date_logged,
                    company_involved = excluded.company_involved,
                    incident_topic = excluded.incident_topic,
                    reality_summary = excluded.reality_summary,
                    reality_summary_en = excluded.reality_summary_en,
                    reality_summary_zh = coalesce(
                        incident_logs.reality_summary_zh,
                        excluded.reality_summary_zh
                    ),
                    status = case
                        when incident_logs.status = 'approved' then incident_logs.status
                        else excluded.status
                    end,
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
                    translation_status = case
                        when incident_logs.translation_status = 'completed'
                            then incident_logs.translation_status
                        else excluded.translation_status
                    end,
                    review_batch_id = excluded.review_batch_id,
                    review_model = excluded.review_model,
                    reviewed_at = excluded.reviewed_at,
                    translated_at = coalesce(
                        incident_logs.translated_at,
                        excluded.translated_at
                    ),
                    publication_track = excluded.publication_track,
                    evidence_tier = excluded.evidence_tier,
                    source_family = excluded.source_family,
                    verification_summary = excluded.verification_summary,
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
                    [],
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
                    publication_track or "accident_watch",
                    evidence_tier or "developing",
                    source_family or "other",
                    verification_summary,
                ),
            )
            connection.execute(
                "delete from incident_sources where incident_id = %s",
                (resolved_incident_id,),
            )
            source_rows: list[tuple[object, ...]] = []
            for display_order, source_url in enumerate(source_links):
                raw_source_payload = None
                if raw_source_payloads and display_order < len(raw_source_payloads):
                    raw_source_payload = raw_source_payloads[display_order]
                source_evidence_text = None
                if (
                    source_evidence_texts
                    and display_order < len(source_evidence_texts)
                ):
                    source_evidence_text = source_evidence_texts[display_order]
                canonical_url = source_url if source_evidence_text else None
                fetch_status = "fetched" if source_evidence_text else None
                source_rows.append(
                    (
                        str(uuid4()),
                        resolved_incident_id,
                        source_url,
                        canonical_url,
                        "imported",
                        None,
                        None,
                        None,
                        fetch_status,
                        None,
                        source_evidence_text,
                        None,
                        source_origin or "manual_import",
                        source_registry_key,
                        _jsonb_or_none(raw_source_payload),
                        display_order == 0,
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
                    source_origin,
                    source_registry_key,
                    raw_source_payload,
                    is_primary
                ) values (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
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
        raw_source_payload: dict[str, object] | None = None,
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
                    fetched_at = %s,
                    raw_source_payload = coalesce(%s, raw_source_payload)
                where id = %s
                """,
                (
                    canonical_url,
                    fetch_status,
                    http_status,
                    evidence_text,
                    fetch_error,
                    fetched_at,
                    _jsonb_or_none(raw_source_payload),
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
                (embedding_model, _jsonb_or_none(embedding_vector), incident_id),
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
                        str(uuid4()),
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
            existing_source_urls = {row["source_url"] for row in existing_source_rows}
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
                        str(uuid4()),
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
        incident_summary_en: str | None = None,
        what_happened_en: str | None = None,
        ai_failure_point_en: str | None = None,
        why_it_matters_en: str | None = None,
        evidence_summary_en: str | None = None,
        publication_track: str | None = None,
        evidence_tier: str | None = None,
        source_family: str | None = None,
        verification_summary: str | None = None,
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
                    incident_summary_en = %s,
                    what_happened_en = %s,
                    ai_failure_point_en = %s,
                    why_it_matters_en = %s,
                    evidence_summary_en = %s,
                    publication_track = coalesce(%s, publication_track),
                    evidence_tier = coalesce(%s, evidence_tier),
                    source_family = coalesce(%s, source_family),
                    verification_summary = coalesce(%s, verification_summary),
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
                    categories,
                    severity_score,
                    suggested_severity_score,
                    severity_confidence,
                    severity_reasoning,
                    severity_flags,
                    severity_model,
                    severity_decision_source,
                    legitimacy_score,
                    legitimacy_label,
                    legitimacy_reasoning,
                    source_validation_summary,
                    incident_summary_en,
                    what_happened_en,
                    ai_failure_point_en,
                    why_it_matters_en,
                    evidence_summary_en,
                    publication_track,
                    evidence_tier,
                    source_family,
                    verification_summary,
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
                    incident_summary_en,
                    what_happened_en,
                    ai_failure_point_en,
                    why_it_matters_en,
                    evidence_summary_en,
                    publication_track,
                    evidence_tier,
                    source_family,
                    verification_summary,
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
                    fetch_error,
                    source_origin,
                    source_registry_key,
                    raw_source_payload
                from incident_sources
                where incident_id = %s
                order by published_at desc, id asc
                """,
                (incident_id,),
            ).fetchall()
            connection.commit()

        sources_by_incident = group_sources_by_incident(source_rows)
        row = incident_row
        assert row is not None
        return serialize_review_result_row(
            row,
            sources=sources_by_incident[str(row["id"])],
            duplicate_candidates=self._list_duplicate_candidates(row["id"]),
        )

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
        incident_summary_zh: str | None = None,
        what_happened_zh: str | None = None,
        ai_failure_point_zh: str | None = None,
        why_it_matters_zh: str | None = None,
        evidence_summary_zh: str | None = None,
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
                    incident_summary_zh = %s,
                    what_happened_zh = %s,
                    ai_failure_point_zh = %s,
                    why_it_matters_zh = %s,
                    evidence_summary_zh = %s,
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
                    incident_summary_zh,
                    what_happened_zh,
                    ai_failure_point_zh,
                    why_it_matters_zh,
                    evidence_summary_zh,
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
                    incident_summary_en,
                    incident_summary_zh,
                    what_happened_en,
                    what_happened_zh,
                    ai_failure_point_en,
                    ai_failure_point_zh,
                    why_it_matters_en,
                    why_it_matters_zh,
                    evidence_summary_en,
                    evidence_summary_zh,
                    publication_track,
                    evidence_tier,
                    source_family,
                    verification_summary,
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

        sources_by_incident = group_sources_by_incident(source_rows)
        row = incident_row
        assert row is not None
        return serialize_translation_result_row(
            row,
            sources=sources_by_incident[str(row["id"])],
            duplicate_candidates=self._list_duplicate_candidates(row["id"]),
        )

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
        return [serialize_duplicate_candidate_row(row) for row in rows]

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
            where_clauses.append("%s = any(incident_logs.categories)")
            params.append(filters.category)
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
        if filters.publication_track:
            where_clauses.append("incident_logs.publication_track = %s")
            params.append(filters.publication_track)
        if filters.source_family:
            where_clauses.append("incident_logs.source_family = %s")
            params.append(filters.source_family)
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
