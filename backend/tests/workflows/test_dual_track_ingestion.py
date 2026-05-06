from __future__ import annotations

from app.workflows.dual_track_ingestion import (
    BraveNewsSearchProvider,
    SearchDiscoveryResult,
    VerifiedSourceRecord,
    get_verified_source_adapters,
    get_watch_search_queries,
    ingest_dual_track_candidates,
    normalize_verified_source_record,
    run_dual_track_daily_ingestion,
    run_watch_search_discovery,
)
from tests.support.fakes import InMemoryIncidentRepository


def test_verified_source_registry_defines_fixed_high_provenance_adapters() -> None:
    adapters = get_verified_source_adapters()

    assert {
        adapter.source_registry_key: (
            adapter.publication_track,
            adapter.evidence_tier,
            adapter.source_family,
            adapter.source_origin,
        )
        for adapter in adapters
    } == {
        "damien_charlotin_hallucinations": (
            "verified_accident",
            "court_or_regulator",
            "legal_hallucination",
            "fixed_verified_source",
        ),
        "ca_dmv_av_collisions": (
            "verified_accident",
            "official_documented",
            "autonomous_vehicle",
            "fixed_verified_source",
        ),
        "edrm_judicial_orders": (
            "verified_accident",
            "court_or_regulator",
            "legal_hallucination",
            "fixed_verified_source",
        ),
        "nhtsa_data": (
            "verified_accident",
            "official_documented",
            "autonomous_vehicle",
            "fixed_verified_source",
        ),
    }


def test_verified_source_record_normalizes_into_common_incident_candidate() -> None:
    record = VerifiedSourceRecord(
        source_registry_key="ca_dmv_av_collisions",
        external_id="ca-dmv-2026-001",
        title="Autonomous vehicle collision report involving Waymo",
        incident_date="2026-04-28",
        company="Waymo",
        summary=(
            "California DMV published a collision report involving an "
            "autonomous vehicle."
        ),
        source_url="https://www.dmv.ca.gov/report.pdf",
        publisher="California DMV",
        raw_payload={"report_number": "OL 316", "pdf_url": "https://www.dmv.ca.gov/report.pdf"},
    )

    candidate = normalize_verified_source_record(record)

    assert candidate.external_id == "ca-dmv-2026-001"
    assert candidate.publication_track == "verified_accident"
    assert candidate.evidence_tier == "official_documented"
    assert candidate.source_family == "autonomous_vehicle"
    assert candidate.verification_summary == (
        "Fixed verified source California DMV documents this incident; "
        "editorial review still checks AI relevance, dedupe, and severity."
    )
    assert candidate.sources[0].source_origin == "fixed_verified_source"
    assert candidate.sources[0].source_registry_key == "ca_dmv_av_collisions"
    assert candidate.sources[0].raw_source_payload == {
        "report_number": "OL 316",
        "pdf_url": "https://www.dmv.ca.gov/report.pdf",
    }


def test_watch_search_discovery_creates_watch_candidates_with_search_provenance() -> (
    None
):
    class FakeSearchProvider:
        def search(self, query: str) -> list[SearchDiscoveryResult]:
            assert query == "AI coding failure production outage"
            return [
                SearchDiscoveryResult(
                    title="AI coding assistant shipped broken migration",
                    url="https://example.com/ai-coding-outage",
                    snippet=(
                        "A coding assistant produced a migration that caused an "
                        "outage."
                    ),
                    published_at="2026-05-01",
                    publisher="Example Tech",
                )
            ]

    candidates = run_watch_search_discovery(
        search_provider=FakeSearchProvider(),
        queries=["AI coding failure production outage"],
    )

    assert len(candidates) == 1
    assert candidates[0].publication_track == "accident_watch"
    assert candidates[0].evidence_tier == "reported_unconfirmed"
    assert candidates[0].source_family == "coding_failure"
    assert candidates[0].verification_summary == (
        "Search discovery found credible reporting, but no fixed official, "
        "court, regulator, or company source has verified the incident yet."
    )
    assert candidates[0].sources[0].source_origin == "search_discovery"
    assert candidates[0].external_id == "news:https://example.com/ai-coding-outage"
    assert candidates[0].sources[0].source_registry_key == "brave_news_search"
    assert candidates[0].sources[0].raw_source_payload == {
        "query": "AI coding failure production outage",
        "snippet": "A coding assistant produced a migration that caused an outage.",
        "published_at": "2026-05-01",
    }


