from __future__ import annotations

import pytest

from app.services.incident_import import (
    IncidentImportValidationError,
    import_incidents_csv_text,
    parse_incidents_csv_text,
)
from tests.support.fakes import InMemoryIncidentRepository
from tests.support.incident_csv_fixtures import VALID_IMPORT_CSV

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


def test_in_memory_repository_accepts_forensic_review_and_translation_kwargs() -> None:
    repository = InMemoryIncidentRepository(
        incidents=[
            {
                "id": "incident-1",
                "headline": "Original headline",
                "headline_en": "Original headline",
                "headline_zh": None,
                "date_logged": "2026-05-01",
                "company_involved": "OpenAI",
                "incident_topic": "model governance",
                "claimant_name": None,
                "categories": [],
                "severity_score": 2,
                "reality_summary": "Original summary",
                "reality_summary_en": "Original summary",
                "reality_summary_zh": None,
                "status": "pending_review",
                "translation_status": "not_requested",
                "sources": [],
            }
        ]
    )

    reviewed = repository.apply_incident_review_result(
        incident_id="incident-1",
        status="approved",
        legitimacy_score=0.95,
        legitimacy_label="approved",
        legitimacy_reasoning="Strong evidence.",
        source_validation_summary="Validated sources.",
        headline_en="Reviewed headline",
        reality_summary_en="Reviewed summary",
        categories=["Model Governance"],
        severity_score=3,
        suggested_severity_score=3,
        severity_confidence=0.9,
        severity_reasoning="High confidence.",
        severity_flags=[],
        severity_model="deepseek-v4-flash",
        severity_decision_source="llm",
        severity_suggested_at="2026-05-01T12:00:00+00:00",
        review_model="deepseek-v4-flash",
        review_batch_id="batch-1",
        reviewed_at="2026-05-01T12:01:00+00:00",
        incident_summary_en="Summary.",
        what_happened_en="What happened.",
        ai_failure_point_en="Failure point.",
        why_it_matters_en="Importance.",
        evidence_summary_en="Evidence summary.",
    )
    translated = repository.update_incident_translation(
        incident_id="incident-1",
        company_involved_zh="开放人工智能",
        headline_zh="审核后标题",
        reality_summary_zh="审核后摘要",
        legitimacy_reasoning_zh="证据充分。",
        source_validation_summary_zh="来源已核实。",
        translation_status="completed",
        translated_at="2026-05-01T12:02:00+00:00",
        incident_summary_zh="摘要。",
        what_happened_zh="发生了什么。",
        ai_failure_point_zh="失败点。",
        why_it_matters_zh="重要性。",
        evidence_summary_zh="证据摘要。",
    )

    assert reviewed is not None
    assert translated is not None
    assert repository.incidents["incident-1"]["incident_summary_en"] == "Summary."
    assert repository.incidents["incident-1"]["what_happened_en"] == "What happened."
    assert repository.incidents["incident-1"]["ai_failure_point_en"] == "Failure point."
    assert repository.incidents["incident-1"]["why_it_matters_en"] == "Importance."
    assert (
        repository.incidents["incident-1"]["evidence_summary_en"]
        == "Evidence summary."
    )
    assert repository.incidents["incident-1"]["incident_summary_zh"] == "摘要。"
    assert repository.incidents["incident-1"]["what_happened_zh"] == "发生了什么。"
    assert repository.incidents["incident-1"]["ai_failure_point_zh"] == "失败点。"
    assert repository.incidents["incident-1"]["why_it_matters_zh"] == "重要性。"
    assert repository.incidents["incident-1"]["evidence_summary_zh"] == "证据摘要。"
