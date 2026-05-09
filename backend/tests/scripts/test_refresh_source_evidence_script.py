from __future__ import annotations

from app.scripts.refresh_source_evidence import refresh_pending_source_evidence
from app.services.source_evidence import FetchedIncidentSource
from tests.support.fakes import InMemoryIncidentRepository


class FakeSourceFetcher:
    def __init__(self) -> None:
        self.fetched_urls: list[str] = []

    def fetch(self, source_url: str) -> FetchedIncidentSource:
        self.fetched_urls.append(source_url)
        return FetchedIncidentSource(
            source_url=source_url,
            canonical_url=f"{source_url}?canonical",
            fetch_status="fetched",
            http_status=200,
            evidence_text=f"Evidence for {source_url}",
            fetch_error=None,
        )


def test_refresh_pending_source_evidence_skips_existing_evidence() -> None:
    repository = InMemoryIncidentRepository(
        incidents=[
            _incident(
                "incident-1",
                [
                    _source("source-1", "https://example.com/existing", "old text"),
                    _source("source-2", "https://example.com/missing", None),
                ],
            )
        ]
    )
    fetcher = FakeSourceFetcher()

    summary = refresh_pending_source_evidence(
        repository,
        source_fetcher=fetcher,
    )

    assert summary == {
        "incidents_seen": 1,
        "sources_seen": 2,
        "fetched": 1,
        "failed": 0,
        "skipped": 1,
        "remaining_unfetched": 0,
    }
    assert fetcher.fetched_urls == ["https://example.com/missing"]
    incident = repository.list_incidents_pending_llm_review()[0]
    assert incident["sources"][0]["evidence_text"] == "old text"
    assert incident["sources"][1]["evidence_text"] == (
        "Evidence for https://example.com/missing"
    )


def test_refresh_pending_source_evidence_respects_source_limit() -> None:
    repository = InMemoryIncidentRepository(
        incidents=[
            _incident(
                "incident-1",
                [
                    _source("source-1", "https://example.com/one", None),
                    _source("source-2", "https://example.com/two", None),
                ],
            )
        ]
    )
    fetcher = FakeSourceFetcher()

    summary = refresh_pending_source_evidence(
        repository,
        source_fetcher=fetcher,
        limit=1,
    )

    assert summary["fetched"] == 1
    assert summary["remaining_unfetched"] == 1
    assert fetcher.fetched_urls == ["https://example.com/one"]


def test_refresh_pending_source_evidence_force_refetches_existing_evidence() -> None:
    repository = InMemoryIncidentRepository(
        incidents=[
            _incident(
                "incident-1",
                [_source("source-1", "https://example.com/existing", "old text")],
            )
        ]
    )
    fetcher = FakeSourceFetcher()

    summary = refresh_pending_source_evidence(
        repository,
        source_fetcher=fetcher,
        force=True,
    )

    assert summary["fetched"] == 1
    assert summary["skipped"] == 0
    assert fetcher.fetched_urls == ["https://example.com/existing"]
    incident = repository.list_incidents_pending_llm_review()[0]
    assert incident["sources"][0]["evidence_text"] == (
        "Evidence for https://example.com/existing"
    )


def test_refresh_pending_source_evidence_reuses_existing_duplicate_url_evidence(
) -> None:
    repository = InMemoryIncidentRepository(
        incidents=[
            _incident(
                "incident-1",
                [_source("source-1", "https://example.com/shared", "cached text")],
            ),
            _incident(
                "incident-2",
                [_source("source-2", "https://example.com/shared", None)],
            ),
        ]
    )
    fetcher = FakeSourceFetcher()

    summary = refresh_pending_source_evidence(
        repository,
        source_fetcher=fetcher,
    )

    assert summary["fetched"] == 1
    assert summary["skipped"] == 1
    assert fetcher.fetched_urls == []
    incident = repository.list_incidents_pending_llm_review()[0]
    assert incident["sources"][0]["evidence_text"] == "cached text"


def test_refresh_pending_source_evidence_skips_existing_failed_source() -> None:
    repository = InMemoryIncidentRepository(
        incidents=[
            _incident(
                "incident-1",
                [
                    _source(
                        "source-1",
                        "https://example.com/blocked",
                        None,
                        fetch_status="failed",
                    ),
                    _source("source-2", "https://example.com/missing", None),
                ],
            )
        ]
    )
    fetcher = FakeSourceFetcher()

    summary = refresh_pending_source_evidence(
        repository,
        source_fetcher=fetcher,
    )

    assert summary["fetched"] == 1
    assert summary["skipped"] == 1
    assert summary["remaining_unfetched"] == 0
    assert fetcher.fetched_urls == ["https://example.com/missing"]


def _incident(incident_id: str, sources: list[dict[str, object]]) -> dict[str, object]:
    return {
        "id": incident_id,
        "external_id": incident_id,
        "headline": "Pending incident",
        "headline_en": "Pending incident",
        "headline_zh": None,
        "date_logged": "2026-05-09",
        "company_involved": "Example",
        "incident_topic": "autonomous_vehicle",
        "claimant_name": None,
        "categories": [],
        "severity_score": 3,
        "suggested_severity_score": None,
        "reality_summary": "Summary",
        "reality_summary_en": "Summary",
        "reality_summary_zh": None,
        "status": "pending_llm_review",
        "ingestion_run_id": None,
        "confidence_score": None,
        "severity_confidence": None,
        "severity_reasoning": None,
        "severity_flags": [],
        "severity_model": None,
        "severity_decision_source": None,
        "review_notes": None,
        "matched_claim_id": None,
        "claim_match_confidence": None,
        "legitimacy_score": None,
        "legitimacy_label": None,
        "legitimacy_reasoning": None,
        "source_validation_summary": "Validation",
        "legitimacy_flag": "REVIEW",
        "confidence_level": "medium",
        "import_notes": None,
        "translation_status": "not_requested",
        "publication_track": "verified_accident",
        "evidence_tier": "official_documented",
        "source_family": "autonomous_vehicle",
        "verification_summary": "Verification",
        "review_batch_id": None,
        "review_model": None,
        "reviewed_at": None,
        "translated_at": None,
        "duplicate_status": None,
        "duplicate_of_incident_id": None,
        "canonical_incident_id": None,
        "embedding_model": None,
        "embedding_vector": None,
        "sources": sources,
    }


def _source(
    source_id: str,
    source_url: str,
    evidence_text: str | None,
    *,
    fetch_status: str | None = None,
) -> dict[str, object]:
    return {
        "id": source_id,
        "source_url": source_url,
        "canonical_url": None,
        "source_type": "official",
        "publisher": None,
        "title": None,
        "fetch_status": fetch_status,
        "http_status": None,
        "evidence_text": evidence_text,
        "fetch_error": None,
        "source_origin": "fixed_verified_source",
        "source_registry_key": "ca_dmv_av_collisions",
        "raw_source_payload": None,
        "is_primary": True,
    }
