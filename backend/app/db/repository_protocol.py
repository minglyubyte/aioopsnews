from __future__ import annotations

from typing import Any, Protocol

from app.models.claim import ClaimRecord
from app.scrapers.rss import RSSArticle
from app.services.incident_query import IncidentQueryFilters


class IncidentRepository(Protocol):
    def close(self) -> None: ...

    def list_public_incidents(
        self,
        filters: IncidentQueryFilters,
    ) -> list[dict[str, Any]]: ...

    def get_public_incident(self, incident_id: str) -> dict[str, Any] | None: ...

    def get_filter_values(self) -> dict[str, object]: ...

    def list_review_queue(self) -> list[dict[str, Any]]: ...

    def ingest_rss_article(
        self,
        article: RSSArticle,
        *,
        ingestion_run_id: str,
    ) -> bool: ...

    def list_pending_incidents(self) -> list[dict[str, Any]]: ...

    def list_claims(self) -> list[ClaimRecord]: ...

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
    ) -> None: ...

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
    ) -> dict[str, Any] | None: ...

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
    ) -> None: ...
