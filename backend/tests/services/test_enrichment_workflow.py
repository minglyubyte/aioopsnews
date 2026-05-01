from __future__ import annotations

from datetime import datetime, timezone

from app.scrapers.rss import RSSArticle
from app.services.classifier import classify_incident
from app.services.summarizer import summarize_incident
from app.workflows.enrich_pending_incidents import enrich_pending_incidents
from tests.support.fakes import InMemoryIncidentRepository

ASSISTCO_CLAIM = "Our assistant will eliminate repetitive support escalations."


def test_summarizer_produces_neutral_two_sentence_summary() -> None:
    summary = summarize_incident(
        headline="AssistCo support bot leaks internal notes",
        source_summary=(
            "A customer support assistant exposed private account notes in "
            "user-facing replies before the feature was disabled."
        ),
    )

    assert "private account notes" in summary
    assert summary.count(".") == 2
    assert "must" not in summary.lower()


def test_classifier_returns_structured_category_and_company() -> None:
    classification = classify_incident(
        headline="AssistCo support bot leaks internal notes",
        source_summary=(
            "A customer support assistant exposed private account notes in "
            "user-facing replies before the feature was disabled."
        ),
    )

    assert classification.company_involved == "AssistCo"
    assert classification.categories == ["Privacy/Security"]
    assert 0.0 < classification.confidence_score <= 1.0


def test_enrichment_workflow_updates_pending_incidents_in_place() -> None:
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

    repository.ingest_rss_article(
        RSSArticle(
            source_key="test-source",
            publisher="Example News",
            title="AssistCo support bot leaks internal notes",
            url="https://example.com/articles/assistco-support-bot",
            summary=(
                "A customer support assistant exposed private account notes in "
                "user-facing replies before the feature was disabled."
            ),
            published_at=datetime(2026, 4, 30, 8, 0, tzinfo=timezone.utc),
            source_type="secondary",
        ),
        ingestion_run_id="run-2026-04-30",
    )
    repository.ingest_rss_article(
        RSSArticle(
            source_key="test-source",
            publisher="Example News",
            title="RoboFleet delivery robot pilot pauses after safety interventions",
            url="https://example.com/articles/robofleet-pilot",
            summary=(
                "Repeated sidewalk interventions forced operators to pause a "
                "delivery robot pilot and return to supervised testing."
            ),
            published_at=datetime(2026, 4, 29, 16, 0, tzinfo=timezone.utc),
            source_type="secondary",
        ),
        ingestion_run_id="run-2026-04-30",
    )

    result = enrich_pending_incidents(repository=repository)

    assert result == {
        "pending_found": 2,
        "enriched": 2,
        "skipped": 0,
    }
    assistco_incident = next(
        incident
        for incident in repository.incidents.values()
        if incident["headline"] == "AssistCo support bot leaks internal notes"
    )
    assert assistco_incident["matched_claim_id"] == "claim-1"
    assert assistco_incident["claim_match_confidence"] == 0.91
