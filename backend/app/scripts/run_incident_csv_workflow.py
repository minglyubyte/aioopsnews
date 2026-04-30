from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.services.incident_review import (
    HttpIncidentSourceFetcher,
    OpenAIIncidentReviewClient,
)
from app.services.incident_translation import DeepSeekIncidentTranslationClient
from app.workflows.incident_csv_workflow import run_incident_csv_workflow


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the daily incident CSV import and review workflow."
    )
    parser.add_argument(
        "--inbox-dir",
        type=Path,
        default=Path("app/imports/inbox"),
        help="Directory to scan for incoming incident CSV files.",
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=Path("app/imports/archive"),
        help="Directory to move successfully imported CSV files into.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inbox CSVs without writing database rows or moving files.",
    )
    parser.add_argument(
        "--submit-new-batches",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Submit new OpenAI review batches for unbatched pending incidents.",
    )
    parser.add_argument(
        "--reconcile-ready-batches",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reconcile any completed review batches already attached to incidents.",
    )
    args = parser.parse_args()

    settings = get_settings()
    repository = build_incident_repository(settings.database_url)
    source_fetcher = HttpIncidentSourceFetcher()
    batch_client = OpenAIIncidentReviewClient(api_key=settings.openai_api_key or "")
    translation_client = DeepSeekIncidentTranslationClient(
        api_key=settings.deepseek_api_key or "",
        model=settings.deepseek_translation_model,
    )

    summary = run_incident_csv_workflow(
        repository=repository,
        inbox_dir=args.inbox_dir,
        archive_dir=args.archive_dir,
        source_fetcher=source_fetcher,
        batch_client=batch_client,
        escalation_client=batch_client,
        translation_client=translation_client,
        primary_model=settings.openai_primary_review_model,
        escalation_model=settings.openai_escalation_review_model,
        dry_run=args.dry_run,
        submit_new_batches=args.submit_new_batches,
        reconcile_ready_batches=args.reconcile_ready_batches,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
