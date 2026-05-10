from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
from typing import Any

from app.core.incident_metadata import (
    DEFAULT_EVIDENCE_TIER,
    DEFAULT_PUBLICATION_TRACK,
    DEFAULT_SOURCE_FAMILY,
    DEFAULT_VERIFICATION_SUMMARY,
)
from app.models.claim import ClaimRecord
from app.scrapers.rss import RSSArticle
from app.services.autonomous_vehicle_details import (
    assess_autonomous_vehicle_detail_quality,
)
from app.services.claim_matcher import PUBLIC_CLAIM_MATCH_THRESHOLD
from app.services.incident_query import IncidentQueryFilters


class InMemoryIncidentRepository:
    def __init__(
        self,
        *,
        claims: list[dict[str, Any]] | None = None,
        incidents: list[dict[str, Any]] | None = None,
        claim_sources: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self.public_filter_calls: list[IncidentQueryFilters] = []
        self.claims: dict[str, dict[str, Any]] = {}
        self.claim_sources: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.incidents: dict[str, dict[str, Any]] = {}
        self.duplicate_candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._source_urls: set[str] = set()
        self._incident_sequence = 0
        self._source_sequence = 0

        for claim in claims or []:
            self.claims[claim["id"]] = deepcopy(claim)

        for claim_id, sources in (claim_sources or {}).items():
            self.claim_sources[claim_id] = deepcopy(sources)

        for incident in incidents or []:
            cloned = deepcopy(incident)
            self.incidents[cloned["id"]] = cloned
            self._incident_sequence += 1
            for source in cloned.get("sources", []):
                self._source_urls.add(source["source_url"])
                self._source_sequence += 1

    def list_public_incidents(
        self,
        filters: IncidentQueryFilters,
    ) -> list[dict[str, Any]]:
        self.public_filter_calls.append(filters)
        incidents = self._filter_public_incidents(filters)
        offset = (filters.page - 1) * filters.page_size
        window = incidents[offset : offset + filters.page_size]
        return [
            self._serialize_public_archive_incident(incident)
            for incident in window
        ]

    def list_public_incident_feed(
        self,
        filters: IncidentQueryFilters,
    ) -> dict[str, Any]:
        incidents = self._filter_public_incidents(filters)
        total_count = len(incidents)
        total_pages = max((total_count + filters.page_size - 1) // filters.page_size, 1)
        offset = (filters.page - 1) * filters.page_size
        window = incidents[offset : offset + filters.page_size]
        category_counts = Counter(
            category
            for incident in incidents
            for category in incident.get("categories", [])
        )
        company_counts = Counter(
            incident["company_involved"] for incident in incidents
        )

        return {
            "items": [
                self._serialize_public_archive_incident(incident)
                for incident in window
            ],
            "page": filters.page,
            "page_size": filters.page_size,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_next_page": filters.page < total_pages,
            "has_previous_page": filters.page > 1,
            "slice_summary": {
                "total_matches": total_count,
                "newest_logged": incidents[0]["date_logged"] if incidents else None,
                "oldest_logged": incidents[-1]["date_logged"] if incidents else None,
                "highest_severity": max(
                    (incident["severity_score"] for incident in incidents),
                    default=None,
                ),
                "top_categories": [
                    {"category": category, "count": count}
                    for category, count in sorted(
                        category_counts.items(),
                        key=lambda item: (-item[1], item[0]),
                    )
                ],
                "top_companies": [
                    {
                        "company": company,
                        "company_zh": next(
                            (
                                incident.get("company_involved_zh")
                                for incident in incidents
                                if incident["company_involved"] == company
                                and incident.get("company_involved_zh")
                            ),
                            None,
                        ),
                        "count": count,
                    }
                    for company, count in sorted(
                        company_counts.items(),
                        key=lambda item: (-item[1], item[0]),
                    )
                ],
            },
        }

    def close(self) -> None:
        return None

    def get_public_incident(self, incident_id: str) -> dict[str, Any] | None:
        incident = self.incidents.get(incident_id)
        if incident is None or incident["status"] != "approved":
            return None
        return self._serialize_public_detail_incident(incident)

    def get_filter_values(self) -> dict[str, object]:
        incidents = [
            self._serialize_public_archive_incident(incident)
            for incident in self._filter_public_incidents(IncidentQueryFilters())
        ]

        categories = sorted(
            {category for incident in incidents for category in incident["categories"]}
        )
        claimants = sorted(
            {
                incident["claimant_name"]
                for incident in incidents
                if incident.get("claimant_name")
            }
        )
        companies = sorted({incident["company_involved"] for incident in incidents})
        publication_tracks = sorted(
            {incident["publication_track"] for incident in incidents}
        )
        source_families = sorted(
            {incident["source_family"] for incident in incidents}
        )
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
                tuple(map(int, incident["date_logged"].split("-")[:2]))
                for incident in incidents
            },
            reverse=True,
        )
        years = sorted({year for year, _ in archive_pairs}, reverse=True)
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

    def list_review_queue(self) -> list[dict[str, Any]]:
        incidents = [
            incident
            for incident in self.incidents.values()
            if incident["status"]
            in {
                "pending_review",
                "pending_llm_escalation",
                "pending_duplicate_review",
            }
        ]
        incidents.sort(
            key=lambda incident: (incident["date_logged"], incident["id"]),
            reverse=True,
        )
        return [self._serialize_admin_incident(incident) for incident in incidents]

    def ingest_rss_article(
        self,
        article: RSSArticle,
        *,
        ingestion_run_id: str,
    ) -> bool:
        if article.url in self._source_urls:
            return False

        self._incident_sequence += 1
        incident_id = f"incident-{self._incident_sequence}"
        self._source_sequence += 1
        source_id = f"source-{self._source_sequence}"
        self._source_urls.add(article.url)
        self.incidents[incident_id] = {
            "id": incident_id,
            "external_id": None,
            "headline": article.title,
            "headline_en": article.title,
            "headline_zh": None,
            "date_logged": article.published_at.date().isoformat(),
            "company_involved": "Pending classification",
            "incident_topic": None,
            "claimant_name": None,
            "categories": [],
            "severity_score": 1,
            "suggested_severity_score": None,
            "reality_summary": article.summary,
            "reality_summary_en": article.summary,
            "reality_summary_zh": None,
            "status": "pending_review",
            "ingestion_run_id": ingestion_run_id,
            "confidence_score": None,
            "severity_confidence": None,
            "severity_reasoning": None,
            "severity_flags": [],
            "severity_model": None,
            "severity_decision_source": None,
            "review_notes": (
                f"Ingested from {article.publisher} RSS feed; "
                "awaiting enrichment and editorial review."
            ),
            "matched_claim_id": None,
            "claim_match_confidence": None,
            "legitimacy_score": None,
            "legitimacy_label": None,
            "legitimacy_reasoning": None,
            "legitimacy_reasoning_zh": None,
            "source_validation_summary": None,
            "source_validation_summary_zh": None,
            "legitimacy_flag": None,
            "confidence_level": None,
            "import_notes": None,
            "translation_status": "not_requested",
            "publication_track": DEFAULT_PUBLICATION_TRACK,
            "evidence_tier": "reported_unconfirmed",
            "source_family": DEFAULT_SOURCE_FAMILY,
            "verification_summary": (
                "RSS discovery found reporting that needs source verification "
                "before publication."
            ),
            "review_batch_id": None,
            "review_model": None,
            "reviewed_at": None,
            "translated_at": None,
            "sources": [
                {
                    "id": source_id,
                    "source_url": article.url,
                    "canonical_url": None,
                    "source_type": article.source_type,
                    "publisher": article.publisher,
                    "title": article.title,
                    "fetch_status": None,
                    "http_status": None,
                    "evidence_text": None,
                    "fetch_error": None,
                    "source_origin": "search_discovery",
                    "source_registry_key": article.source_key,
                    "raw_source_payload": {"source_key": article.source_key},
                }
            ],
        }
        return True

    def incident_exists_by_external_id(self, external_id: str) -> bool:
        return any(
            incident.get("external_id") == external_id
            for incident in self.incidents.values()
        )

    def source_url_exists(self, source_url: str) -> bool:
        return source_url in self._source_urls

    def upgrade_watch_incident_to_verified_accident(
        self,
        incident_id: str,
    ) -> dict[str, Any] | None:
        incident = self.incidents.get(incident_id)
        if incident is None or incident.get("publication_track") != "accident_watch":
            return None

        incident["status"] = "pending_llm_review"
        incident["publication_track"] = "verified_accident"
        incident["evidence_tier"] = "developing"
        incident["translation_status"] = "not_requested"
        incident["review_batch_id"] = None
        incident["review_model"] = None
        incident["reviewed_at"] = None
        incident["verification_summary"] = (
            "Manually upgraded from AI news discovery into AI accident review; "
            "source metadata is preserved, and accident verification is pending."
        )
        incident["review_notes"] = (
            ((incident.get("review_notes") or "") + " ").strip()
            + "Manually upgraded from AI news discovery."
        ).strip()
        return self._serialize_admin_incident(incident)

    def list_pending_incidents(self) -> list[dict[str, Any]]:
        incidents = [
            incident
            for incident in self.incidents.values()
            if incident["status"] == "pending_review"
        ]
        incidents.sort(
            key=lambda incident: (incident["date_logged"], incident["id"]),
            reverse=True,
        )
        return [
            {
                "id": incident["id"],
                "headline": incident["headline"],
                "date_logged": incident["date_logged"],
                "source_summary": incident["reality_summary"],
                "publisher": incident["sources"][0]["publisher"]
                if incident["sources"]
                else None,
                "source_title": incident["sources"][0]["title"]
                if incident["sources"]
                else None,
                "source_url": incident["sources"][0]["source_url"]
                if incident["sources"]
                else None,
            }
            for incident in incidents
        ]

    def list_incidents_pending_llm_review(self) -> list[dict[str, Any]]:
        incidents = [
            incident
            for incident in self.incidents.values()
            if incident["status"] == "pending_llm_review"
        ]
        incidents.sort(
            key=lambda incident: (incident["date_logged"], incident["id"]),
            reverse=True,
        )
        return [self._serialize_admin_incident(incident) for incident in incidents]

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        incident = self.incidents.get(incident_id)
        return deepcopy(incident) if incident is not None else None

    def list_duplicate_search_pool(
        self,
        *,
        incident_id: str,
        date_logged: str,
        date_window_days: int,
    ) -> list[dict[str, Any]]:
        from datetime import date, timedelta

        target_date = date.fromisoformat(date_logged)
        earliest = target_date - timedelta(days=date_window_days)
        latest = target_date + timedelta(days=date_window_days)
        incidents = [
            deepcopy(incident)
            for candidate_id, incident in self.incidents.items()
            if candidate_id != incident_id
            and incident["status"] != "duplicate_confirmed"
            and earliest <= date.fromisoformat(incident["date_logged"]) <= latest
        ]
        incidents.sort(key=lambda incident: (incident["date_logged"], incident["id"]))
        return incidents

    def list_claims(self) -> list[ClaimRecord]:
        claims = [
            claim
            for claim in self.claims.values()
            if claim["status"] in {"seeded", "approved"}
        ]
        claims.sort(key=lambda claim: (claim["claim_date"], claim["id"]), reverse=True)
        return [
            ClaimRecord(
                id=claim["id"],
                claimant_name=claim["claimant_name"],
                company_involved=claim["company_involved"],
                original_claim=claim["original_claim"],
                claim_date=claim["claim_date"],
                claim_topic=claim["claim_topic"],
                status=claim["status"],
                notes=claim.get("notes"),
            )
            for claim in claims
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
        incident = self.incidents[incident_id]
        incident.update(
            {
                "company_involved": company_involved,
                "claimant_name": claimant_name,
                "categories": categories,
                "reality_summary": reality_summary,
                "confidence_score": confidence_score,
                "review_notes": review_notes,
                "matched_claim_id": matched_claim_id,
                "claim_match_confidence": claim_match_confidence,
            }
        )

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
        incident = self.incidents.get(incident_id)
        if incident is None:
            return None

        incident.update(
            {
                "status": status,
                "company_involved": company_involved,
                "claimant_name": claimant_name,
                "categories": categories,
                "severity_score": severity_score,
                "severity_decision_source": (
                    "editor"
                    if severity_score != incident.get("suggested_severity_score")
                    else incident.get("severity_decision_source")
                ),
                "reality_summary": reality_summary,
                "matched_claim_id": matched_claim_id,
                "claim_match_confidence": claim_match_confidence,
                "review_notes": review_notes,
            }
        )
        return self._serialize_admin_incident(incident)

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
        self.claims[claim_id] = {
            "id": claim_id,
            "claimant_name": claimant_name,
            "company_involved": company_involved,
            "original_claim": original_claim,
            "claim_date": claim_date,
            "claim_topic": claim_topic,
            "status": status,
            "notes": notes,
        }
        sources: list[dict[str, Any]] = []
        for display_order, url in enumerate(primary_source_links):
            sources.append(
                {
                    "source_url": url,
                    "source_kind": "primary",
                    "display_order": display_order,
                }
            )
        for display_order, url in enumerate(secondary_source_links):
            sources.append(
                {
                    "source_url": url,
                    "source_kind": "secondary",
                    "display_order": display_order,
                }
            )
        self.claim_sources[claim_id] = sources

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
        raw_source_payloads: list[dict[str, object] | None] | None = None,
    ) -> None:
        existing_incident_id = next(
            (
                incident_id
                for incident_id, incident in self.incidents.items()
                if incident.get("external_id") == external_id
            ),
            None,
        )
        if existing_incident_id is None:
            self._incident_sequence += 1
            incident_id = f"incident-{self._incident_sequence}"
        else:
            incident_id = existing_incident_id

        sources: list[dict[str, Any]] = []
        for display_order, url in enumerate(source_links):
            raw_source_payload = None
            if raw_source_payloads and display_order < len(raw_source_payloads):
                raw_source_payload = raw_source_payloads[display_order]
            self._source_sequence += 1
            sources.append(
                {
                    "id": f"source-{self._source_sequence}",
                    "source_url": url,
                    "canonical_url": None,
                    "source_type": "imported",
                    "publisher": None,
                    "title": None,
                    "fetch_status": None,
                    "http_status": None,
                    "evidence_text": None,
                    "fetch_error": None,
                    "source_origin": source_origin or "manual_import",
                    "source_registry_key": source_registry_key,
                    "raw_source_payload": raw_source_payload,
                    "is_primary": display_order == 0,
                }
            )
            self._source_urls.add(url)

        self.incidents[incident_id] = {
            "id": incident_id,
            "external_id": external_id,
            "headline": headline,
            "headline_en": headline,
            "headline_zh": headline_zh,
            "date_logged": date_logged,
            "company_involved": company_involved,
            "incident_topic": incident_topic,
            "claimant_name": None,
            "categories": [],
            "severity_score": 3,
            "suggested_severity_score": None,
            "reality_summary": reality_summary,
            "reality_summary_en": reality_summary,
            "reality_summary_zh": reality_summary_zh,
            "status": status,
            "ingestion_run_id": None,
            "confidence_score": legitimacy_score,
            "severity_confidence": None,
            "severity_reasoning": None,
            "severity_flags": [],
            "severity_model": None,
            "severity_decision_source": None,
            "review_notes": legitimacy_reasoning,
            "matched_claim_id": matched_claim_id,
            "claim_match_confidence": None,
            "legitimacy_score": legitimacy_score,
            "legitimacy_label": legitimacy_label,
            "legitimacy_reasoning": legitimacy_reasoning,
            "source_validation_summary": source_validation_summary,
            "legitimacy_flag": legitimacy_flag,
            "confidence_level": confidence_level,
            "import_notes": import_notes,
            "translation_status": translation_status,
            "publication_track": publication_track or DEFAULT_PUBLICATION_TRACK,
            "evidence_tier": evidence_tier or DEFAULT_EVIDENCE_TIER,
            "source_family": source_family or DEFAULT_SOURCE_FAMILY,
            "verification_summary": verification_summary
            or DEFAULT_VERIFICATION_SUMMARY,
            "review_batch_id": None,
            "review_model": None,
            "reviewed_at": None,
            "translated_at": "2026-04-30T12:00:00" if headline_zh else None,
            "duplicate_status": None,
            "duplicate_of_incident_id": None,
            "canonical_incident_id": None,
            "embedding_model": None,
            "embedding_vector": None,
            "sources": sources,
        }

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
        for incident in self.incidents.values():
            for source in incident.get("sources", []):
                if source["id"] != source_id:
                    continue
                source.update(
                    {
                        "canonical_url": canonical_url,
                        "fetch_status": fetch_status,
                        "http_status": http_status,
                        "evidence_text": evidence_text,
                        "fetch_error": fetch_error,
                        "fetched_at": fetched_at,
                    }
                )
                return

    def mark_incidents_review_batch(
        self,
        *,
        incident_ids: list[str],
        review_batch_id: str,
        review_model: str,
    ) -> None:
        for incident_id in incident_ids:
            incident = self.incidents[incident_id]
            incident["review_batch_id"] = review_batch_id
            incident["review_model"] = review_model

    def update_incident_embedding(
        self,
        *,
        incident_id: str,
        embedding_model: str,
        embedding_vector: list[float],
    ) -> None:
        incident = self.incidents[incident_id]
        incident["embedding_model"] = embedding_model
        incident["embedding_vector"] = list(embedding_vector)

    def replace_duplicate_candidates(
        self,
        *,
        incident_id: str,
        candidates: list[dict[str, Any]],
    ) -> None:
        self.duplicate_candidates[incident_id] = deepcopy(candidates)
        if incident_id in self.incidents:
            self.incidents[incident_id]["duplicate_candidates"] = deepcopy(candidates)

    def merge_duplicate_incident(
        self,
        *,
        duplicate_incident_id: str,
        canonical_incident_id: str,
        duplicate_status: str,
        reasoning: str,
        confidence: float,
    ) -> None:
        duplicate_incident = self.incidents[duplicate_incident_id]
        canonical_incident = self.incidents[canonical_incident_id]

        duplicate_incident.update(
            {
                "status": "duplicate_confirmed",
                "duplicate_status": duplicate_status,
                "duplicate_of_incident_id": canonical_incident_id,
                "canonical_incident_id": canonical_incident_id,
                "translation_status": "not_requested",
                "review_notes": reasoning,
                "legitimacy_score": confidence,
            }
        )

        duplicate_note = duplicate_incident.get("import_notes")
        if duplicate_note:
            merged_note = (
                f"Merged duplicate {duplicate_incident_id}: {duplicate_note}"
            )
            canonical_note = canonical_incident.get("import_notes")
            canonical_incident["import_notes"] = (
                f"{canonical_note}\n{merged_note}" if canonical_note else merged_note
            )

        existing_urls = {
            source["source_url"] for source in canonical_incident.get("sources", [])
        }
        for source in duplicate_incident.get("sources", []):
            if source["source_url"] in existing_urls:
                continue
            canonical_incident.setdefault("sources", []).append(deepcopy(source))
            existing_urls.add(source["source_url"])

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
        incident = self.incidents.get(incident_id)
        if incident is None:
            return None
        incident.update(
            {
                "status": status,
                "headline": headline_en,
                "headline_en": headline_en,
                "reality_summary": reality_summary_en,
                "reality_summary_en": reality_summary_en,
                "categories": list(categories),
                "severity_score": severity_score,
                "suggested_severity_score": suggested_severity_score,
                "severity_confidence": severity_confidence,
                "severity_reasoning": severity_reasoning,
                "severity_flags": list(severity_flags),
                "severity_model": severity_model,
                "severity_decision_source": severity_decision_source,
                "severity_suggested_at": severity_suggested_at,
                "legitimacy_score": legitimacy_score,
                "legitimacy_label": legitimacy_label,
                "legitimacy_reasoning": legitimacy_reasoning,
                "source_validation_summary": source_validation_summary,
                "incident_summary_en": incident_summary_en,
                "what_happened_en": what_happened_en,
                "ai_failure_point_en": ai_failure_point_en,
                "why_it_matters_en": why_it_matters_en,
                "evidence_summary_en": evidence_summary_en,
                "publication_track": publication_track
                or incident.get("publication_track", DEFAULT_PUBLICATION_TRACK),
                "evidence_tier": evidence_tier
                or incident.get("evidence_tier", DEFAULT_EVIDENCE_TIER),
                "source_family": source_family
                or incident.get("source_family", DEFAULT_SOURCE_FAMILY),
                "verification_summary": verification_summary
                or incident.get("verification_summary", DEFAULT_VERIFICATION_SUMMARY),
                "review_model": review_model,
                "review_batch_id": review_batch_id,
                "reviewed_at": reviewed_at,
            }
        )
        return self._serialize_admin_incident(incident)

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
        incident = self.incidents.get(incident_id)
        if incident is None:
            return None
        incident.update(
            {
                "company_involved_zh": company_involved_zh,
                "headline_zh": headline_zh,
                "reality_summary_zh": reality_summary_zh,
                "legitimacy_reasoning_zh": legitimacy_reasoning_zh,
                "source_validation_summary_zh": source_validation_summary_zh,
                "incident_summary_zh": incident_summary_zh,
                "what_happened_zh": what_happened_zh,
                "ai_failure_point_zh": ai_failure_point_zh,
                "why_it_matters_zh": why_it_matters_zh,
                "evidence_summary_zh": evidence_summary_zh,
                "translation_status": translation_status,
                "translated_at": translated_at,
            }
        )
        return self._serialize_admin_incident(incident)

    def _serialize_public_archive_incident(
        self,
        incident: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "id": incident["id"],
            "headline": incident["headline"],
            "headline_en": incident.get("headline_en", incident["headline"]),
            "headline_zh": incident.get("headline_zh"),
            "date_logged": incident["date_logged"],
            "company_involved": incident["company_involved"],
            "company_involved_zh": incident.get("company_involved_zh"),
            "incident_topic": incident.get("incident_topic"),
            "claimant_name": incident.get("claimant_name"),
            "categories": list(incident["categories"]),
            "severity_score": incident["severity_score"],
            "archive_summary": incident["reality_summary"],
            "archive_summary_en": incident.get(
                "reality_summary_en",
                incident["reality_summary"],
            ),
            "archive_summary_zh": incident.get("reality_summary_zh"),
            "status": incident["status"],
            "translation_status": incident.get("translation_status"),
            "publication_track": incident.get(
                "publication_track",
                DEFAULT_PUBLICATION_TRACK,
            ),
            "evidence_tier": incident.get("evidence_tier", DEFAULT_EVIDENCE_TIER),
            "source_family": incident.get("source_family", DEFAULT_SOURCE_FAMILY),
            "verification_summary": incident.get(
                "verification_summary",
                DEFAULT_VERIFICATION_SUMMARY,
            ),
        }

    def _serialize_public_detail_incident(
        self,
        incident: dict[str, Any],
    ) -> dict[str, Any]:
        public_sources = _public_detail_sources(incident, incident.get("sources", []))
        detail_quality = assess_autonomous_vehicle_detail_quality(
            {**incident, "sources": public_sources}
        )
        payload = {
            "id": incident["id"],
            "headline": incident["headline"],
            "headline_en": incident.get("headline_en", incident["headline"]),
            "headline_zh": incident.get("headline_zh"),
            "date_logged": incident["date_logged"],
            "company_involved": incident["company_involved"],
            "company_involved_zh": incident.get("company_involved_zh"),
            "incident_topic": incident.get("incident_topic"),
            "claimant_name": incident.get("claimant_name"),
            "categories": list(incident["categories"]),
            "severity_score": incident["severity_score"],
            "reality_summary": incident["reality_summary"],
            "reality_summary_en": incident.get(
                "reality_summary_en",
                incident["reality_summary"],
            ),
            "reality_summary_zh": incident.get("reality_summary_zh"),
            "status": incident["status"],
            "translation_status": incident.get("translation_status"),
            "publication_track": incident.get(
                "publication_track",
                DEFAULT_PUBLICATION_TRACK,
            ),
            "evidence_tier": incident.get("evidence_tier", DEFAULT_EVIDENCE_TIER),
            "source_family": incident.get("source_family", DEFAULT_SOURCE_FAMILY),
            "verification_summary": incident.get(
                "verification_summary",
                DEFAULT_VERIFICATION_SUMMARY,
            ),
            "analysis": {
                "incident_summary_en": _sanitize_reader_text(
                    incident.get("incident_summary_en")
                )
                or incident.get("reality_summary_en", incident["reality_summary"]),
                "incident_summary_zh": _sanitize_reader_text(
                    incident.get("incident_summary_zh")
                )
                or _sanitize_reader_text(incident.get("reality_summary_zh")),
                "what_happened_en": _sanitize_reader_text(
                    incident.get("what_happened_en")
                ),
                "what_happened_zh": _sanitize_reader_text(
                    incident.get("what_happened_zh")
                ),
                "ai_failure_point_en": _sanitize_reader_text(
                    incident.get("ai_failure_point_en")
                ),
                "ai_failure_point_zh": _sanitize_reader_text(
                    incident.get("ai_failure_point_zh")
                ),
                "why_it_matters_en": _sanitize_reader_text(
                    incident.get("why_it_matters_en")
                )
                or _sanitize_reader_text(
                    incident.get("legitimacy_reasoning"),
                ),
                "why_it_matters_zh": _sanitize_reader_text(
                    incident.get("why_it_matters_zh")
                )
                or _sanitize_reader_text(
                    incident.get("legitimacy_reasoning_zh")
                ),
                "evidence_summary_en": _sanitize_reader_text(
                    incident.get("evidence_summary_en")
                )
                or _sanitize_reader_text(
                    incident.get("source_validation_summary"),
                ),
                "evidence_summary_zh": _sanitize_reader_text(
                    incident.get("evidence_summary_zh")
                )
                or _sanitize_reader_text(
                    incident.get("source_validation_summary_zh")
                ),
                "detail_quality": detail_quality.detail_quality,
                "detail_quality_reasons": detail_quality.detail_quality_reasons,
                "source_fact_summary": detail_quality.source_fact_summary,
            },
            "matched_claim": None,
            "sources": deepcopy(public_sources),
        }

        matched_claim_id = incident.get("matched_claim_id")
        confidence = incident.get("claim_match_confidence")
        claim = self.claims.get(matched_claim_id) if matched_claim_id else None
        if (
            claim is not None
            and claim["status"] == "approved"
            and confidence is not None
            and confidence >= PUBLIC_CLAIM_MATCH_THRESHOLD
        ):
            payload["matched_claim"] = {
                "id": claim["id"],
                "claimant_name": claim["claimant_name"],
                "company_involved": claim["company_involved"],
                "original_claim": claim["original_claim"],
                "claim_date": claim["claim_date"],
                "claim_topic": claim["claim_topic"],
                "match_confidence": confidence,
            }

        return payload

    def _serialize_admin_incident(self, incident: dict[str, Any]) -> dict[str, Any]:
        detail_quality = assess_autonomous_vehicle_detail_quality(incident)
        return {
            "id": incident["id"],
            "external_id": incident.get("external_id"),
            "headline": incident["headline"],
            "headline_en": incident.get("headline_en", incident["headline"]),
            "headline_zh": incident.get("headline_zh"),
            "date_logged": incident["date_logged"],
            "company_involved": incident["company_involved"],
            "company_involved_zh": incident.get("company_involved_zh"),
            "incident_topic": incident.get("incident_topic"),
            "claimant_name": incident.get("claimant_name"),
            "categories": list(incident["categories"]),
            "severity_score": incident["severity_score"],
            "suggested_severity_score": incident.get("suggested_severity_score"),
            "reality_summary": incident["reality_summary"],
            "reality_summary_en": incident.get(
                "reality_summary_en",
                incident["reality_summary"],
            ),
            "reality_summary_zh": incident.get("reality_summary_zh"),
            "status": incident["status"],
            "matched_claim_id": incident.get("matched_claim_id"),
            "claim_match_confidence": incident.get("claim_match_confidence"),
            "review_notes": incident.get("review_notes"),
            "legitimacy_score": incident.get("legitimacy_score"),
            "legitimacy_label": incident.get("legitimacy_label"),
            "legitimacy_flag": incident.get("legitimacy_flag"),
            "confidence_level": incident.get("confidence_level"),
            "import_notes": incident.get("import_notes"),
            "severity_confidence": incident.get("severity_confidence"),
            "severity_reasoning": incident.get("severity_reasoning"),
            "severity_flags": list(incident.get("severity_flags", [])),
            "severity_model": incident.get("severity_model"),
            "severity_decision_source": incident.get("severity_decision_source"),
            "legitimacy_reasoning": incident.get("legitimacy_reasoning"),
            "source_validation_summary": incident.get("source_validation_summary"),
            "legitimacy_reasoning_zh": incident.get("legitimacy_reasoning_zh"),
            "source_validation_summary_zh": incident.get(
                "source_validation_summary_zh"
            ),
            "incident_summary_en": incident.get("incident_summary_en"),
            "incident_summary_zh": incident.get("incident_summary_zh"),
            "what_happened_en": incident.get("what_happened_en"),
            "what_happened_zh": incident.get("what_happened_zh"),
            "ai_failure_point_en": incident.get("ai_failure_point_en"),
            "ai_failure_point_zh": incident.get("ai_failure_point_zh"),
            "why_it_matters_en": incident.get("why_it_matters_en"),
            "why_it_matters_zh": incident.get("why_it_matters_zh"),
            "evidence_summary_en": incident.get("evidence_summary_en"),
            "evidence_summary_zh": incident.get("evidence_summary_zh"),
            "translation_status": incident.get("translation_status"),
            "publication_track": incident.get(
                "publication_track",
                DEFAULT_PUBLICATION_TRACK,
            ),
            "evidence_tier": incident.get("evidence_tier", DEFAULT_EVIDENCE_TIER),
            "source_family": incident.get("source_family", DEFAULT_SOURCE_FAMILY),
            "verification_summary": incident.get(
                "verification_summary",
                DEFAULT_VERIFICATION_SUMMARY,
            ),
            "review_batch_id": incident.get("review_batch_id"),
            "review_model": incident.get("review_model"),
            "duplicate_status": incident.get("duplicate_status"),
            "duplicate_of_incident_id": incident.get("duplicate_of_incident_id"),
            "canonical_incident_id": incident.get("canonical_incident_id"),
            "duplicate_candidates": deepcopy(
                self.duplicate_candidates.get(incident["id"], [])
            ),
            "sources": deepcopy(incident.get("sources", [])),
            "analysis": {
                "incident_summary_en": incident.get("incident_summary_en"),
                "incident_summary_zh": incident.get("incident_summary_zh"),
                "what_happened_en": incident.get("what_happened_en"),
                "what_happened_zh": incident.get("what_happened_zh"),
                "ai_failure_point_en": incident.get("ai_failure_point_en"),
                "ai_failure_point_zh": incident.get("ai_failure_point_zh"),
                "why_it_matters_en": incident.get("why_it_matters_en"),
                "why_it_matters_zh": incident.get("why_it_matters_zh"),
                "evidence_summary_en": incident.get("evidence_summary_en"),
                "evidence_summary_zh": incident.get("evidence_summary_zh"),
                "detail_quality": detail_quality.detail_quality,
                "detail_quality_reasons": detail_quality.detail_quality_reasons,
                "source_fact_summary": detail_quality.source_fact_summary,
            },
        }

    def _filter_public_incidents(
        self,
        filters: IncidentQueryFilters,
    ) -> list[dict[str, Any]]:
        incidents = [
            incident
            for incident in self.incidents.values()
            if incident["status"] == "approved"
        ]

        if filters.category:
            incidents = [
                incident
                for incident in incidents
                if filters.category in incident["categories"]
            ]
        if filters.company:
            incidents = [
                incident
                for incident in incidents
                if incident["company_involved"] == filters.company
            ]
        if filters.claimant:
            incidents = [
                incident
                for incident in incidents
                if incident.get("claimant_name") == filters.claimant
            ]
        if filters.severity_min is not None:
            incidents = [
                incident
                for incident in incidents
                if incident["severity_score"] >= filters.severity_min
            ]
        if filters.severity_max is not None:
            incidents = [
                incident
                for incident in incidents
                if incident["severity_score"] <= filters.severity_max
            ]
        if filters.publication_track:
            incidents = [
                incident
                for incident in incidents
                if incident.get("publication_track", DEFAULT_PUBLICATION_TRACK)
                == filters.publication_track
            ]
        if filters.source_family:
            incidents = [
                incident
                for incident in incidents
                if incident.get("source_family", DEFAULT_SOURCE_FAMILY)
                == filters.source_family
            ]
        if filters.year is not None:
            incidents = [
                incident
                for incident in incidents
                if date.fromisoformat(incident["date_logged"]).year == filters.year
            ]
        if filters.month is not None:
            incidents = [
                incident
                for incident in incidents
                if date.fromisoformat(incident["date_logged"]).month == filters.month
            ]

        incidents.sort(key=lambda incident: incident["date_logged"], reverse=True)
        return incidents


def _sanitize_reader_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def _public_detail_sources(
    incident: dict[str, Any],
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if incident.get("source_family") != "autonomous_vehicle":
        return sources
    return [
        source
        for source in sources
        if _looks_like_incident_document_url(str(source.get("source_url") or ""))
    ]


def _looks_like_incident_document_url(source_url: str) -> bool:
    normalized = source_url.lower()
    return (
        normalized.endswith(".pdf")
        or "/portal/file/" in normalized
        or normalized.endswith("-pdf/")
        or normalized.endswith("-pdf")
    )
