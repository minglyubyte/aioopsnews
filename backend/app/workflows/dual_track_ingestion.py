from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.incident_metadata import EvidenceTier, PublicationTrack, SourceFamily
from app.db.repository_protocol import IncidentRepository


@dataclass(frozen=True)
class VerifiedSourceAdapter:
    source_registry_key: str
    publisher: str
    publication_track: PublicationTrack
    evidence_tier: EvidenceTier
    source_family: SourceFamily
    source_origin: str = "fixed_verified_source"


@dataclass(frozen=True)
class WatchSearchQuery:
    query: str
    source_family: SourceFamily


@dataclass(frozen=True)
class VerifiedSourceRecord:
    source_registry_key: str
    external_id: str
    title: str
    incident_date: str
    company: str
    summary: str
    source_url: str
    publisher: str
    raw_payload: dict[str, object]


@dataclass(frozen=True)
class SearchDiscoveryResult:
    title: str
    url: str
    snippet: str
    published_at: str | None
    publisher: str | None


@dataclass(frozen=True)
class CandidateSource:
    source_url: str
    source_type: str
    publisher: str | None
    title: str | None
    source_origin: str
    source_registry_key: str
    raw_source_payload: dict[str, object]


@dataclass(frozen=True)
class IncidentCandidate:
    external_id: str
    headline: str
    date_logged: str
    company_involved: str
    incident_topic: str
    reality_summary: str
    publication_track: PublicationTrack
    evidence_tier: EvidenceTier
    source_family: SourceFamily
    verification_summary: str
    sources: list[CandidateSource]


class SearchProvider(Protocol):
    def search(self, query: str) -> list[SearchDiscoveryResult]: ...


VERIFIED_SOURCE_ADAPTERS: tuple[VerifiedSourceAdapter, ...] = (
    VerifiedSourceAdapter(
        source_registry_key="damien_charlotin_hallucinations",
        publisher="Damien Charlotin AI Hallucination Cases",
        publication_track="verified_accident",
        evidence_tier="court_or_regulator",
        source_family="legal_hallucination",
    ),
    VerifiedSourceAdapter(
        source_registry_key="ca_dmv_av_collisions",
        publisher="California DMV",
        publication_track="verified_accident",
        evidence_tier="official_documented",
        source_family="autonomous_vehicle",
    ),
    VerifiedSourceAdapter(
        source_registry_key="edrm_judicial_orders",
        publisher="EDRM Judicial Orders",
        publication_track="verified_accident",
        evidence_tier="court_or_regulator",
        source_family="legal_hallucination",
    ),
    VerifiedSourceAdapter(
        source_registry_key="nhtsa_data",
        publisher="NHTSA",
        publication_track="verified_accident",
        evidence_tier="official_documented",
        source_family="autonomous_vehicle",
    ),
)

WATCH_SEARCH_QUERIES: tuple[WatchSearchQuery, ...] = (
    WatchSearchQuery("AI coding failure production outage", "coding_failure"),
    WatchSearchQuery("AI security privacy incident data leak", "security_privacy"),
    WatchSearchQuery("AI customer support chatbot failure", "customer_support"),
    WatchSearchQuery(
        "AI education public sector chatbot failure",
        "education_public_sector",
    ),
    WatchSearchQuery(
        "AI healthcare benefits denial triage failure",
        "healthcare_benefits",
    ),
    WatchSearchQuery("AI model governance deployment failure", "model_governance"),
)


def get_verified_source_adapters() -> list[VerifiedSourceAdapter]:
    return list(VERIFIED_SOURCE_ADAPTERS)


def get_watch_search_queries() -> list[WatchSearchQuery]:
    return list(WATCH_SEARCH_QUERIES)


def normalize_verified_source_record(record: VerifiedSourceRecord) -> IncidentCandidate:
    adapter = _get_verified_adapter(record.source_registry_key)
    return IncidentCandidate(
        external_id=record.external_id,
        headline=record.title,
        date_logged=record.incident_date,
        company_involved=record.company,
        incident_topic=adapter.source_family,
        reality_summary=record.summary,
        publication_track=adapter.publication_track,
        evidence_tier=adapter.evidence_tier,
        source_family=adapter.source_family,
        verification_summary=(
            f"Fixed verified source {record.publisher} documents this incident; "
            "editorial review still checks AI relevance, dedupe, and severity."
        ),
        sources=[
            CandidateSource(
                source_url=record.source_url,
                source_type="official"
                if adapter.evidence_tier == "official_documented"
                else "primary",
                publisher=record.publisher,
                title=record.title,
                source_origin=adapter.source_origin,
                source_registry_key=adapter.source_registry_key,
                raw_source_payload=dict(record.raw_payload),
            )
        ],
    )


