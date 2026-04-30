from __future__ import annotations

import argparse

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.services.incident_review import (
    OpenAIIncidentReviewClient,
    reconcile_incident_review_batch,
)
from app.services.incident_translation import DeepSeekIncidentTranslationClient


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile a completed OpenAI incident review batch."
    )
    parser.add_argument("batch_id")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY is required for incident review batches")
    if not settings.deepseek_api_key:
        raise SystemExit("DEEPSEEK_API_KEY is required for approved translations")

    repository = build_incident_repository(settings.database_url)
    review_client = OpenAIIncidentReviewClient(api_key=settings.openai_api_key)
    summary = reconcile_incident_review_batch(
        repository,
        batch_id=args.batch_id,
        batch_client=review_client,
        escalation_client=review_client,
        translation_client=DeepSeekIncidentTranslationClient(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_translation_model,
        ),
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


if __name__ == "__main__":
    raise SystemExit(main())
