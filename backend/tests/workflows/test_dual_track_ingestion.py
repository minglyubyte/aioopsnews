from __future__ import annotations

from app.workflows.dual_track_ingestion import (
    SearchDiscoveryResult,
    VerifiedSourceRecord,
    get_verified_source_adapters,
    get_watch_search_queries,
    ingest_dual_track_candidates,
    normalize_verified_source_record,
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
        summary="California DMV published a collision report involving an autonomous vehicle.",
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


def test_watch_search_discovery_creates_watch_candidates_with_search_provenance() -> None:
    class FakeSearchProvider:
        def search(self, query: str) -> list[SearchDiscoveryResult]:
            assert query == "AI coding failure production outage"
            return [
                SearchDiscoveryResult(
                    title="AI coding assistant shipped broken migration",
                    url="https://example.com/ai-coding-outage",
                    snippet="A coding assistant produced a migration that caused an outage.",
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
    assert candidates[0].sources[0].source_registry_key == "google_search"
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
