from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.scrapers.verified_sources import VerifiedSourceRecord
from app.services.source_evidence import FetchedIncidentSource
from app.workflows.scrape_workflow import run_verified_source_scrape


@dataclass
class _StubSourceFetcher:
    """No-op source fetcher for testing."""

    calls: list[Any] = field(default_factory=list)

    def fetch(self, url: str) -> FetchedIncidentSource:
        self.calls.append(url)
        return FetchedIncidentSource(
            source_url=url,
            canonical_url=url,
            fetch_status="fetched",
            http_status=200,
            evidence_text="stub evidence",
        )


class _StubRepository:
    """Minimal stub for IncidentRepository used in scrape_workflow tests."""

    def __init__(
        self,
        *,
        existing_external_ids: set[str] | None = None,
        existing_source_urls: set[str] | None = None,
    ) -> None:
        self._existing_external_ids = existing_external_ids or set()
        self._existing_source_urls = existing_source_urls or set()
        self.upserted: list[dict[str, Any]] = []
        self._evidence_updates: dict[str, dict[str, Any]] = {}
        self.closed = False

    def incident_exists_by_external_id(self, external_id: str) -> bool:
        return external_id in self._existing_external_ids

    def source_url_exists(self, source_url: str) -> bool:
        return source_url in self._existing_source_urls

    def upsert_incident_import_row(self, **kwargs: Any) -> None:
        self.upserted.append(kwargs)

    def update_incident_source_evidence(self, *, source_id: str, **kwargs: Any) -> None:
        self._evidence_updates[source_id] = kwargs

    def list_incidents_pending_llm_review(
        self,
        *,
        source_registry_keys: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        results = []
        for row in self.upserted:
            source_url = row["source_links"][0] if row.get("source_links") else ""
            source_id = f"src-{row['external_id']}"
            evidence_update = self._evidence_updates.get(source_id, {})
            fetch_status = evidence_update.get("fetch_status", "not_attempted")
            results.append({
                "id": row["external_id"],
                "external_id": row["external_id"],
                "sources": [{
                    "id": source_id,
                    "source_url": source_url,
                    "fetch_status": fetch_status,
                }],
            })
        return results

    def close(self) -> None:
        self.closed = True


def _make_record(
    external_id: str = "ca-dmv-test-2026-01-01",
    source_registry_key: str = "ca_dmv_av_collisions",
    source_url: str = "https://example.com/report.pdf",
) -> VerifiedSourceRecord:
    return VerifiedSourceRecord(
        source_registry_key=source_registry_key,
        external_id=external_id,
        title="Test collision report",
        incident_date="2026-01-01",
        company="TestCo",
        summary="Test summary",
        source_url=source_url,
        publisher="California DMV",
        raw_payload={"test": True},
    )


def test_dry_run_does_not_write_to_repository() -> None:
    repo = _StubRepository()
    record = _make_record()

    summary = run_verified_source_scrape(
        repository=repo,
        source_fetcher=_StubSourceFetcher(),
        verified_records=[record],
        dry_run=True,
    )

    assert summary["records_seen"] == 1
    assert summary["incidents_created"] == 1
    assert summary["incidents_skipped_existing"] == 0
    assert len(repo.upserted) == 0


def test_new_record_is_persisted() -> None:
    repo = _StubRepository()
    record = _make_record()

    summary = run_verified_source_scrape(
        repository=repo,
        source_fetcher=_StubSourceFetcher(),
        verified_records=[record],
        skip_evidence_fetch=True,
    )

    assert summary["incidents_created"] == 1
    assert len(repo.upserted) == 1
    assert repo.upserted[0]["status"] == "pending_llm_review"


def test_existing_external_id_is_skipped() -> None:
    repo = _StubRepository(
        existing_external_ids={"ca-dmv-test-2026-01-01"},
    )
    record = _make_record()

    summary = run_verified_source_scrape(
        repository=repo,
        source_fetcher=_StubSourceFetcher(),
        verified_records=[record],
        skip_evidence_fetch=True,
    )

    assert summary["incidents_created"] == 0
    assert summary["incidents_skipped_existing"] == 1
    assert len(repo.upserted) == 0


def test_existing_source_url_is_skipped() -> None:
    repo = _StubRepository(
        existing_source_urls={"https://example.com/report.pdf"},
    )
    record = _make_record()

    summary = run_verified_source_scrape(
        repository=repo,
        source_fetcher=_StubSourceFetcher(),
        verified_records=[record],
        skip_evidence_fetch=True,
    )

    assert summary["incidents_created"] == 0
    assert summary["incidents_skipped_existing"] == 1


def test_evidence_fetch_runs_after_persistence() -> None:
    repo = _StubRepository()
    record = _make_record()

    summary = run_verified_source_scrape(
        repository=repo,
        source_fetcher=_StubSourceFetcher(),
        verified_records=[record],
        skip_evidence_fetch=False,
    )

    assert summary["incidents_created"] == 1
    assert summary["evidence_fetch_succeeded"] == 1
    assert summary["evidence_fetch_failed"] == 0


def test_skip_evidence_fetch_flag() -> None:
    repo = _StubRepository()
    record = _make_record()

    summary = run_verified_source_scrape(
        repository=repo,
        source_fetcher=_StubSourceFetcher(),
        verified_records=[record],
        skip_evidence_fetch=True,
    )

    assert summary["incidents_created"] == 1
    assert "evidence_fetch_succeeded" not in summary or summary["evidence_fetch_succeeded"] == 0
    assert summary.get("evidence_fetch_attempted", 0) == 0


def test_empty_records_returns_zero_counts() -> None:
    repo = _StubRepository()

    summary = run_verified_source_scrape(
        repository=repo,
        source_fetcher=_StubSourceFetcher(),
        verified_records=[],
    )

    assert summary["records_seen"] == 0
    assert summary["incidents_created"] == 0
    assert summary["incidents_skipped_existing"] == 0
