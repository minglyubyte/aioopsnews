"""Review pending AI accident incidents via LLM, deduplicate, and translate.

Usage::

    uv run python -m app.scripts.review_pending_incidents
    uv run python -m app.scripts.review_pending_incidents --dry-run
    uv run python -m app.scripts.review_pending_incidents --max-reviews 10
    uv run python -m app.scripts.review_pending_incidents --source-registry-key nhtsa_data
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.services.incident_deduplication import (
    CompatibleIncidentDuplicateJudgeClient,
    OpenAIIncidentEmbeddingClient,
)
from app.services.incident_review import (
    AsyncCompatibleIncidentReviewClient,
    review_pending_incidents,
)
from app.services.incident_translation import DeepSeekIncidentTranslationClient
from app.services.source_evidence import HttpIncidentSourceFetcher

LOGGER = logging.getLogger(__name__)


def _require_credentials(settings) -> None:
    """Validate that all required API keys are present for a live run."""
    missing: list[str] = []
    if not settings.primary_review_api_key:
        missing.append("PRIMARY_REVIEW_API_KEY or DEEPSEEK_API_KEY")
    if not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if not settings.deepseek_api_key:
        missing.append("DEEPSEEK_API_KEY")
    if missing:
        raise ValueError(
            "Credentials missing for review run: "
            + ", ".join(missing)
            + ". Set the required environment variables."
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Review pending AI accident incidents: LLM review, "
            "deduplication, and translation."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List pending incidents without calling review APIs.",
    )
    parser.add_argument(
        "--max-reviews",
        type=int,
        default=None,
        help="Maximum pending incidents to review in this run.",
    )
    parser.add_argument(
        "--source-registry-key",
        dest="source_registry_keys",
        action="append",
        default=None,
        help=(
            "Restrict review to pending incidents from this source. "
            "Repeat the flag to include multiple sources."
        ),
    )
    parser.add_argument(
        "--review-concurrency",
        type=int,
        default=None,
        help="Maximum concurrent review API calls. Default: REVIEW_CONCURRENCY.",
    )
    parser.add_argument(
        "--backoff-max-seconds",
        type=float,
        default=60.0,
        help="Maximum 429 exponential backoff delay. Default: 60.",
    )
    args = parser.parse_args()
    _configure_logging()

    settings = get_settings()
    review_concurrency = max(
        args.review_concurrency or settings.review_concurrency,
        1,
    )

    if args.dry_run:
        return _dry_run(settings, args)

    _require_credentials(settings)
    repository = build_incident_repository(settings.database_url)

    try:
        LOGGER.info(
            "Starting incident review: max_reviews=%s sources=%s concurrency=%d",
            args.max_reviews,
            args.source_registry_keys,
            review_concurrency,
        )

        source_fetcher = HttpIncidentSourceFetcher()
        review_client = AsyncCompatibleIncidentReviewClient(
            api_key=settings.primary_review_api_key,
            base_url=settings.primary_review_base_url,
            max_output_tokens=settings.review_max_output_tokens,
            response_parse_max_attempts=settings.review_response_parse_max_attempts,
        )
        escalation_client = object()
        embedding_client = OpenAIIncidentEmbeddingClient(
            api_key=settings.openai_api_key or "",
        )
        duplicate_judge_client = CompatibleIncidentDuplicateJudgeClient(
            api_key=settings.primary_review_api_key,
            base_url=settings.primary_review_base_url,
        )
        translation_client = DeepSeekIncidentTranslationClient(
            api_key=settings.deepseek_api_key or "",
            model=settings.deepseek_translation_model,
            base_url=settings.primary_review_base_url,
        )

        review_summary = asyncio.run(
            review_pending_incidents(
                repository,
                source_fetcher=source_fetcher,
                review_client=review_client,
                escalation_client=escalation_client,
                translation_client=translation_client,
                embedding_client=embedding_client,
                duplicate_judge_client=duplicate_judge_client,
                primary_model=settings.primary_review_model,
                escalation_model=settings.escalation_review_model,
                embedding_model=settings.openai_embedding_model,
                duplicate_judge_model=settings.escalation_review_model,
                max_reviews=args.max_reviews,
                source_registry_keys=args.source_registry_keys,
                concurrency=review_concurrency,
                adaptive_backoff_max_seconds=args.backoff_max_seconds,
            )
        )

        summary = {
            "reviews_attempted": review_summary.reviews_attempted,
            "reviews_completed": review_summary.reviews_completed,
            "reviews_failed": review_summary.reviews_failed,
            "approved": review_summary.approved,
            "pending_review": review_summary.pending_review,
            "rejected": review_summary.rejected,
            "translations_completed": review_summary.translations_completed,
            "translations_failed": review_summary.translations_failed,
            "review_failures": [
                {
                    "incident_id": f.incident_id,
                    "external_id": f.external_id,
                    "error": f.error,
                }
                for f in review_summary.review_failures
            ],
        }

        LOGGER.info(
            "Review complete: attempted=%d completed=%d failed=%d "
            "approved=%d pending_review=%d rejected=%d "
            "translations=%d",
            summary["reviews_attempted"],
            summary["reviews_completed"],
            summary["reviews_failed"],
            summary["approved"],
            summary["pending_review"],
            summary["rejected"],
            summary["translations_completed"],
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    except Exception:
        LOGGER.exception("Incident review failed")
        raise
    finally:
        repository.close()


def _dry_run(settings, args) -> int:
    """Print a count of pending incidents without calling any APIs."""
    repository = build_incident_repository(settings.database_url)
    try:
        incidents = repository.list_incidents_pending_llm_review(
            source_registry_keys=args.source_registry_keys,
        )
        if args.max_reviews is not None:
            incidents = incidents[: args.max_reviews]
        summary = {
            "dry_run": True,
            "pending_incidents_found": len(incidents),
            "incident_ids": [str(i["id"]) for i in incidents],
        }
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
