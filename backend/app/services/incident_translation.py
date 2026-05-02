from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class IncidentTranslation:
    headline_zh: str
    reality_summary_zh: str
    legitimacy_reasoning_zh: str
    source_validation_summary_zh: str
    company_involved_zh: str = ""
    incident_summary_zh: str = ""
    what_happened_zh: str = ""
    ai_failure_point_zh: str = ""
    why_it_matters_zh: str = ""
    evidence_summary_zh: str = ""
    status: str = "completed"


class IncidentTranslationClient(Protocol):
    def translate(
        self,
        *,
        headline_en: str,
        reality_summary_en: str,
        legitimacy_reasoning_en: str,
        source_validation_summary_en: str,
        company_involved_en: str = "",
        incident_summary_en: str = "",
        what_happened_en: str = "",
        ai_failure_point_en: str = "",
        why_it_matters_en: str = "",
        evidence_summary_en: str = "",
    ) -> IncidentTranslation: ...


class DeepSeekIncidentTranslationClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "deepseek-v4-flash",
        base_url: str = "https://api.deepseek.com",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def translate(
        self,
        *,
        headline_en: str,
        reality_summary_en: str,
        legitimacy_reasoning_en: str,
        source_validation_summary_en: str,
        company_involved_en: str = "",
        incident_summary_en: str = "",
        what_happened_en: str = "",
        ai_failure_point_en: str = "",
        why_it_matters_en: str = "",
        evidence_summary_en: str = "",
    ) -> IncidentTranslation:
        response = httpx.post(
            f"{self._base_url}/chat/completions",
            headers=self._headers,
            json={
                "model": self._model,
                "thinking": {"type": "disabled"},
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Translate the incident company name, headline, and "
                            "reader-facing analysis into simplified Chinese. "
                            "Return JSON only with keys company_involved_zh, "
                            "headline_zh, reality_summary_zh, "
                            "incident_summary_zh, what_happened_zh, "
                            "ai_failure_point_zh, why_it_matters_zh, "
                            "evidence_summary_zh, "
                            "legitimacy_reasoning_zh, and "
                            "source_validation_summary_zh."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "company_involved_en": company_involved_en,
                                "headline_en": headline_en,
                                "reality_summary_en": reality_summary_en,
                                "incident_summary_en": incident_summary_en,
                                "what_happened_en": what_happened_en,
                                "ai_failure_point_en": ai_failure_point_en,
                                "why_it_matters_en": why_it_matters_en,
                                "evidence_summary_en": evidence_summary_en,
                                "legitimacy_reasoning_en": legitimacy_reasoning_en,
                                "source_validation_summary_en": (
                                    source_validation_summary_en
                                ),
                            }
                        ),
                    },
                ],
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return IncidentTranslation(
            company_involved_zh=parsed["company_involved_zh"],
            headline_zh=parsed["headline_zh"],
            reality_summary_zh=parsed["reality_summary_zh"],
            incident_summary_zh=parsed["incident_summary_zh"],
            what_happened_zh=parsed["what_happened_zh"],
            ai_failure_point_zh=parsed["ai_failure_point_zh"],
            why_it_matters_zh=parsed["why_it_matters_zh"],
            evidence_summary_zh=parsed["evidence_summary_zh"],
            legitimacy_reasoning_zh=parsed["legitimacy_reasoning_zh"],
            source_validation_summary_zh=parsed["source_validation_summary_zh"],
            status="completed",
        )


class DisabledIncidentTranslationClient:
    def translate(
        self,
        *,
        headline_en: str,
        reality_summary_en: str,
        legitimacy_reasoning_en: str,
        source_validation_summary_en: str,
        company_involved_en: str = "",
        incident_summary_en: str = "",
        what_happened_en: str = "",
        ai_failure_point_en: str = "",
        why_it_matters_en: str = "",
        evidence_summary_en: str = "",
    ) -> IncidentTranslation:
        raise RuntimeError(
            "DeepSeek translation is not configured. Set DEEPSEEK_API_KEY "
            "or inject a translation client."
        )


def translate_incident_copy(
    *,
    headline_en: str,
    reality_summary_en: str,
    legitimacy_reasoning_en: str,
    source_validation_summary_en: str,
    client: IncidentTranslationClient,
    company_involved_en: str = "",
    incident_summary_en: str = "",
    what_happened_en: str = "",
    ai_failure_point_en: str = "",
    why_it_matters_en: str = "",
    evidence_summary_en: str = "",
) -> IncidentTranslation:
    payload = {
        "company_involved_en": company_involved_en,
        "headline_en": headline_en,
        "reality_summary_en": reality_summary_en,
        "legitimacy_reasoning_en": legitimacy_reasoning_en,
        "source_validation_summary_en": source_validation_summary_en,
    }
    if any(
        (
            incident_summary_en,
            what_happened_en,
            ai_failure_point_en,
            why_it_matters_en,
            evidence_summary_en,
        )
    ):
        payload.update(
            {
                "incident_summary_en": incident_summary_en,
                "what_happened_en": what_happened_en,
                "ai_failure_point_en": ai_failure_point_en,
                "why_it_matters_en": why_it_matters_en,
                "evidence_summary_en": evidence_summary_en,
            }
        )
    return client.translate(**payload)
