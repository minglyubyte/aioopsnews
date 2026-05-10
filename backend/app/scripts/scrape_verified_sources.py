"""Scrape verified sources and fetch evidence for AI accident incidents.

Usage::

    uv run python -m app.scripts.scrape_verified_sources
    uv run python -m app.scripts.scrape_verified_sources --dry-run
    uv run python -m app.scripts.scrape_verified_sources --sources ca_dmv_av_collisions,nhtsa_data
"""

from __future__ import annotations

import argparse
import json
import logging

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.scrapers.verified_sources import fetch_verified_source_records
from app.services.source_evidence import HttpIncidentSourceFetcher
from app.workflows.scrape_workflow import run_verified_source_scrape

LOGGER = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scrape verified sources, persist new incidents, and fetch "
            "source evidence for AI accident review."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute create/skip counts without writing to the database.",
    )
    parser.add_argument(
        "--sources",
        default="all",
        help=(
            "Comma-separated verified source registry keys to scrape, "
            "or 'all' for every registered source. Default: all."
        ),
    )
    parser.add_argument(
        "--since",
        default=None,
        help="Only include records on or after this YYYY-MM-DD date.",
    )
    parser.add_argument(
        "--limit-per-source",
        type=int,
        default=50,
        help="Maximum records to fetch per source. Default: 50.",
    )
    parser.add_argument(
        "--skip-evidence-fetch",
        action="store_true",
        help="Persist incidents without fetching source evidence (debug only).",
    )
    args = parser.parse_args()
    _configure_logging()

    settings = get_settings()
    repository = build_incident_repository(settings.database_url)

    try:
        selected_sources = (
            None
            if args.sources == "all"
            else [s.strip() for s in args.sources.split(",") if s.strip()]
        )

        LOGGER.info(
            "Starting verified source scrape: sources=%s since=%s "
            "limit_per_source=%d dry_run=%s",
            args.sources,
            args.since,
            args.limit_per_source,
            args.dry_run,
        )

        verified_records = fetch_verified_source_records(
            sources=selected_sources,
            since=args.since,
            limit_per_source=args.limit_per_source,
        )
        LOGGER.info("Fetched %d verified source records", len(verified_records))

        source_fetcher = HttpIncidentSourceFetcher()
        summary = run_verified_source_scrape(
            repository=repository,
            source_fetcher=source_fetcher,
            verified_records=verified_records,
            dry_run=args.dry_run,
            skip_evidence_fetch=args.skip_evidence_fetch,
        )

        LOGGER.info(
            "Scrape complete: created=%d skipped=%d "
            "evidence_succeeded=%d evidence_failed=%d",
            summary["incidents_created"],
            summary["incidents_skipped_existing"],
            summary.get("evidence_fetch_succeeded", 0),
            summary.get("evidence_fetch_failed", 0),
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    except Exception:
        LOGGER.exception("Verified source scrape failed")
        raise
    finally:
        repository.close()


def _configure_logging() -> None:
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


if __name__ == "__main__":
    raise SystemExit(main())
