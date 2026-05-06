from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

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


class _HttpClient(Protocol):
    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, object],
    ): ...


class BraveNewsSearchProvider:
    endpoint = "https://api.search.brave.com/res/v1/news/search"

    def __init__(
        self,
        *,
        api_key: str,
        http_client: _HttpClient | None = None,
        result_limit: int = 3,
        freshness: str = "pd",
        country: str = "US",
        search_lang: str = "en",
    ) -> None:
        self._api_key = api_key
        self._http_client = http_client or httpx.Client(timeout=20.0)
        self._result_limit = result_limit
        self._freshness = freshness
        self._country = country
        self._search_lang = search_lang

    def search(self, query: str) -> list[SearchDiscoveryResult]:
        response = self._http_client.get(
            self.endpoint,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self._api_key,
            },
            params={
                "q": query,
                "count": self._result_limit,
                "freshness": self._freshness,
                "country": self._country,
                "search_lang": self._search_lang,
            },
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results", [])
        if not isinstance(results, list):
            return []

        mapped_results: list[SearchDiscoveryResult] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            url = item.get("url")
            if not isinstance(title, str) or not isinstance(url, str):
                continue
            description = item.get("description")
            profile = item.get("profile")
            publisher = None
            if isinstance(profile, dict) and isinstance(profile.get("name"), str):
                publisher = profile["name"]
            mapped_results.append(
                SearchDiscoveryResult(
                    title=title,
                    url=url,
                    snippet=description if isinstance(description, str) else "",
                    published_at=_date_from_brave_item(item),
                    publisher=publisher,
                )
            )
        return mapped_results


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
            canonical_url = canonicalize_news_url(result.url)
            candidates.append(
                IncidentCandidate(
                    external_id=f"news:{canonical_url}",
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
                            source_url=canonical_url,
                            source_type="secondary",
                            publisher=result.publisher,
                            title=result.title,
                            source_origin="search_discovery",
                            source_registry_key="brave_news_search",
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


def run_dual_track_daily_ingestion(
    *,
    repository: IncidentRepository,
    verified_records: list[VerifiedSourceRecord],
    search_provider: SearchProvider | None,
    search_queries: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    summary = {
        "accident_sources_seen": len(verified_records),
        "accidents_created": 0,
        "accidents_skipped_existing": 0,
        "news_queries_run": 0,
        "news_results_seen": 0,
        "news_created": 0,
        "news_duplicates_skipped": 0,
        "news_filtered": 0,
        "source_failures": 0,
    }

    for record in verified_records:
        candidate = normalize_verified_source_record(record)
        if _candidate_exists(repository, candidate):
            summary["accidents_skipped_existing"] += 1
            continue
        if not dry_run:
            _persist_dual_track_candidate(
                repository=repository,
                candidate=candidate,
                status="pending_llm_review",
                legitimacy_reasoning=(
                    "Imported from fixed verified source discovery; awaiting AI "
                    "relevance, duplicate, and severity review."
                ),
            )
        summary["accidents_created"] += 1

    selected_queries = search_queries or [query.query for query in WATCH_SEARCH_QUERIES]
    seen_news_external_ids: set[str] = set()
    if search_provider is not None:
        for query in selected_queries:
            summary["news_queries_run"] += 1
            try:
                candidates = run_watch_search_discovery(
                    search_provider=search_provider,
                    queries=[query],
                )
            except Exception:
                summary["source_failures"] += 1
                continue

            summary["news_results_seen"] += len(candidates)
            for candidate in candidates:
                if candidate.external_id in seen_news_external_ids:
                    summary["news_duplicates_skipped"] += 1
                    continue
                seen_news_external_ids.add(candidate.external_id)
                if _candidate_exists(repository, candidate):
                    summary["news_duplicates_skipped"] += 1
                    continue
                if not dry_run:
                    _persist_dual_track_candidate(
                        repository=repository,
                        candidate=candidate,
                        status="approved",
                        legitimacy_reasoning=(
                            "Auto-published from daily AI news discovery. This is a "
                            "fresh news signal, not a verified AI accident."
                        ),
                    )
                summary["news_created"] += 1

    return summary


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


def canonicalize_news_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or parsed.path
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
    ]
    query = urlencode(query_items, doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def _date_from_brave_item(item: dict[str, object]) -> str | None:
    for key in ("page_age", "date", "published_at"):
        value = item.get(key)
        if isinstance(value, str) and len(value) >= 10:
            return value[:10]
    return None


def _candidate_exists(
    repository: IncidentRepository,
    candidate: IncidentCandidate,
) -> bool:
    if repository.incident_exists_by_external_id(candidate.external_id):
        return True
    return any(
        repository.source_url_exists(source.source_url)
        for source in candidate.sources
    )


def _persist_dual_track_candidate(
    *,
    repository: IncidentRepository,
    candidate: IncidentCandidate,
    status: str,
    legitimacy_reasoning: str,
) -> None:
    repository.upsert_incident_import_row(
        external_id=candidate.external_id,
        headline=candidate.headline,
        date_logged=candidate.date_logged,
        company_involved=candidate.company_involved,
        incident_topic=candidate.incident_topic,
        reality_summary=candidate.reality_summary,
        status=status,
        source_links=[source.source_url for source in candidate.sources],
        legitimacy_score=None,
        legitimacy_label=None,
        legitimacy_reasoning=legitimacy_reasoning,
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
        raw_source_payloads=[source.raw_source_payload for source in candidate.sources],
    )


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
