from __future__ import annotations

import pytest

from app.services.claim_import import (
    ClaimImportValidationError,
    import_claims_csv_text,
    parse_claims_csv_text,
)
from tests.support.fakes import InMemoryIncidentRepository

CLAIMS_WITH_SOURCES_CSV = "\n".join(
    [
        (
            "id,claimant_name,company_involved,original_claim,"
            "claim_date,claim_topic,status,primary_source_links,"
            "secondary_source_links,notes"
        ),
        (
            "claim-openai-001,OpenAI,OpenAI,"
            '"Our model will reduce repetitive support work.",'
            "2026-01-15,customer support,approved,"
            '"https://openai.com/blog/example-announcement | '
            'https://openai.com/newsroom/example",'
            '"https://www.reuters.com/example-openai-support",'
            "Claim pulled from launch post"
        ),
        "",
    ]
)
INVALID_URL_CSV = "\n".join(
    [
        (
            "claimant_name,company_involved,original_claim,"
            "claim_date,claim_topic,primary_source_links"
        ),
        (
            'OpenAI,OpenAI,"Our model will reduce repetitive support work.",'
            "2026-01-15,customer support,not-a-url"
        ),
        "",
    ]
)
IMPORT_CSV = "\n".join(
    [
        (
            "claimant_name,company_involved,original_claim,claim_date,claim_topic,"
            "primary_source_links,secondary_source_links,notes"
        ),
        (
            'OpenAI,OpenAI,"Our model will reduce repetitive support work.",'
            "2026-01-15,customer support,"
            "https://openai.com/blog/example-announcement,"
            "https://www.reuters.com/example-openai-support,"
            "Claim pulled from launch post"
        ),
        (
            "OpenAI,OpenAI,"
            '"Our model will reduce repetitive support work for '
            'enterprise support teams.",'
            "2026-02-12,customer support,"
            "https://openai.com/newsroom/example,,"
        ),
        "",
    ]
)
DRY_RUN_CSV = "\n".join(
    [
        "claimant_name,company_involved,original_claim,claim_date,claim_topic",
        (
            'OpenAI,OpenAI,"Our model will reduce repetitive support work.",'
            "2026-01-15,customer support"
        ),
        "",
    ]
)


def test_parse_claims_csv_text_extracts_pipe_separated_sources_and_notes() -> None:
    rows = parse_claims_csv_text(CLAIMS_WITH_SOURCES_CSV)

    assert len(rows) == 1
    assert rows[0].primary_source_links == [
        "https://openai.com/blog/example-announcement",
        "https://openai.com/newsroom/example",
    ]
    assert rows[0].secondary_source_links == [
        "https://www.reuters.com/example-openai-support",
    ]
    assert rows[0].notes == "Claim pulled from launch post"


def test_parse_claims_csv_text_rejects_invalid_urls() -> None:
    with pytest.raises(ClaimImportValidationError) as exc_info:
        parse_claims_csv_text(INVALID_URL_CSV)

    assert "line 2" in str(exc_info.value)
    assert "valid http:// or https:// URL" in str(exc_info.value)


def test_import_claims_csv_text_persists_generated_ids_and_sources() -> None:
    repository = InMemoryIncidentRepository()

    summary = import_claims_csv_text(
        repository,
        IMPORT_CSV,
        dry_run=False,
    )

    assert summary.inserted == 2
    assert sorted(repository.claims) == ["claim-openai-001", "claim-openai-002"]
    assert repository.claims["claim-openai-001"]["status"] == "approved"
    assert (
        repository.claims["claim-openai-001"]["notes"]
        == "Claim pulled from launch post"
    )
    assert repository.claim_sources["claim-openai-001"] == [
        {
            "source_url": "https://openai.com/blog/example-announcement",
            "source_kind": "primary",
            "display_order": 0,
        },
        {
            "source_url": "https://www.reuters.com/example-openai-support",
            "source_kind": "secondary",
            "display_order": 0,
        },
    ]


def test_import_claims_csv_text_dry_run_validates_without_persisting() -> None:
    repository = InMemoryIncidentRepository()

    summary = import_claims_csv_text(
        repository,
        DRY_RUN_CSV,
        dry_run=True,
    )

    assert summary.inserted == 0
    assert summary.validated == 1
    assert repository.claims == {}
