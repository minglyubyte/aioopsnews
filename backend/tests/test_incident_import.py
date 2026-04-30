from __future__ import annotations

import pytest

from app.services.incident_import import (
    IncidentImportValidationError,
    import_incidents_csv_text,
    parse_incidents_csv_text,
)
from tests.fakes import InMemoryIncidentRepository

VALID_IMPORT_CSV = "\n".join(
    [
        (
            "ref_number,incident_id,company,incident_date,incident_topic,"
            "incident_description,mapped_claim,source_links,legitimacy_flag,"
            "confidence_level,notes"
        ),
        (
            "1,inc-openai-001,OpenAI,2023-05-01,legal hallucination,"
            '"ChatGPT-generated fake legal citations were filed in federal court.",,'
            '"https://example.com/court-order | https://example.com/reuters-legal | '
            'https://example.com/stanford-analysis",ACCEPT,high,Strong primary support'
        ),
        (
            "2,inc-school-002,Example School District,"
            '2023-09-14,education failure,'
            '"A school chatbot gave families inaccurate enrollment guidance.",'
            "claim-missing-1,"
            '"https://example.com/district-statement | '
            "https://example.com/local-news | "
            'https://example.com/state-analysis | https://example.com/local-news",'
            "REVIEW,medium,Claim mapping should be ignored when missing"
        ),
        "",
    ]
)

INVALID_DATE_CSV = "\n".join(
    [
        (
            "ref_number,incident_id,company,incident_date,incident_topic,"
            "incident_description,mapped_claim,source_links,legitimacy_flag,"
            "confidence_level,notes"
        ),
        (
            "1,inc-openai-001,OpenAI,2023-02-30,legal hallucination,"
            '"ChatGPT-generated fake legal citations were filed in federal court.",,'
            '"https://example.com/court-order | https://example.com/reuters-legal | '
            'https://example.com/stanford-analysis",ACCEPT,high,'
        ),
        "",
    ]
)

TOO_FEW_SOURCES_CSV = "\n".join(
    [
        (
            "ref_number,incident_id,company,incident_date,incident_topic,"
            "incident_description,mapped_claim,source_links,legitimacy_flag,"
            "confidence_level,notes"
        ),
        (
            "1,inc-openai-001,OpenAI,2023-05-01,legal hallucination,"
            '"ChatGPT-generated fake legal citations were filed in federal court.",,'
            '"https://example.com/court-order | https://example.com/court-order | '
            'https://example.com/reuters-legal",ACCEPT,high,'
        ),
        "",
    ]
)


def test_parse_incidents_csv_text_extracts_distinct_sources_and_editorial_inputs(
) -> None:
    rows = parse_incidents_csv_text(VALID_IMPORT_CSV)

    assert len(rows) == 2
    assert rows[0].incident_id == "inc-openai-001"
    assert rows[0].legitimacy_flag == "ACCEPT"
    assert rows[0].confidence_level == "high"
    assert rows[1].source_links == [
        "https://example.com/district-statement",
        "https://example.com/local-news",
        "https://example.com/state-analysis",
    ]


def test_parse_incidents_csv_text_rejects_invalid_calendar_dates() -> None:
    with pytest.raises(IncidentImportValidationError) as exc_info:
        parse_incidents_csv_text(INVALID_DATE_CSV)

    assert "incident_date" in str(exc_info.value)
    assert "line 2" in str(exc_info.value)


def test_parse_incidents_csv_text_requires_three_distinct_sources() -> None:
    with pytest.raises(IncidentImportValidationError) as exc_info:
        parse_incidents_csv_text(TOO_FEW_SOURCES_CSV)

    assert "at least 3 distinct" in str(exc_info.value)


def test_import_incidents_csv_text_persists_legitimacy_metadata_and_translation(
) -> None:
    repository = InMemoryIncidentRepository()

    summary = import_incidents_csv_text(repository, VALID_IMPORT_CSV, dry_run=False)

    assert summary.validated == 2
    assert summary.inserted == 2
    assert summary.approved == 0
    assert summary.pending_review == 0
    assert summary.pending_llm_review == 2

    first_incident = next(
        incident
        for incident in repository.incidents.values()
        if incident["external_id"] == "inc-openai-001"
    )
    second_incident = next(
        incident
        for incident in repository.incidents.values()
        if incident["external_id"] == "inc-school-002"
    )

    assert first_incident["status"] == "pending_llm_review"
    assert first_incident["legitimacy_score"] is None
    assert first_incident["translation_status"] == "not_requested"
    assert first_incident["headline_en"] == first_incident["headline"]
    assert first_incident["headline_zh"] is None
    assert first_incident["matched_claim_id"] is None

    assert second_incident["status"] == "pending_llm_review"
    assert second_incident["translation_status"] == "not_requested"
    assert second_incident["matched_claim_id"] is None
    assert second_incident["source_validation_summary"] == (
        "Validated 3 distinct sources."
    )
    assert [source["source_url"] for source in second_incident["sources"]] == [
        "https://example.com/district-statement",
        "https://example.com/local-news",
        "https://example.com/state-analysis",
    ]


def test_import_incidents_csv_text_dry_run_validates_without_persisting() -> None:
    repository = InMemoryIncidentRepository()

    summary = import_incidents_csv_text(repository, VALID_IMPORT_CSV, dry_run=True)

    assert summary.validated == 2
    assert summary.inserted == 0
    assert repository.incidents == {}
