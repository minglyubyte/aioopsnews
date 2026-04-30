from __future__ import annotations

from collections.abc import Callable

from app.core.source_registry import SourceDefinition
from app.db.repository_protocol import IncidentRepository
from app.scrapers.rss import RSSArticle, parse_rss_feed
from app.workflows.enrich_pending_incidents import enrich_pending_incidents


def ingest_rss_feed(
    *,
    repository: IncidentRepository,
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


def run_daily_ingestion(
    *,
    repository: IncidentRepository,
    sources: list[SourceDefinition],
    fetch_articles: Callable[[str], list[RSSArticle]],
    ingestion_run_id: str,
    max_retries: int = 1,
) -> dict[str, object]:
    source_results: list[dict[str, object]] = []
    articles_fetched = 0
    incidents_created = 0
    duplicates_skipped = 0
    sources_processed = 0
    source_failures = 0

    for source in sources:
        attempts = 0
        last_error: Exception | None = None
        articles: list[RSSArticle] | None = None

        while attempts <= max_retries:
            attempts += 1
            try:
                articles = fetch_articles(source.key)
                break
            except Exception as error:
                last_error = error

        if articles is None:
            source_failures += 1
            source_results.append(
                {
                    "source_key": source.key,
                    "status": "failed",
                    "attempts": attempts,
                    "error": str(last_error) if last_error else "Unknown fetch error",
                }
            )
            continue

        sources_processed += 1
        created_for_source = 0
        duplicates_for_source = 0

        for article in articles:
            created = repository.ingest_rss_article(
                article,
                ingestion_run_id=ingestion_run_id,
            )
            if created:
                created_for_source += 1
            else:
                duplicates_for_source += 1

        enrich_result = enrich_pending_incidents(repository=repository)
        review_queue = repository.list_review_queue()
        matched_claims = sum(
            1 for incident in review_queue if incident["matched_claim_id"] is not None
        )
        pending_review_count = len(review_queue)

        source_results.append(
            {
                "source_key": source.key,
                "status": "ok",
                "attempts": attempts,
                "fetch": {"articles_fetched": len(articles)},
                "dedupe": {"duplicates_skipped": duplicates_for_source},
                "persist": {"incidents_created": created_for_source},
                "enrich": enrich_result,
                "claim_match": {
                    "matched_claims": matched_claims,
                    "unmatched_incidents": pending_review_count - matched_claims,
                },
                "mark_review_status": {"pending_review": pending_review_count},
            }
        )

        articles_fetched += len(articles)
        incidents_created += created_for_source
        duplicates_skipped += duplicates_for_source

    incidents_flagged_for_manual_review = len(repository.list_review_queue())

    return {
        "run_id": ingestion_run_id,
        "sources_processed": sources_processed,
        "source_failures": source_failures,
        "articles_fetched": articles_fetched,
        "incidents_created": incidents_created,
        "duplicates_skipped": duplicates_skipped,
        "incidents_flagged_for_manual_review": incidents_flagged_for_manual_review,
        "source_results": source_results,
    }
