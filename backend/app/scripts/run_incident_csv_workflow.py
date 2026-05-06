from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.services.incident_deduplication import (
    CompatibleIncidentDuplicateJudgeClient,
    OpenAIIncidentEmbeddingClient,
)
from app.services.incident_review import (
    AsyncCompatibleIncidentReviewClient,
    CompatibleIncidentReviewClient,
    HttpIncidentSourceFetcher,
)
from app.services.incident_translation import DeepSeekIncidentTranslationClient
from app.workflows.incident_csv_workflow import run_incident_csv_workflow

LOGGER = logging.getLogger(__name__)


def _require_non_dry_run_credentials(settings) -> None:
    missing: list[str] = []
    if not settings.primary_review_api_key:
        missing.append("PRIMARY_REVIEW_API_KEY or DEEPSEEK_API_KEY")
    if not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if not settings.deepseek_api_key:
        missing.append("DEEPSEEK_API_KEY")

    if not missing:
        return

    raise ValueError(
        "Workflow credentials are missing for non-dry runs: "
        + ", ".join(missing)
        + ". DeepSeek credentials are required for primary review, second-phase "
        "review, duplicate checks, and translation. OPENAI_API_KEY is required "
        "only for embeddings."
    )


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
        "--import-only",
        action="store_true",
        help="Import and archive valid CSV files without running review.",
    )
    parser.add_argument(
        "--max-reviews",
        type=int,
        default=None,
        help="Maximum pending incidents to review in this run.",
    )
    parser.add_argument(
        "--review-concurrency",
        type=int,
        default=None,
        help=(
            "Maximum primary review API calls to run at the same time. "
            "Defaults to REVIEW_CONCURRENCY."
        ),
    )
    args = parser.parse_args()
    _configure_logging()

    settings = get_settings()
    review_concurrency = max(
        getattr(args, "review_concurrency", None) or settings.review_concurrency,
        1,
    )
    if not args.dry_run and not args.import_only:
        _require_non_dry_run_credentials(settings)
    repository = build_incident_repository(settings.database_url)
    try:
        LOGGER.info(
            "Starting incident CSV workflow: inbox=%s archive=%s dry_run=%s",
            args.inbox_dir,
            args.archive_dir,
            args.dry_run,
        )
        if args.dry_run or args.import_only:
            source_fetcher = object()
            review_client = object()
            escalation_client = object()
            embedding_client = object()
            duplicate_judge_client = object()
            translation_client = object()
        else:
            source_fetcher = HttpIncidentSourceFetcher()
            review_client = AsyncCompatibleIncidentReviewClient(
                api_key=settings.primary_review_api_key,
                base_url=settings.primary_review_base_url,
                max_output_tokens=settings.review_max_output_tokens,
                response_parse_max_attempts=(
                    settings.review_response_parse_max_attempts
                ),
            )
            escalation_client = CompatibleIncidentReviewClient(
                api_key=settings.primary_review_api_key,
                base_url=settings.primary_review_base_url,
                max_output_tokens=settings.review_max_output_tokens,
                response_parse_max_attempts=(
                    settings.review_response_parse_max_attempts
                ),
            )
            embedding_client = OpenAIIncidentEmbeddingClient(
                api_key=settings.openai_api_key or ""
            )
            duplicate_judge_client = CompatibleIncidentDuplicateJudgeClient(
                api_key=settings.primary_review_api_key,
                base_url=settings.primary_review_base_url,
            )
            translation_client = DeepSeekIncidentTranslationClient(
                api_key=settings.deepseek_api_key or "",
                model=settings.deepseek_translation_model,
            )

        summary = asyncio.run(
            run_incident_csv_workflow(
                repository=repository,
                inbox_dir=args.inbox_dir,
                archive_dir=args.archive_dir,
                source_fetcher=source_fetcher,
                review_client=review_client,
                escalation_client=escalation_client,
                translation_client=translation_client,
                embedding_client=embedding_client,
                duplicate_judge_client=duplicate_judge_client,
                primary_model=settings.primary_review_model,
                escalation_model=settings.escalation_review_model,
                embedding_model=settings.openai_embedding_model,
                dry_run=args.dry_run,
                import_only=args.import_only,
                max_reviews=args.max_reviews,
                review_concurrency=review_concurrency,
            )
        )
        LOGGER.info(
            "Completed incident CSV workflow: files_found=%s files_imported=%s "
            "files_failed=%s incidents_imported=%s reviews_attempted=%s "
            "reviews_completed=%s reviews_failed=%s approved=%s "
            "pending_review=%s rejected=%s translations_completed=%s",
            summary.get("files_found"),
            summary.get("files_imported"),
            summary.get("files_failed"),
            summary.get("incidents_imported"),
            summary.get("reviews_attempted"),
            summary.get("reviews_completed"),
            summary.get("reviews_failed"),
            summary.get("approved"),
            summary.get("pending_review"),
            summary.get("rejected"),
            summary.get("translations_completed"),
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    except Exception:
        LOGGER.exception("Incident CSV workflow failed")
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
