from __future__ import annotations

import argparse
import json
import logging

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.workflows.dual_track_ingestion import (
    BraveNewsSearchProvider,
    run_dual_track_daily_ingestion,
)

LOGGER = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run dual-track daily AI accident and AI news ingestion."
    )
    parser.add_argument(
        "--skip-news",
        action="store_true",
        help="Skip AI news search discovery.",
    )
    parser.add_argument(
        "--skip-verified",
        action="store_true",
        help="Skip fixed-source verified accident discovery.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute create/skip counts without writing incident rows.",
    )
    args = parser.parse_args()
    _configure_logging()

    settings = get_settings()
    if not args.skip_news and not settings.brave_search_api_key:
        raise ValueError(
            "BRAVE_SEARCH_API_KEY is required unless --skip-news is provided."
        )

    repository = build_incident_repository(settings.database_url)
    try:
        LOGGER.info(
            "Starting dual-track daily runner: skip_news=%s "
            "skip_verified=%s dry_run=%s",
            args.skip_news,
            args.skip_verified,
            args.dry_run,
        )
        search_provider = (
            None
            if args.skip_news
            else BraveNewsSearchProvider(
                api_key=settings.brave_search_api_key or "",
                result_limit=settings.ai_news_daily_result_limit,
                freshness=settings.ai_news_freshness,
            )
        )
        summary = run_dual_track_daily_ingestion(
            repository=repository,
            verified_records=[] if args.skip_verified else [],
            search_provider=search_provider,
            dry_run=args.dry_run,
        )
        LOGGER.info(
            "Completed dual-track daily runner: accidents_created=%s "
            "news_created=%s news_duplicates_skipped=%s source_failures=%s",
            summary.get("accidents_created"),
            summary.get("news_created"),
            summary.get("news_duplicates_skipped"),
            summary.get("source_failures"),
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
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
