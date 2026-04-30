from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import date
from typing import Any

from app.models.claim import ClaimRecord
from app.scrapers.rss import RSSArticle
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

        offset = (filters.page - 1) * filters.page_size
        window = incidents[offset : offset + filters.page_size]
        return [self._serialize_public_incident(incident) for incident in window]

    def close(self) -> None:
        return None

    def get_public_incident(self, incident_id: str) -> dict[str, Any] | None:
        incident = self.incidents.get(incident_id)
        if incident is None or incident["status"] != "approved":
            return None
        return self._serialize_public_incident(incident)

    def get_filter_values(self) -> dict[str, object]:
        incidents = self.list_public_incidents(IncidentQueryFilters(page_size=500))

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
            "years": years,
            "months_by_year": months_by_year,
        }

    def list_review_queue(self) -> list[dict[str, Any]]:
        incidents = [
            incident
            for incident in self.incidents.values()
            if incident["status"] == "pending_review"
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
            "headline": article.title,
            "date_logged": article.published_at.date().isoformat(),
            "company_involved": "Pending classification",
            "claimant_name": None,
            "categories": [],
            "severity_score": 1,
            "reality_summary": article.summary,
            "status": "pending_review",
            "ingestion_run_id": ingestion_run_id,
            "confidence_score": None,
            "review_notes": (
                f"Ingested from {article.publisher} RSS feed; "
                "awaiting enrichment and editorial review."
            ),
            "matched_claim_id": None,
            "claim_match_confidence": None,
            "sources": [
                {
                    "id": source_id,
                    "source_url": article.url,
                    "source_type": article.source_type,
                    "publisher": article.publisher,
                    "title": article.title,
                }
            ],
        }
        return True

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
        severity_score: int,
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
                "severity_score": severity_score,
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

    def _serialize_public_incident(self, incident: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "id": incident["id"],
            "headline": incident["headline"],
            "date_logged": incident["date_logged"],
            "company_involved": incident["company_involved"],
            "claimant_name": incident.get("claimant_name"),
            "categories": list(incident["categories"]),
            "severity_score": incident["severity_score"],
            "reality_summary": incident["reality_summary"],
            "status": incident["status"],
            "matched_claim": None,
            "sources": deepcopy(incident.get("sources", [])),
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
        return {
            "id": incident["id"],
            "headline": incident["headline"],
            "date_logged": incident["date_logged"],
            "company_involved": incident["company_involved"],
            "claimant_name": incident.get("claimant_name"),
            "categories": list(incident["categories"]),
            "severity_score": incident["severity_score"],
            "reality_summary": incident["reality_summary"],
            "status": incident["status"],
            "matched_claim_id": incident.get("matched_claim_id"),
            "claim_match_confidence": incident.get("claim_match_confidence"),
            "review_notes": incident.get("review_notes"),
            "sources": deepcopy(incident.get("sources", [])),
        }