def test_dual_track_candidates_persist_into_same_incident_repository() -> None:
    repository = InMemoryIncidentRepository()
    candidate = normalize_verified_source_record(
        VerifiedSourceRecord(
            source_registry_key="edrm_judicial_orders",
            external_id="edrm-order-2026-001",
            title="Court sanctions filing with hallucinated citations",
            incident_date="2026-03-21",
            company="Unknown legal filer",
            summary="A judicial order discussed hallucinated AI citations in a filing.",
            source_url="https://edrm.net/order",
            publisher="EDRM",
            raw_payload={"case": "Example v. Example"},
        )
    )

    summary = ingest_dual_track_candidates(
        repository=repository,
        candidates=[candidate],
    )

    assert summary == {"candidates_seen": 1, "incidents_upserted": 1}
    stored = next(iter(repository.incidents.values()))
    assert stored["publication_track"] == "verified_accident"
    assert stored["evidence_tier"] == "court_or_regulator"
    assert stored["source_family"] == "legal_hallucination"
    assert stored["sources"][0]["source_origin"] == "fixed_verified_source"
    assert stored["sources"][0]["source_registry_key"] == "edrm_judicial_orders"


def test_watch_search_registry_covers_first_phase_watch_families() -> None:
    queries = get_watch_search_queries()

    assert {query.source_family for query in queries} == {
        "coding_failure",
        "security_privacy",
        "customer_support",
        "education_public_sector",
        "healthcare_benefits",
        "model_governance",
    }


def test_dual_track_daily_ingestion_auto_publishes_news_and_dedupes_urls() -> None:
    class FakeSearchProvider:
        def search(self, query: str) -> list[SearchDiscoveryResult]:
            assert query == "AI coding failure production outage"
            return [
                SearchDiscoveryResult(
                    title="AI coding assistant caused a migration outage",
                    url="https://example.com/news/ai-outage?utm_source=search",
                    snippet=(
                        "A coding assistant generated a migration that caused "
                        "downtime."
                    ),
                    published_at="2026-05-06",
                    publisher="Example News",
                ),
                SearchDiscoveryResult(
                    title="Duplicate rewrite of the same migration outage",
                    url="https://example.com/news/ai-outage",
                    snippet="A second result points to the same canonical news URL.",
                    published_at="2026-05-06",
                    publisher="Example News",
                ),
            ]

    repository = InMemoryIncidentRepository()

    first_summary = run_dual_track_daily_ingestion(
        repository=repository,
        verified_records=[],
        search_provider=FakeSearchProvider(),
        search_queries=["AI coding failure production outage"],
    )
    second_summary = run_dual_track_daily_ingestion(
        repository=repository,
        verified_records=[],
        search_provider=FakeSearchProvider(),
        search_queries=["AI coding failure production outage"],
    )

    assert first_summary["news_results_seen"] == 2
    assert first_summary["news_created"] == 1
    assert first_summary["news_duplicates_skipped"] == 1
    assert second_summary["news_created"] == 0
    assert second_summary["news_duplicates_skipped"] == 2
    assert len(repository.incidents) == 1
    stored = next(iter(repository.incidents.values()))
    assert stored["status"] == "approved"
    assert stored["publication_track"] == "accident_watch"
    assert stored["evidence_tier"] == "reported_unconfirmed"
    assert stored["source_family"] == "coding_failure"
    assert stored["external_id"] == "news:https://example.com/news/ai-outage"
    assert stored["sources"][0]["source_origin"] == "search_discovery"
    assert stored["sources"][0]["source_registry_key"] == "brave_news_search"
    assert stored["sources"][0]["raw_source_payload"] == {
        "query": "AI coding failure production outage",
        "snippet": "A coding assistant generated a migration that caused downtime.",
        "published_at": "2026-05-06",
    }
    assert repository.list_incidents_pending_llm_review() == []


