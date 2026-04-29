from __future__ import annotations

from app.core.source_registry import SourceDefinition
from app.db.sqlite_repository import SQLiteIncidentRepository
from app.scrapers.rss import parse_rss_feed


def ingest_rss_feed(
    *,
    repository: SQLiteIncidentRepository,
    source: SourceDefinition,
    rss_xml: str,
    ingestion_run_id: str,
) -> dict[str, int]:
    articles = parse_rss_feed(source, rss_xml)
    incidents_created = 0
    duplicates_skipped = 0

    for article in articles:
        created = repository.ingest_rss_article(
            article,
            ingestion_run_id=ingestion_run_id,
        )
        if created:
            incidents_created += 1
        else:
            duplicates_skipped += 1

    return {
        "articles_fetched": len(articles),
        "incidents_created": incidents_created,
        "duplicates_skipped": duplicates_skipped,
    }
