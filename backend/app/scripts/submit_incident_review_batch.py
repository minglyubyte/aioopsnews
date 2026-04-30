from __future__ import annotations

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.services.incident_review import (
    HttpIncidentSourceFetcher,
    OpenAIIncidentReviewClient,
    submit_incident_review_batch,
)


def main() -> int:
    settings = get_settings()
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY is required for incident review batches")

    repository = build_incident_repository(settings.database_url)
    submission = submit_incident_review_batch(
        repository,
        source_fetcher=HttpIncidentSourceFetcher(),
        batch_client=OpenAIIncidentReviewClient(api_key=settings.openai_api_key),
        primary_model=settings.openai_primary_review_model,
    )
    print(
        " ".join(
            [
                f"batch_id={submission.batch_id}",
                f"submitted={submission.submitted}",
                f"model={submission.model}",
            ]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
