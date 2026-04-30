from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from app.core.source_registry import SourceDefinition
from app.db.sqlite_repository import SQLiteIncidentRepository
from app.scrapers.rss import RSSArticle
from app.workflows.enrich_pending_incidents import enrich_pending_incidents


@dataclass(frozen=True)
class BackfillBatch:
    start_date: date
    end_date: date

    @property
    def key(self) -> str:
        return f"{self.start_date.isoformat()}:{self.end_date.isoformat()}"


FetchArticles = Callable[[SourceDefinition, date, date], list[RSSArticle]]


def plan_backfill_batches(
    *,
    start_date: date,
    end_date: date,
    months_per_batch: int = 1,
) -> list[BackfillBatch]:
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    if months_per_batch < 1:
        raise ValueError("months_per_batch must be at least 1")

    batches: list[BackfillBatch] = []
    cursor = start_date

    while cursor <= end_date:
        batch_end = _end_of_batch(
            cursor=cursor,
            end_date=end_date,
            months_per_batch=months_per_batch,
        )
        batches.append(BackfillBatch(start_date=cursor, end_date=batch_end))
        cursor = _next_day(batch_end)

    return batches


def run_historical_backfill(
    *,
    repository: SQLiteIncidentRepository,
    sources: list[SourceDefinition],
    start_date: date,
    end_date: date,
    checkpoint_path: Path,
    audit_path: Path,
    fetch_articles: FetchArticles,
    months_per_batch: int = 1,
    pilot_mode: bool = False,
    max_batches: int | None = None,
) -> dict[str, int]:
    batches = plan_backfill_batches(
        start_date=start_date,
        end_date=end_date,
        months_per_batch=months_per_batch,
    )
    selected_batches = batches[:1] if pilot_mode else batches
    selected_sources = sources[:1] if pilot_mode else sources

    checkpoint = _load_checkpoint(checkpoint_path)
    audit_log = _load_audit_log(audit_path)

    batches_completed = 0
    sources_processed = 0
    articles_fetched = 0
    incidents_created = 0
    duplicates_skipped = 0

    for batch in selected_batches:
        if max_batches is not None and batches_completed >= max_batches:
            break

        batch_processed = False

        for source in selected_sources:
            checkpoint_key = f"{source.key}|{batch.key}"
            if checkpoint_key in checkpoint["completed"]:
                continue

            articles = fetch_articles(source, batch.start_date, batch.end_date)
            created_for_batch = 0
            duplicates_for_batch = 0

            for article in articles:
                created = repository.ingest_rss_article(
                    article,
                    ingestion_run_id=(
                        f"backfill:{source.key}:{batch.start_date.isoformat()}"
                    ),
                )
                if created:
                    created_for_batch += 1
                else:
                    duplicates_for_batch += 1

            enrich_pending_incidents(repository=repository)

            audit_log["entries"].append(
                {
                    "source_key": source.key,
                    "publisher": source.publisher,
                    "batch_start": batch.start_date.isoformat(),
                    "batch_end": batch.end_date.isoformat(),
                    "articles_fetched": len(articles),
                    "incidents_created": created_for_batch,
                    "duplicates_skipped": duplicates_for_batch,
                }
            )

            checkpoint["completed"].append(checkpoint_key)
            _write_checkpoint(checkpoint_path, checkpoint)
            _write_audit_log(audit_path, audit_log)

            sources_processed += 1
            articles_fetched += len(articles)
            incidents_created += created_for_batch
            duplicates_skipped += duplicates_for_batch
            batch_processed = True

        if batch_processed:
            batches_completed += 1

    return {
        "batches_planned": len(batches),
        "batches_completed": batches_completed,
        "sources_processed": sources_processed,
        "articles_fetched": articles_fetched,
        "incidents_created": incidents_created,
        "duplicates_skipped": duplicates_skipped,
    }


def _end_of_batch(
    *,
    cursor: date,
    end_date: date,
    months_per_batch: int,
) -> date:
    year = cursor.year
    month = cursor.month

    for _ in range(months_per_batch):
        month += 1
        if month == 13:
            month = 1
            year += 1

    batch_start_of_next_month = date(year, month, 1)
    batch_end = _previous_day(batch_start_of_next_month)
    return min(batch_end, end_date)


def _next_day(value: date) -> date:
    return value.fromordinal(value.toordinal() + 1)


def _previous_day(value: date) -> date:
    return value.fromordinal(value.toordinal() - 1)


def _load_checkpoint(checkpoint_path: Path) -> dict[str, list[str]]:
    if checkpoint_path.exists():
        return json.loads(checkpoint_path.read_text())
    return {"completed": []}


def _write_checkpoint(checkpoint_path: Path, checkpoint: dict[str, list[str]]) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True))


def _load_audit_log(audit_path: Path) -> dict[str, list[dict[str, object]]]:
    if audit_path.exists():
        return json.loads(audit_path.read_text())
    return {"entries": []}


def _write_audit_log(
    audit_path: Path,
    audit_log: dict[str, list[dict[str, object]]],
) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit_log, indent=2, sort_keys=True))