def test_dual_track_daily_ingestion_skips_existing_accidents_without_overwrite() -> (
    None
):
    repository = InMemoryIncidentRepository(
        incidents=[
            {
                "id": "incident-existing",
                "external_id": "ca-dmv-waymo-2026-05-01",
                "headline": "Editor-approved Waymo collision report",
                "headline_en": "Editor-approved Waymo collision report",
                "headline_zh": None,
                "date_logged": "2026-05-01",
                "company_involved": "Waymo",
                "incident_topic": "autonomous_vehicle",
                "claimant_name": None,
                "categories": ["Autonomous Systems"],
                "severity_score": 3,
                "reality_summary": "Existing editor summary must not be overwritten.",
                "reality_summary_en": (
                    "Existing editor summary must not be overwritten."
                ),
                "reality_summary_zh": None,
                "status": "approved",
                "translation_status": "not_requested",
                "publication_track": "verified_accident",
                "evidence_tier": "official_documented",
                "source_family": "autonomous_vehicle",
                "verification_summary": "Existing editor verification summary.",
                "matched_claim_id": None,
                "claim_match_confidence": None,
                "review_notes": "editor locked",
                "sources": [
                    {
                        "id": "source-existing",
                        "source_url": "https://www.dmv.ca.gov/portal/file/waymo_050126-pdf/",
                        "source_type": "official",
                        "publisher": "California DMV",
                        "title": "Existing report",
                    }
                ],
            }
        ]
    )
    verified_records = [
        VerifiedSourceRecord(
            source_registry_key="ca_dmv_av_collisions",
            external_id="ca-dmv-waymo-2026-05-01",
            title="Source title should not overwrite editor title",
            incident_date="2026-05-01",
            company="Waymo",
            summary="Source summary should not overwrite editor summary.",
            source_url="https://www.dmv.ca.gov/portal/file/waymo_050126-pdf/",
            publisher="California DMV",
            raw_payload={"report_number": "existing"},
        ),
        VerifiedSourceRecord(
            source_registry_key="ca_dmv_av_collisions",
            external_id="ca-dmv-zoox-2026-05-02",
            title="California DMV posts Zoox collision report",
            incident_date="2026-05-02",
            company="Zoox",
            summary="California DMV posted a new autonomous-vehicle collision report.",
            source_url="https://www.dmv.ca.gov/portal/file/zoox_050226-pdf/",
            publisher="California DMV",
            raw_payload={"report_number": "new"},
        ),
    ]

    summary = run_dual_track_daily_ingestion(
        repository=repository,
        verified_records=verified_records,
        search_provider=None,
        search_queries=[],
    )

    assert summary["accident_sources_seen"] == 2
    assert summary["accidents_created"] == 1
    assert summary["accidents_skipped_existing"] == 1
    assert repository.incidents["incident-existing"]["headline"] == (
        "Editor-approved Waymo collision report"
    )
    assert repository.incidents["incident-existing"]["review_notes"] == "editor locked"
    created = [
        incident
        for incident in repository.incidents.values()
        if incident["external_id"] == "ca-dmv-zoox-2026-05-02"
    ][0]
    assert created["status"] == "pending_llm_review"
    assert created["publication_track"] == "verified_accident"
    assert created["sources"][0]["source_origin"] == "fixed_verified_source"


def test_brave_news_search_provider_maps_news_results() -> None:
    captured_requests: list[dict[str, object]] = []

    class FakeHttpClient:
        def get(self, url: str, *, headers: dict[str, str], params: dict[str, object]):
            captured_requests.append(
                {"url": url, "headers": headers, "params": params}
            )

            class FakeResponse:
                def raise_for_status(self) -> None:
                    return None

                def json(self) -> dict[str, object]:
                    return {
                        "results": [
                            {
                                "title": "AI support bot leaked customer notes",
                                "url": "https://example.com/support-leak",
                                "description": "A support bot exposed account notes.",
                                "age": "2 hours ago",
                                "page_age": "2026-05-06T09:15:00Z",
                                "profile": {"name": "Example News"},
                            }
                        ]
                    }

            return FakeResponse()

    provider = BraveNewsSearchProvider(
        api_key="brave-key",
        http_client=FakeHttpClient(),
        result_limit=3,
        freshness="pd",
    )

    results = provider.search("AI customer support chatbot failure")

    assert captured_requests == [
        {
            "url": "https://api.search.brave.com/res/v1/news/search",
            "headers": {
                "Accept": "application/json",
                "X-Subscription-Token": "brave-key",
            },
            "params": {
                "q": "AI customer support chatbot failure",
                "count": 3,
                "freshness": "pd",
                "country": "US",
                "search_lang": "en",
            },
        }
    ]
    assert results == [
        SearchDiscoveryResult(
            title="AI support bot leaked customer notes",
            url="https://example.com/support-leak",
            snippet="A support bot exposed account notes.",
            published_at="2026-05-06",
            publisher="Example News",
        )
    ]
