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
    IncidentBatchReviewClient,
    IncidentEscalationReviewClient,
    IncidentSourceFetcher,
    reconcile_incident_review_batch,
    submit_incident_review_batch,
)
from app.services.incident_translation import IncidentTranslationClient


def run_incident_csv_workflow(
    *,
    repository: IncidentRepository,
    inbox_dir: Path,
    archive_dir: Path,
    source_fetcher: IncidentSourceFetcher,
    batch_client: IncidentBatchReviewClient,
    escalation_client: IncidentEscalationReviewClient,
    translation_client: IncidentTranslationClient,
    embedding_client: IncidentEmbeddingClient,
    duplicate_judge_client: IncidentDuplicateJudgeClient,
    primary_model: str,
    escalation_model: str,
    embedding_model: str = "text-embedding-3-small",
    duplicate_judge_model: str | None = None,
    dry_run: bool = False,
    submit_new_batches: bool = True,
    reconcile_ready_batches: bool = True,
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
        "batches_submitted": 0,
        "batches_reconciled": 0,
        "batches_skipped": 0,
        "approved": 0,
        "pending_review": 0,
        "rejected": 0,
        "translations_completed": 0,
        "translations_failed": 0,
        "file_results": [],
        "batch_results": [],
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

    if submit_new_batches:
        pending_without_batch = [
            incident
            for incident in repository.list_incidents_pending_llm_review()
            if not incident.get("review_batch_id")
        ]
        if pending_without_batch:
            batch_submission = submit_incident_review_batch(
                repository,
                source_fetcher=source_fetcher,
                batch_client=batch_client,
                primary_model=primary_model,
            )
            summary["batches_submitted"] += 1
            summary["batch_results"].append(
                {
                    "batch_id": batch_submission.batch_id,
                    "status": "submitted",
                    "submitted": batch_submission.submitted,
                }
            )

    if reconcile_ready_batches:
        pending_incidents = repository.list_incidents_pending_llm_review()
        seen_batch_ids: set[str] = set()
        for incident in pending_incidents:
            batch_id = incident.get("review_batch_id")
            if not batch_id or batch_id in seen_batch_ids:
                continue
            seen_batch_ids.add(batch_id)
            batch_status = batch_client.get_batch_status(batch_id=batch_id)
            if batch_status != "completed":
                summary["batches_skipped"] += 1
                summary["batch_results"].append(
                    {
                        "batch_id": batch_id,
                        "status": batch_status,
                    }
                )
                continue

            reconcile_summary = reconcile_incident_review_batch(
                repository,
                batch_id=batch_id,
                batch_client=batch_client,
                escalation_client=escalation_client,
                translation_client=translation_client,
                embedding_client=embedding_client,
                duplicate_judge_client=duplicate_judge_client,
                embedding_model=embedding_model,
                duplicate_judge_model=duplicate_judge_model or escalation_model,
                escalation_model=escalation_model,
            )
            summary["batches_reconciled"] += 1
            summary["approved"] += reconcile_summary.approved
            summary["pending_review"] += reconcile_summary.pending_review
            summary["rejected"] += reconcile_summary.rejected
            summary["translations_completed"] += reconcile_summary.approved
            summary["batch_results"].append(
                {
                    "batch_id": batch_id,
                    "status": "completed",
                    "approved": reconcile_summary.approved,
                    "pending_review": reconcile_summary.pending_review,
                    "rejected": reconcile_summary.rejected,
                    "escalated": reconcile_summary.escalated,
                }
            )

    return summary


def _archive_csv(csv_path: Path, archive_dir: Path) -> None:
    archive_dir.mkdir(parents=True, exist_ok=True)
    destination = archive_dir / csv_path.name
    if destination.exists():
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        destination = archive_dir / f"{csv_path.stem}-{timestamp}{csv_path.suffix}"
    shutil.move(str(csv_path), str(destination))
