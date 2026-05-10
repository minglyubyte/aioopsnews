from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.db.repository_protocol import IncidentRepository
from app.services.incident_query import IncidentQueryFilters
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
    source_registry_keys: set[str] | None = None,
    statuses: set[str] | None = None,
    source_url_kind: str = "all",
) -> dict[str, int]:
    incidents = _source_refresh_incidents(
        repository,
        statuses=statuses or {"pending_llm_review"},
    )
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
        for source in _iter_matching_sources(
            incident.get("sources", []),
            source_registry_keys=source_registry_keys,
            source_url_kind=source_url_kind,
        ):
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
    parser.add_argument(
        "--source-registry-keys",
        default=None,
        help=(
            "Comma-separated source_registry_key filter. When omitted, all "
            "pending LLM-review sources are eligible."
        ),
    )
    parser.add_argument(
        "--statuses",
        default="pending_llm_review",
        help=(
            "Comma-separated incident statuses to refresh. Defaults to "
            "pending_llm_review. Use approved for public backfills."
        ),
    )
    parser.add_argument(
        "--source-url-kind",
        choices=("all", "incident_document"),
        default="all",
        help=(
            "Filter eligible source URLs. Use incident_document to fetch only "
            "single-incident documents such as DMV PDF report URLs."
        ),
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
            source_registry_keys=_split_source_registry_keys(
                args.source_registry_keys
            ),
            statuses=_split_statuses(args.statuses),
            source_url_kind=args.source_url_kind,
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


def _iter_matching_sources(
    sources: list[dict[str, Any]],
    *,
    source_registry_keys: set[str] | None,
    source_url_kind: str,
) -> list[dict[str, Any]]:
    return [
        source
        for source in sources
        if (
            source_registry_keys is None
            or source.get("source_registry_key") in source_registry_keys
        )
        and _source_url_matches_kind(source, source_url_kind)
    ]


def _source_url_matches_kind(source: dict[str, Any], source_url_kind: str) -> bool:
    if source_url_kind == "all":
        return True
    if source_url_kind == "incident_document":
        return _looks_like_incident_document_url(str(source.get("source_url") or ""))
    raise ValueError(f"Unsupported source_url_kind: {source_url_kind}")


def _split_source_registry_keys(value: str | None) -> set[str] | None:
    if value is None:
        return None
    keys = {key.strip() for key in value.split(",") if key.strip()}
    return keys or None


def _split_statuses(value: str | None) -> set[str]:
    if value is None:
        return {"pending_llm_review"}
    statuses = {status.strip() for status in value.split(",") if status.strip()}
    return statuses or {"pending_llm_review"}


def _source_refresh_incidents(
    repository: IncidentRepository,
    *,
    statuses: set[str],
) -> list[dict[str, Any]]:
    incidents_by_id: dict[str, dict[str, Any]] = {}
    if "pending_llm_review" in statuses:
        for incident in repository.list_incidents_pending_llm_review():
            incidents_by_id[str(incident["id"])] = incident

    if "approved" in statuses:
        page = 1
        while True:
            feed = repository.list_public_incident_feed(
                IncidentQueryFilters(page=page, page_size=100)
            )
            for item in feed["items"]:
                detail = repository.get_public_incident(str(item["id"]))
                if detail is not None:
                    incidents_by_id[str(detail["id"])] = detail
            if not feed["has_next_page"]:
                break
            page += 1

    return list(incidents_by_id.values())


def _looks_like_incident_document_url(source_url: str) -> bool:
    normalized = source_url.lower()
    return (
        normalized.endswith(".pdf")
        or "/portal/file/" in normalized
        or normalized.endswith("-pdf/")
        or normalized.endswith("-pdf")
    )


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
