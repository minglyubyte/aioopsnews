from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.db.sqlite_repository import SQLiteIncidentRepository
from app.scrapers.rss import RSSArticle
from app.services.classifier import classify_incident
from app.services.summarizer import summarize_incident
from app.workflows.enrich_pending_incidents import enrich_pending_incidents


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


def test_classifier_returns_structured_category_severity_and_company() -> None:
    classification = classify_incident(
        headline="AssistCo support bot leaks internal notes",
        source_summary=(
            "A customer support assistant exposed private account notes in "
            "user-facing replies before the feature was disabled."
        ),
    )

    assert classification.company_involved == "AssistCo"
    assert classification.categories == ["Privacy/Security"]
    assert classification.severity_score == 4
    assert 0.0 < classification.confidence_score <= 1.0


def test_enrichment_workflow_updates_pending_incidents_in_place(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "enrichment.db"
    repository = SQLiteIncidentRepository(f"sqlite:///{database_path}")

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
        "pending_found": 3,
        "enriched": 3,
        "skipped": 0,
    }

    connection = sqlite3.connect(database_path)
    enriched_rows = connection.execute(
        """
        select
            headline,
            company_involved,
            claimant_name,
            categories,
            severity_score,
            reality_summary,
            confidence_score,
            status
        from incident_logs
        where headline in (
            'AssistCo support bot leaks internal notes',
            'RoboFleet delivery robot pilot pauses after safety interventions'
        )
        order by headline asc
        """
    ).fetchall()
    connection.close()

    assert enriched_rows == [
        (
            "AssistCo support bot leaks internal notes",
            "AssistCo",
            "AssistCo",
            '["Privacy/Security"]',
            4,
            (
                "AssistCo support bot leaks internal notes. A customer support "
                "assistant exposed private account notes in user-facing replies "
                "before the feature was disabled."
            ),
            0.87,
            "pending_review",
        ),
        (
            "RoboFleet delivery robot pilot pauses after safety interventions",
            "RoboFleet",
            "RoboFleet",
            '["Autonomous Systems"]',
            3,
            (
                "RoboFleet delivery robot pilot pauses after safety interventions. "
                "Repeated sidewalk interventions forced operators to pause a "
                "delivery robot pilot and return to supervised testing."
            ),
            0.82,
            "pending_review",
        ),
    ]
