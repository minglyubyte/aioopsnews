from __future__ import annotations

import json

import httpx

from app.services.incident_translation import DeepSeekIncidentTranslationClient


def test_deepseek_translation_client_tolerates_missing_optional_analysis_keys(
    monkeypatch,
) -> None:
    def fake_post(*args: object, **kwargs: object) -> httpx.Response:
        del args, kwargs
        request = httpx.Request("POST", "https://deepseek.example/v1/chat/completions")
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "company_involved_zh": "公司",
                                    "headline_zh": "标题",
                                    "reality_summary_zh": "摘要",
                                    "incident_summary_zh": "事件摘要",
                                    "what_happened_zh": "发生了什么",
                                    "ai_failure_point_zh": "失败点",
                                    "why_it_matters_zh": "重要性",
                                    "legitimacy_reasoning_zh": "理由",
                                    "source_validation_summary_zh": "来源摘要",
                                }
                            )
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr("app.services.incident_translation.httpx.post", fake_post)

    translation = DeepSeekIncidentTranslationClient(
        api_key="test-key",
        base_url="https://deepseek.example/v1",
    ).translate(
        company_involved_en="Waymo",
        headline_en="Headline",
        reality_summary_en="Summary",
        incident_summary_en="Incident summary",
        what_happened_en="What happened",
        ai_failure_point_en="Failure point",
        why_it_matters_en="Why it matters",
        evidence_summary_en="Evidence summary",
        legitimacy_reasoning_en="Reasoning",
        source_validation_summary_en="Source summary",
    )

    assert translation.status == "completed"
    assert translation.evidence_summary_zh == ""


def test_deepseek_translation_client_tolerates_missing_reasoning_keys(
    monkeypatch,
) -> None:
    def fake_post(*args: object, **kwargs: object) -> httpx.Response:
        del args, kwargs
        request = httpx.Request("POST", "https://deepseek.example/v1/chat/completions")
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "company_involved_zh": "公司",
                                    "headline_zh": "标题",
                                }
                            )
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr("app.services.incident_translation.httpx.post", fake_post)

    translation = DeepSeekIncidentTranslationClient(
        api_key="test-key",
        base_url="https://deepseek.example/v1",
    ).translate(
        company_involved_en="Waymo",
        headline_en="Headline",
        reality_summary_en="Summary",
        legitimacy_reasoning_en="Reasoning",
        source_validation_summary_en="Source summary",
    )

    assert translation.status == "completed"
    assert translation.reality_summary_zh == ""
    assert translation.legitimacy_reasoning_zh == ""
    assert translation.source_validation_summary_zh == ""
