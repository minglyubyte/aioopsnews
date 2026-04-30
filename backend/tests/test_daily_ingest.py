from __future__ import annotations

from datetime import datetime, timezone

from app.core.source_registry import get_trusted_sources
from app.scrapers.rss import RSSArticle, parse_rss_feed
from app.workflows.daily_ingest import ingest_rss_feed, run_daily_ingestion
from tests.fakes import InMemoryIncidentRepository

ASSISTCO_CLAIM = "Our assistant will eliminate repetitive support escalations."

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


def test_ingest_rss_feed_persists_pending_review_incidents_and_dedupes() -> None:
    repository = InMemoryIncidentRepository()
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
    assert sorted(repository.incidents) == ["incident-1", "incident-2"]


def test_run_daily_ingestion_records_stage_metrics_and_manual_review_volume() -> None:
    repository = InMemoryIncidentRepository(
        claims=[
            {
                "id": "claim-1",
                "claimant_name": "AssistCo",
                "company_involved": "AssistCo",
                "original_claim": ASSISTCO_CLAIM,
                "claim_date": "2026-01-15",
                "claim_topic": "job automation",
                "status": "approved",
                "notes": None,
            }
        ]
    )
    sources = [get_trusted_sources()[0]]

    def fetch_articles(source_key: str) -> list[RSSArticle]:
        assert source_key == sources[0].key
        return [
            RSSArticle(
                source_key=source_key,
                publisher=sources[0].publisher,
                title="AssistCo support bot leaks internal notes",
                url="https://example.com/articles/support-leak",
                summary=(
                    "A customer support assistant exposed private account notes in "
                    "user-facing replies before the feature was disabled."
                ),
                published_at=datetime(2026, 4, 30, 8, 0, tzinfo=timezone.utc),
                source_type="secondary",
            )
        ]

    result = run_daily_ingestion(
        repository=repository,
        sources=sources,
        fetch_articles=fetch_articles,
        ingestion_run_id="daily-run-2026-04-30",
    )

    assert result["articles_fetched"] == 1
    assert result["incidents_created"] == 1
    assert result["duplicates_skipped"] == 0
    assert result["incidents_flagged_for_manual_review"] == 1
    assert result["source_failures"] == 0
    assert result["sources_processed"] == 1
    assert result["source_results"][0]["claim_match"]["matched_claims"] == 1


def test_run_daily_ingestion_retries_transient_source_failure_and_reports_errors() -> (
    None
):
    repository = InMemoryIncidentRepository()
    sources = [get_trusted_sources()[0], get_trusted_sources()[1]]
    attempts: dict[str, int] = {}

    def fetch_articles(source_key: str) -> list[RSSArticle]:
        attempts[source_key] = attempts.get(source_key, 0) + 1

        if source_key == sources[0].key and attempts[source_key] == 1:
            raise TimeoutError("temporary timeout")
        if source_key == sources[1].key:
            raise RuntimeError("feed unavailable")

        return [
            RSSArticle(
                source_key=source_key,
                publisher=sources[0].publisher,
                title="AssistCo support bot leaks internal notes",
                url=f"https://example.com/articles/{source_key}-support-leak",
                summary=(
                    "A customer support assistant exposed private account notes in "
                    "user-facing replies before the feature was disabled."
                ),
                published_at=datetime(2026, 4, 30, 8, 0, tzinfo=timezone.utc),
                source_type="secondary",
            )
        ]

    result = run_daily_ingestion(
        repository=repository,
        sources=sources,
        fetch_articles=fetch_articles,
        ingestion_run_id="daily-run-2026-05-01",
        max_retries=2,
    )

    assert result["articles_fetched"] == 1
    assert result["incidents_created"] == 1
    assert result["source_failures"] == 1
    assert result["sources_processed"] == 1
    assert attempts == {
        sources[0].key: 2,
        sources[1].key: 3,
    }
