from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from app.core.source_registry import SourceDefinition
from app.db.sqlite_repository import SQLiteIncidentRepository
from app.scrapers.rss import RSSArticle
from app.workflows.backfill import plan_backfill_batches, run_historical_backfill


def test_plan_backfill_batches_partitions_date_range_monthly() -> None:
    batches = plan_backfill_batches(
        start_date=date(2022, 11, 30),
        end_date=date(2023, 2, 10),
        months_per_batch=1,
    )

    assert [(batch.start_date, batch.end_date) for batch in batches] == [
        (date(2022, 11, 30), date(2022, 11, 30)),
        (date(2022, 12, 1), date(2022, 12, 31)),
        (date(2023, 1, 1), date(2023, 1, 31)),
        (date(2023, 2, 1), date(2023, 2, 10)),
    ]


def test_run_historical_backfill_pilot_mode_processes_one_source_and_one_batch(
    tmp_path: Path,
) -> None:
    repository = SQLiteIncidentRepository(f"sqlite:///{tmp_path / 'pilot.db'}")
    checkpoint_path = tmp_path / "backfill-checkpoint.json"
    audit_path = tmp_path / "backfill-audit.json"
    sources = [
        SourceDefinition(
            key="example-news",
            publisher="Example News",
            rss_url="https://example.com/rss",
        ),
        SourceDefinition(
            key="city-ledger",
            publisher="City Ledger",
            rss_url="https://example.com/city-ledger",
        ),
    ]

    def fetch_articles(
        source: SourceDefinition,
        start_date: date,
        end_date: date,
    ) -> list[RSSArticle]:
        return [
            RSSArticle(
                source_key=source.key,
                publisher=source.publisher,
                title=f"{source.publisher} incident during {start_date.isoformat()}",
                url=f"https://example.com/{source.key}/{start_date.isoformat()}",
                summary="Historical article summary.",
                published_at=datetime(2023, 1, 15, 12, 0, tzinfo=timezone.utc),
                source_type=source.source_type,
            )
        ]

    result = run_historical_backfill(
        repository=repository,
        sources=sources,
        start_date=date(2023, 1, 1),
        end_date=date(2023, 2, 28),
        checkpoint_path=checkpoint_path,
        audit_path=audit_path,
        fetch_articles=fetch_articles,
        pilot_mode=True,
    )

    assert result == {
        "batches_planned": 2,
        "batches_completed": 1,
        "sources_processed": 1,
        "articles_fetched": 1,
        "incidents_created": 1,
        "duplicates_skipped": 0,
    }

    audit_payload = json.loads(audit_path.read_text())
    assert len(audit_payload["entries"]) == 1
    assert audit_payload["entries"][0]["source_key"] == "example-news"
    assert audit_payload["entries"][0]["batch_start"] == "2023-01-01"


def test_run_historical_backfill_resumes_from_checkpoint_without_duplicates(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "resume.db"
    repository = SQLiteIncidentRepository(f"sqlite:///{database_path}")
    checkpoint_path = tmp_path / "resume-checkpoint.json"
    audit_path = tmp_path / "resume-audit.json"
    source = SourceDefinition(
        key="example-news",
        publisher="Example News",
        rss_url="https://example.com/rss",
    )

    def fetch_articles(
        current_source: SourceDefinition,
        start_date: date,
        end_date: date,
    ) -> list[RSSArticle]:
        assert current_source.key == source.key
        return [
            RSSArticle(
                source_key=current_source.key,
                publisher=current_source.publisher,
                title=f"Incident for {start_date.isoformat()}",
                url=f"https://example.com/{current_source.key}/{start_date.isoformat()}",
                summary="Historical article summary.",
                published_at=datetime.combine(
                    start_date,
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                ),
                source_type=current_source.source_type,
            )
        ]

    first_run = run_historical_backfill(
        repository=repository,
        sources=[source],
        start_date=date(2023, 1, 1),
        end_date=date(2023, 2, 28),
        checkpoint_path=checkpoint_path,
        audit_path=audit_path,
        fetch_articles=fetch_articles,
        max_batches=1,
    )
    second_run = run_historical_backfill(
        repository=repository,
        sources=[source],
        start_date=date(2023, 1, 1),
        end_date=date(2023, 2, 28),
        checkpoint_path=checkpoint_path,
        audit_path=audit_path,
        fetch_articles=fetch_articles,
    )

    assert first_run["batches_completed"] == 1
    assert second_run == {
        "batches_planned": 2,
        "batches_completed": 1,
        "sources_processed": 1,
        "articles_fetched": 1,
        "incidents_created": 1,
        "duplicates_skipped": 0,
    }

    connection = sqlite3.connect(database_path)
    incident_count = connection.execute(
        """
        select count(*)
        from incident_logs
        where headline like 'Incident for %'
        """
    ).fetchone()[0]
    connection.close()

    assert incident_count == 2
