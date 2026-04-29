from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.source_registry import get_trusted_sources
from app.db.sqlite_repository import SQLiteIncidentRepository
from app.scrapers.rss import parse_rss_feed
from app.workflows.daily_ingest import ingest_rss_feed

SAMPLE_RSS = """\
<rss version="2.0">
  <channel>
    <title>Example Feed</title>
    <item>
      <title>Robotics pilot pauses after safety review</title>
      <link>https://example.com/articles/robotics-pilot</link>
      <description>
        Operators halted a pilot after repeated sidewalk interventions.
      </description>
      <pubDate>Wed, 29 Apr 2026 15:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Support assistant leaks internal notes</title>
      <link>https://example.com/articles/support-notes</link>
      <description>
        A support assistant exposed internal account notes to users.
      </description>
      <pubDate>Tue, 28 Apr 2026 08:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def test_trusted_source_registry_exposes_rss_publishers() -> None:
    sources = get_trusted_sources()

    assert len(sources) >= 5
    assert {source.key for source in sources} >= {
        "reuters",
        "associated-press",
        "ars-technica",
        "the-verge",
        "wired",
    }
    assert all(source.rss_url for source in sources)
    assert all(source.source_type == "secondary" for source in sources)


def test_parse_rss_feed_extracts_normalized_articles() -> None:
    source = get_trusted_sources()[0]

    articles = parse_rss_feed(source, SAMPLE_RSS)

    assert [article.title for article in articles] == [
        "Robotics pilot pauses after safety review",
        "Support assistant leaks internal notes",
    ]
    assert articles[0].url == "https://example.com/articles/robotics-pilot"
    assert articles[0].summary.startswith("Operators halted a pilot")
    assert articles[0].publisher == source.publisher


def test_ingest_rss_feed_persists_pending_review_incidents_and_dedupes(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "ingest.db"
    repository = SQLiteIncidentRepository(f"sqlite:///{database_path}")
    source = get_trusted_sources()[0]

    first_run = ingest_rss_feed(
        repository=repository,
        source=source,
        rss_xml=SAMPLE_RSS,
        ingestion_run_id="run-2026-04-29",
    )
    second_run = ingest_rss_feed(
        repository=repository,
        source=source,
        rss_xml=SAMPLE_RSS,
        ingestion_run_id="run-2026-04-29-retry",
    )

    assert first_run == {
        "articles_fetched": 2,
        "incidents_created": 2,
        "duplicates_skipped": 0,
    }
    assert second_run == {
        "articles_fetched": 2,
        "incidents_created": 0,
        "duplicates_skipped": 2,
    }

    connection = sqlite3.connect(database_path)
    incident_rows = connection.execute(
        """
        select headline, company_involved, status, ingestion_run_id
        from incident_logs
        where headline in (
            'Robotics pilot pauses after safety review',
            'Support assistant leaks internal notes'
        )
        order by date_logged desc
        """
    ).fetchall()
    source_rows = connection.execute(
        """
        select source_url, source_type, publisher
        from incident_sources
        where source_url like 'https://example.com/articles/%'
        order by source_url asc
        """
    ).fetchall()
    connection.close()

    assert incident_rows == [
        (
            "Robotics pilot pauses after safety review",
            "Pending classification",
            "pending_review",
            "run-2026-04-29",
        ),
        (
            "Support assistant leaks internal notes",
            "Pending classification",
            "pending_review",
            "run-2026-04-29",
        ),
    ]
    assert source_rows == [
        (
            "https://example.com/articles/robotics-pilot",
            "secondary",
            source.publisher,
        ),
        (
            "https://example.com/articles/support-notes",
            "secondary",
            source.publisher,
        ),
    ]
