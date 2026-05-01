from __future__ import annotations

from app.services.case_search_prompt import case_search_prompt


def test_case_search_prompt_includes_required_csv_contract() -> None:
    assert case_search_prompt
    assert (
        "ref_number,incident_id,company,incident_date,incident_topic,"
        "incident_description,mapped_claim,source_links,legitimacy_flag,"
        "confidence_level,notes"
    ) in case_search_prompt
    assert "calendar year 2023 only" in case_search_prompt
    assert "Return exactly one fenced csv block and nothing else." in (
        case_search_prompt
    )


def test_case_search_prompt_requires_stricter_source_quality_rules() -> None:
    assert "Primary sources:" in case_search_prompt
    assert "Second-hand sources:" in case_search_prompt
    assert "require at least 3 distinct URLs total" in case_search_prompt
    assert (
        "require at least 1 primary source whenever a defensible primary "
        "source should exist"
    ) in case_search_prompt
    assert (
        "marked REVIEW, and the notes field explicitly says the stronger "
        "primary source was not found"
    ) in case_search_prompt
