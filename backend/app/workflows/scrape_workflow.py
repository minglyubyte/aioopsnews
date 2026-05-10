"""Workflow logic for verified-source scraping with integrated evidence fetching.

Combines source discovery (via ``verified_sources`` scrapers) with
evidence retrieval into a single workflow that leaves incidents ready
for LLM review.
"""

from __future__ import annotations

import logging
from typing import Any

from app.db.repository_protocol import IncidentRepository
from app.scrapers.verified_sources import VerifiedSourceRecord
from app.services.source_evidence import IncidentSourceFetcher, refresh_source_evidence
from app.workflows.dual_track_ingestion import (
    normalize_verified_source_record,
    _candidate_exists,
    _persist_dual_track_candidate,
)

LOGGER = logging.getLogger(__name__)


def run_verified_source_scrape(
    *,
    repository: IncidentRepository,
    source_fetcher: IncidentSourceFetcher,
    verified_records: list[VerifiedSourceRecord],
    dry_run: bool = False,
    skip_evidence_fetch: bool = False,
) -> dict[str, Any]:
    """Discover, persist, and fetch evidence for verified source incidents.

    Returns a JSON-serialisable summary dict.
    """
    summary: dict[str, Any] = {
        "records_seen": len(verified_records),
        "incidents_created": 0,
        "incidents_skipped_existing": 0,
        "evidence_fetch_attempted": 0,
        "evidence_fetch_succeeded": 0,
        "evidence_fetch_failed": 0,
    }

    created_source_registry_keys: set[str] = set()

    for record in verified_records:
        candidate = normalize_verified_source_record(record)
        if _candidate_exists(repository, candidate):
            summary["incidents_skipped_existing"] += 1
            continue
        if dry_run:
            summary["incidents_created"] += 1
            continue

        _persist_dual_track_candidate(
            repository=repository,
            candidate=candidate,
            status="pending_llm_review",
            legitimacy_reasoning=(
                "Imported from fixed verified source discovery; awaiting AI "
                "relevance, duplicate, and severity review."
            ),
        )
        summary["incidents_created"] += 1
        created_source_registry_keys.add(record.source_registry_key)

    if dry_run or skip_evidence_fetch or not created_source_registry_keys:
        return summary

    # Fetch evidence for all pending incidents from the sources we just scraped.
    # This also covers any incidents from prior runs whose evidence was never fetched.
    pending_incidents = repository.list_incidents_pending_llm_review(
        source_registry_keys=list(created_source_registry_keys),
    )
    summary["evidence_fetch_attempted"] = sum(
        len(incident.get("sources", [])) for incident in pending_incidents
    )

    LOGGER.info(
        "Fetching source evidence for %d pending incidents (%d sources)",
        len(pending_incidents),
        summary["evidence_fetch_attempted"],
    )
    refresh_source_evidence(
        repository,
        incidents=pending_incidents,
        source_fetcher=source_fetcher,
    )

    # Re-read to count successes/failures after evidence refresh.
    refreshed = repository.list_incidents_pending_llm_review(
        source_registry_keys=list(created_source_registry_keys),
    )
    for incident in refreshed:
        for source in incident.get("sources", []):
            if source.get("fetch_status") == "fetched":
                summary["evidence_fetch_succeeded"] += 1
            elif source.get("fetch_status") == "failed":
                summary["evidence_fetch_failed"] += 1

    LOGGER.info(
        "Evidence fetch complete: succeeded=%d failed=%d",
        summary["evidence_fetch_succeeded"],
        summary["evidence_fetch_failed"],
    )
    return summary
