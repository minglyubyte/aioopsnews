from __future__ import annotations

import argparse
import logging

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.scripts.batch_wait import wait_for_batch_completion
from app.services.incident_deduplication import (
    OpenAIIncidentDuplicateJudgeClient,
    OpenAIIncidentEmbeddingClient,
)
from app.services.incident_review import (
    OpenAIIncidentReviewClient,
    reconcile_incident_review_batch,
)
from app.services.incident_translation import DeepSeekIncidentTranslationClient

LOGGER = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile a completed OpenAI incident review batch."
    )
    parser.add_argument("batch_id")
    parser.add_argument(
        "--wait-for-completion",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Poll the batch until it reaches a terminal state before reconciling.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=int,
        default=30,
        help="Seconds to sleep between batch status polls when waiting.",
    )
    parser.add_argument(
        "--max-wait-seconds",
        type=int,
        default=None,
        help="Optional maximum number of seconds to wait for batch completion.",
    )
    args = parser.parse_args()
    _configure_logging()

    settings = get_settings()
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY is required for incident review batches")
    if not settings.deepseek_api_key:
        raise SystemExit("DEEPSEEK_API_KEY is required for approved translations")

    repository = build_incident_repository(settings.database_url)
    try:
        review_client = OpenAIIncidentReviewClient(api_key=settings.openai_api_key)
        batch_status = review_client.get_batch_status(batch_id=args.batch_id)
        if batch_status != "completed":
            if not args.wait_for_completion:
                print(
                    " ".join(
                        [
                            f"batch_id={args.batch_id}",
                            f"status={batch_status}",
                            "action=retry_later",
                        ]
                    )
                )
                return 1
            batch_status = wait_for_batch_completion(
                batch_client=review_client,
                batch_id=args.batch_id,
                poll_interval_seconds=args.poll_interval_seconds,
                max_wait_seconds=args.max_wait_seconds,
                logger=LOGGER,
            )
            if batch_status != "completed":
                print(
                    " ".join(
                        [
                            f"batch_id={args.batch_id}",
                            f"status={batch_status}",
                            "action=not_reconciled",
                        ]
                    )
                )
                return 1

        summary = reconcile_incident_review_batch(
            repository,
            batch_id=args.batch_id,
            batch_client=review_client,
            escalation_client=review_client,
            translation_client=DeepSeekIncidentTranslationClient(
                api_key=settings.deepseek_api_key,
                model=settings.deepseek_translation_model,
            ),
            embedding_client=OpenAIIncidentEmbeddingClient(
                api_key=settings.openai_api_key,
            ),
            duplicate_judge_client=OpenAIIncidentDuplicateJudgeClient(
                api_key=settings.openai_api_key,
            ),
            embedding_model=settings.openai_embedding_model,
            duplicate_judge_model=settings.openai_escalation_review_model,
            escalation_model=settings.openai_escalation_review_model,
        )
        print(
            " ".join(
                [
                    f"approved={summary.approved}",
                    f"pending_review={summary.pending_review}",
                    f"rejected={summary.rejected}",
                    f"escalated={summary.escalated}",
                ]
            )
        )
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
