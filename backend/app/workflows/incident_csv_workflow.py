from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.db.repository_protocol import IncidentRepository
from app.services.incident_deduplication import (
    IncidentDuplicateJudgeClient,
    IncidentEmbeddingClient,
)
from app.services.incident_import import (
    IncidentImportValidationError,
    import_incidents_csv_text,
)
from app.services.incident_review import (
    AsyncIncidentReviewClient,
    IncidentEscalationReviewClient,
    IncidentSourceFetcher,
    review_pending_incidents,
)
from app.services.incident_translation import IncidentTranslationClient


async def run_incident_csv_workflow(
    *,
    repository: IncidentRepository,
    inbox_dir: Path,
    archive_dir: Path,
    source_fetcher: IncidentSourceFetcher,
    review_client: AsyncIncidentReviewClient,
    escalation_client: IncidentEscalationReviewClient,
    translation_client: IncidentTranslationClient,
    embedding_client: IncidentEmbeddingClient,
    duplicate_judge_client: IncidentDuplicateJudgeClient,
    primary_model: str,
    escalation_model: str,
    embedding_model: str = "text-embedding-3-small",
    duplicate_judge_model: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    csv_paths = (
        sorted(path for path in inbox_dir.glob("*.csv"))
        if inbox_dir.exists()
        else []
    )

    summary: dict[str, Any] = {
        "files_found": len(csv_paths),
        "files_imported": 0,
        "files_failed": 0,
        "incidents_imported": 0,
        "reviews_attempted": 0,
        "reviews_completed": 0,
        "reviews_failed": 0,
        "review_failures": [],
        "approved": 0,
        "pending_review": 0,
        "rejected": 0,
        "translations_completed": 0,
        "translations_failed": 0,
        "file_results": [],
    }

    for csv_path in csv_paths:
        try:
            import_summary = import_incidents_csv_text(
                repository,
                csv_path.read_text(encoding="utf-8"),
                dry_run=dry_run,
            )
        except IncidentImportValidationError as exc:
            summary["files_failed"] += 1
            summary["file_results"].append(
                {
                    "path": str(csv_path),
                    "status": "failed",
                    "error": str(exc),
                }
            )
            continue

        summary["files_imported"] += 1
        summary["incidents_imported"] += import_summary.inserted
        summary["file_results"].append(
            {
                "path": str(csv_path),
                "status": "imported",
                "validated": import_summary.validated,
                "inserted": import_summary.inserted,
            }
        )

        if not dry_run:
            _archive_csv(csv_path, archive_dir)

    if dry_run:
        return summary

    review_summary = await review_pending_incidents(
        repository,
        source_fetcher=source_fetcher,
        review_client=review_client,
        escalation_client=escalation_client,
        translation_client=translation_client,
        embedding_client=embedding_client,
        duplicate_judge_client=duplicate_judge_client,
        primary_model=primary_model,
        escalation_model=escalation_model,
        embedding_model=embedding_model,
        duplicate_judge_model=duplicate_judge_model or escalation_model,
    )
    summary["reviews_attempted"] = review_summary.reviews_attempted
    summary["reviews_completed"] = review_summary.reviews_completed
    summary["reviews_failed"] = review_summary.reviews_failed
    summary["review_failures"] = [
        {
            "incident_id": failure.incident_id,
            "external_id": failure.external_id,
            "error": failure.error,
        }
        for failure in review_summary.review_failures
    ]
    summary["approved"] = review_summary.approved
    summary["pending_review"] = review_summary.pending_review
    summary["rejected"] = review_summary.rejected
    summary["translations_completed"] = review_summary.translations_completed
    summary["translations_failed"] = review_summary.translations_failed
    return summary


def _archive_csv(csv_path: Path, archive_dir: Path) -> None:
    archive_dir.mkdir(parents=True, exist_ok=True)
    destination = archive_dir / csv_path.name
    if destination.exists():
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        destination = archive_dir / f"{csv_path.stem}-{timestamp}{csv_path.suffix}"
    shutil.move(str(csv_path), str(destination))
