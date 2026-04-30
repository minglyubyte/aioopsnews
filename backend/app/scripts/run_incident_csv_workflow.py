from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.scripts.batch_wait import wait_for_batch_completion
from app.services.incident_deduplication import (
    OpenAIIncidentDuplicateJudgeClient,
    OpenAIIncidentEmbeddingClient,
)
from app.services.incident_review import (
    HttpIncidentSourceFetcher,
    OpenAIIncidentReviewClient,
    reconcile_incident_review_batch,
)
from app.services.incident_translation import DeepSeekIncidentTranslationClient
from app.workflows.incident_csv_workflow import run_incident_csv_workflow

LOGGER = logging.getLogger(__name__)


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
    parser.add_argument(
        "--wait-for-batches",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Poll submitted or validating batches until they reach a terminal state.",
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
    repository = build_incident_repository(settings.database_url)
    try:
        LOGGER.info(
            "Starting incident CSV workflow: inbox=%s archive=%s dry_run=%s "
            "submit_new_batches=%s reconcile_ready_batches=%s",
            args.inbox_dir,
            args.archive_dir,
            args.dry_run,
            args.submit_new_batches,
            args.reconcile_ready_batches,
        )
        source_fetcher = HttpIncidentSourceFetcher()
        batch_client = OpenAIIncidentReviewClient(
            api_key=settings.openai_api_key or ""
        )
        embedding_client = OpenAIIncidentEmbeddingClient(
            api_key=settings.openai_api_key or ""
        )
        duplicate_judge_client = OpenAIIncidentDuplicateJudgeClient(
            api_key=settings.openai_api_key or ""
        )
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
            embedding_client=embedding_client,
            duplicate_judge_client=duplicate_judge_client,
            primary_model=settings.openai_primary_review_model,
            escalation_model=settings.openai_escalation_review_model,
            embedding_model=settings.openai_embedding_model,
            dry_run=args.dry_run,
            submit_new_batches=args.submit_new_batches,
            reconcile_ready_batches=args.reconcile_ready_batches,
        )
        if args.wait_for_batches and not args.dry_run:
            _wait_for_and_reconcile_batches(
                summary=summary,
                repository=repository,
                batch_client=batch_client,
                translation_client=translation_client,
                embedding_client=embedding_client,
                duplicate_judge_client=duplicate_judge_client,
                escalation_model=settings.openai_escalation_review_model,
                embedding_model=settings.openai_embedding_model,
                duplicate_judge_model=settings.openai_escalation_review_model,
                poll_interval_seconds=args.poll_interval_seconds,
                max_wait_seconds=args.max_wait_seconds,
            )
        LOGGER.info(
            "Completed incident CSV workflow: files_found=%s files_imported=%s "
            "files_failed=%s incidents_imported=%s batches_submitted=%s "
            "batches_reconciled=%s approved=%s pending_review=%s rejected=%s "
            "translations_completed=%s",
            summary.get("files_found"),
            summary.get("files_imported"),
            summary.get("files_failed"),
            summary.get("incidents_imported"),
            summary.get("batches_submitted"),
            summary.get("batches_reconciled"),
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


def _wait_for_and_reconcile_batches(
    *,
    summary: dict[str, object],
    repository,
    batch_client,
    translation_client,
    embedding_client,
    duplicate_judge_client,
    escalation_model: str,
    embedding_model: str,
    duplicate_judge_model: str,
    poll_interval_seconds: int,
    max_wait_seconds: int | None,
) -> None:
    pending_batch_ids = _pending_batch_ids(summary)
    for batch_id in pending_batch_ids:
        final_status = wait_for_batch_completion(
            batch_client=batch_client,
            batch_id=batch_id,
            poll_interval_seconds=poll_interval_seconds,
            max_wait_seconds=max_wait_seconds,
            logger=LOGGER,
        )
        if final_status != "completed":
            summary["batch_results"].append(
                {
                    "batch_id": batch_id,
                    "status": final_status,
                }
            )
            continue

        reconcile_summary = reconcile_incident_review_batch(
            repository,
            batch_id=batch_id,
            batch_client=batch_client,
            escalation_client=batch_client,
            translation_client=translation_client,
            embedding_client=embedding_client,
            duplicate_judge_client=duplicate_judge_client,
            embedding_model=embedding_model,
            duplicate_judge_model=duplicate_judge_model,
            escalation_model=escalation_model,
        )
        summary["batches_reconciled"] = int(summary["batches_reconciled"]) + 1
        summary["approved"] = int(summary["approved"]) + reconcile_summary.approved
        summary["pending_review"] = (
            int(summary["pending_review"]) + reconcile_summary.pending_review
        )
        summary["rejected"] = int(summary["rejected"]) + reconcile_summary.rejected
        summary["translations_completed"] = (
            int(summary["translations_completed"]) + reconcile_summary.approved
        )
        summary["batch_results"].append(
            {
                "batch_id": batch_id,
                "status": "completed_after_wait",
                "approved": reconcile_summary.approved,
                "pending_review": reconcile_summary.pending_review,
                "rejected": reconcile_summary.rejected,
                "escalated": reconcile_summary.escalated,
            }
        )


def _pending_batch_ids(summary: dict[str, object]) -> list[str]:
    pending_statuses = {"submitted", "validating", "in_progress", "finalizing"}
    batch_ids: list[str] = []
    seen_batch_ids: set[str] = set()
    for batch_result in summary.get("batch_results", []):
        if not isinstance(batch_result, dict):
            continue
        batch_id = batch_result.get("batch_id")
        status = batch_result.get("status")
        if not isinstance(batch_id, str) or status not in pending_statuses:
            continue
        if batch_id in seen_batch_ids:
            continue
        seen_batch_ids.add(batch_id)
        batch_ids.append(batch_id)
    return batch_ids


if __name__ == "__main__":
    raise SystemExit(main())
