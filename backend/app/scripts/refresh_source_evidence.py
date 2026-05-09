from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.db.repository_protocol import IncidentRepository
from app.services.source_evidence import (
    FetchedIncidentSource,
    HttpIncidentSourceFetcher,
    IncidentSourceFetcher,
)

LOGGER = logging.getLogger(__name__)


def refresh_pending_source_evidence(
    repository: IncidentRepository,
    *,
    source_fetcher: IncidentSourceFetcher,
    limit: int | None = None,
    force: bool = False,
) -> dict[str, int]:
    incidents = repository.list_incidents_pending_llm_review()
    summary = {
        "incidents_seen": len(incidents),
        "sources_seen": 0,
        "fetched": 0,
        "failed": 0,
        "skipped": 0,
        "remaining_unfetched": 0,
    }

    source_result_by_url = (
        _existing_source_result_by_url(incidents) if not force else {}
    )
    remaining_budget = limit
    for incident in incidents:
        for source in incident.get("sources", []):
            summary["sources_seen"] += 1
            if _source_already_attempted(source) and not force:
                summary["skipped"] += 1
                continue
            cached = source_result_by_url.get(source["source_url"])
            if cached is not None and not force:
                _update_source_evidence(
                    repository,
                    source_id=source["id"],
                    fetched=cached,
                )
                if cached.fetch_status == "fetched":
                    summary["fetched"] += 1
                else:
                    summary["failed"] += 1
                continue
            if remaining_budget is not None and remaining_budget <= 0:
                summary["remaining_unfetched"] += 1
                continue

            fetched = _fetch_source(source_fetcher, source)
            _update_source_evidence(
                repository,
                source_id=source["id"],
                fetched=fetched,
            )
            if fetched.fetch_status == "fetched":
                summary["fetched"] += 1
            else:
                summary["failed"] += 1
            source_result_by_url[source["source_url"]] = fetched
            if remaining_budget is not None:
                remaining_budget -= 1

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch and extract source evidence text for pending LLM-review "
            "incidents without running review."
        )
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum sources to fetch in this run. Defaults to 100.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refetch sources even when evidence_text is already present.",
    )
    args = parser.parse_args()
    _configure_logging()

    settings = get_settings()
    repository = build_incident_repository(settings.database_url)
    try:
        LOGGER.info(
            "Starting source evidence refresh: limit=%s force=%s",
            args.limit,
            args.force,
        )
        summary = refresh_pending_source_evidence(
            repository,
            source_fetcher=HttpIncidentSourceFetcher(),
            limit=args.limit,
            force=args.force,
        )
        LOGGER.info(
            "Completed source evidence refresh: incidents_seen=%s "
            "sources_seen=%s fetched=%s failed=%s skipped=%s "
            "remaining_unfetched=%s",
            summary["incidents_seen"],
            summary["sources_seen"],
            summary["fetched"],
            summary["failed"],
            summary["skipped"],
            summary["remaining_unfetched"],
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    finally:
        repository.close()


def _source_already_attempted(source: dict[str, Any]) -> bool:
    return bool(source.get("evidence_text")) or source.get("fetch_status") == "failed"


def _existing_source_result_by_url(
    incidents: list[dict[str, Any]],
) -> dict[str, FetchedIncidentSource]:
    source_result_by_url: dict[str, FetchedIncidentSource] = {}
    for incident in incidents:
        for source in incident.get("sources", []):
            evidence_text = source.get("evidence_text")
            if not evidence_text and source.get("fetch_status") != "failed":
                continue
            source_result_by_url[source["source_url"]] = FetchedIncidentSource(
                source_url=source["source_url"],
                canonical_url=source.get("canonical_url"),
                fetch_status=source.get("fetch_status") or "fetched",
                http_status=source.get("http_status"),
                evidence_text=evidence_text,
                fetch_error=source.get("fetch_error"),
            )
    return source_result_by_url


def _update_source_evidence(
    repository: IncidentRepository,
    *,
    source_id: str,
    fetched: FetchedIncidentSource,
) -> None:
    repository.update_incident_source_evidence(
        source_id=source_id,
        canonical_url=fetched.canonical_url,
        fetch_status=fetched.fetch_status,
        http_status=fetched.http_status,
        evidence_text=fetched.evidence_text,
        fetch_error=fetched.fetch_error,
        fetched_at=_now_isoformat(),
    )


def _fetch_source(
    source_fetcher: IncidentSourceFetcher,
    source: dict[str, Any],
) -> FetchedIncidentSource:
    try:
        return source_fetcher.fetch(source["source_url"])
    except Exception as exc:
        return FetchedIncidentSource(
            source_url=source["source_url"],
            canonical_url=None,
            fetch_status="failed",
            http_status=None,
            evidence_text=None,
            fetch_error=str(exc),
        )


def _now_isoformat() -> str:
    return datetime.now(tz=UTC).isoformat()


def _configure_logging() -> None:
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


if __name__ == "__main__":
    raise SystemExit(main())