def run_watch_search_discovery(
    *,
    search_provider: SearchProvider,
    queries: list[str] | None = None,
) -> list[IncidentCandidate]:
    selected_queries = queries or [query.query for query in WATCH_SEARCH_QUERIES]
    candidates: list[IncidentCandidate] = []
    for query in selected_queries:
        source_family = _infer_watch_source_family(query)
        for result in search_provider.search(query):
            candidates.append(
                IncidentCandidate(
                    external_id=f"watch:{result.url}",
                    headline=result.title,
                    date_logged=result.published_at or "1970-01-01",
                    company_involved="Pending classification",
                    incident_topic=source_family,
                    reality_summary=result.snippet,
                    publication_track="accident_watch",
                    evidence_tier="reported_unconfirmed",
                    source_family=source_family,
                    verification_summary=(
                        "Search discovery found credible reporting, but no fixed "
                        "official, court, regulator, or company source has verified "
                        "the incident yet."
                    ),
                    sources=[
                        CandidateSource(
                            source_url=result.url,
                            source_type="secondary",
                            publisher=result.publisher,
                            title=result.title,
                            source_origin="search_discovery",
                            source_registry_key="google_search",
                            raw_source_payload={
                                "query": query,
                                "snippet": result.snippet,
                                "published_at": result.published_at,
                            },
                        )
                    ],
                )
            )
    return candidates


def ingest_dual_track_candidates(
    *,
    repository: IncidentRepository,
    candidates: list[IncidentCandidate],
) -> dict[str, int]:
    incidents_upserted = 0
    for candidate in candidates:
        repository.upsert_incident_import_row(
            external_id=candidate.external_id,
            headline=candidate.headline,
            date_logged=candidate.date_logged,
            company_involved=candidate.company_involved,
            incident_topic=candidate.incident_topic,
            reality_summary=candidate.reality_summary,
            status="pending_llm_review",
            source_links=[source.source_url for source in candidate.sources],
            legitimacy_score=None,
            legitimacy_label=None,
            legitimacy_reasoning=(
                "Imported from dual-track ingestion; awaiting source verification "
                "and editorial review."
            ),
            source_validation_summary=candidate.verification_summary,
            legitimacy_flag="REVIEW",
            confidence_level="medium",
            import_notes=None,
            matched_claim_id=None,
            headline_zh=None,
            reality_summary_zh=None,
            translation_status="not_requested",
            publication_track=candidate.publication_track,
            evidence_tier=candidate.evidence_tier,
            source_family=candidate.source_family,
            verification_summary=candidate.verification_summary,
            source_origin=candidate.sources[0].source_origin,
            source_registry_key=candidate.sources[0].source_registry_key,
            raw_source_payloads=[
                source.raw_source_payload for source in candidate.sources
            ],
        )
        incidents_upserted += 1
    return {
        "candidates_seen": len(candidates),
        "incidents_upserted": incidents_upserted,
    }


def _get_verified_adapter(source_registry_key: str) -> VerifiedSourceAdapter:
    for adapter in VERIFIED_SOURCE_ADAPTERS:
        if adapter.source_registry_key == source_registry_key:
            return adapter
    raise ValueError(f"Unknown verified source registry key: {source_registry_key}")


def _infer_watch_source_family(query: str) -> SourceFamily:
    lowered = query.lower()
    for configured_query in WATCH_SEARCH_QUERIES:
        if configured_query.query == query:
            return configured_query.source_family
    if "coding" in lowered:
        return "coding_failure"
    if "security" in lowered or "privacy" in lowered:
        return "security_privacy"
    if "support" in lowered:
        return "customer_support"
    if "education" in lowered or "public sector" in lowered:
        return "education_public_sector"
    if "healthcare" in lowered or "benefits" in lowered:
        return "healthcare_benefits"
    if "governance" in lowered:
        return "model_governance"
    return "other"
