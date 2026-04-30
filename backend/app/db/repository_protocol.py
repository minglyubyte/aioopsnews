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

    def list_incidents_pending_llm_review(self) -> list[dict[str, Any]]: ...

    def get_incident(self, incident_id: str) -> dict[str, Any] | None: ...

    def list_duplicate_search_pool(
        self,
        *,
        incident_id: str,
        date_logged: str,
        date_window_days: int,
    ) -> list[dict[str, Any]]: ...

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
    ) -> None: ...

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
    ) -> None: ...

    def update_incident_embedding(
        self,
        *,
        incident_id: str,
        embedding_model: str,
        embedding_vector: list[float],
    ) -> None: ...

    def replace_duplicate_candidates(
        self,
        *,
        incident_id: str,
        candidates: list[dict[str, Any]],
    ) -> None: ...

    def merge_duplicate_incident(
        self,
        *,
        duplicate_incident_id: str,
        canonical_incident_id: str,
        duplicate_status: str,
        reasoning: str,
        confidence: float,
    ) -> None: ...

    def mark_incidents_review_batch(
        self,
        *,
        incident_ids: list[str],
        review_batch_id: str,
        review_model: str,
    ) -> None: ...

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
        review_model: str,
        review_batch_id: str,
        reviewed_at: str,
    ) -> dict[str, Any] | None: ...

    def update_incident_translation(
        self,
        *,
        incident_id: str,
        headline_zh: str,
        reality_summary_zh: str,
        translation_status: str,
        translated_at: str,
    ) -> dict[str, Any] | None: ...
