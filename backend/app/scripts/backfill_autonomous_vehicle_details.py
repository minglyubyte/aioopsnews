from __future__ import annotations

import argparse
import json
import logging

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.services.incident_translation import DeepSeekIncidentTranslationClient
from app.workflows.autonomous_vehicle_detail_backfill import (
    backfill_autonomous_vehicle_details,
)

LOGGER = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill reader-facing detail fields for approved autonomous "
            "vehicle incidents using already-fetched source evidence."
        )
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum approved autonomous vehicle incidents to backfill.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count eligible updates without writing them.",
    )
    parser.add_argument(
        "--skip-translation",
        action="store_true",
        help="Only update English detail fields.",
    )
    parser.add_argument(
        "--translation-concurrency",
        type=int,
        default=1,
        help="Maximum concurrent translation requests. Defaults to 1.",
    )
    args = parser.parse_args()
    _configure_logging()

    settings = get_settings()
    repository = build_incident_repository(settings.database_url)
    try:
        translation_client = None
        if not args.skip_translation:
            if not settings.deepseek_api_key:
                raise RuntimeError(
                    "DeepSeek translation is not configured. Pass "
                    "--skip-translation or set DEEPSEEK_API_KEY."
                )
            translation_client = DeepSeekIncidentTranslationClient(
                api_key=settings.deepseek_api_key,
                model=settings.deepseek_translation_model,
            )
        summary = backfill_autonomous_vehicle_details(
            repository,
            translation_client=translation_client,
            translation_concurrency=args.translation_concurrency,
            limit=args.limit,
            dry_run=args.dry_run,
        )
        LOGGER.info("Completed autonomous vehicle detail backfill: %s", summary)
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
