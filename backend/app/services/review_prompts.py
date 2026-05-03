"""LLM prompt construction and response parsing for incident review.

Extracted from incident_review.py to separate the LLM protocol layer
(prompt templates, structured output parsing, response normalisation)
from the orchestration layer (batch submission, decision logic, escalation).
"""

from __future__ import annotations

import json
import textwrap
from typing import Any

from app.core.incident_taxonomy import (
    INCIDENT_CATEGORY_TAXONOMY,
    normalize_incident_categories,
)
from app.core.config import get_settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_settings = get_settings()

REVIEW_MAX_OUTPUT_TOKENS = _settings.review_max_output_tokens
REVIEW_RESPONSE_PARSE_MAX_ATTEMPTS = _settings.review_response_parse_max_attempts
FORENSIC_MIN_WORD_COUNTS = {
    "what_happened_en": _settings.forensic_min_word_count_what_happened,
    "ai_failure_point_en": _settings.forensic_min_word_count_ai_failure_point,
    "why_it_matters_en": _settings.forensic_min_word_count_why_it_matters,
}
QUALITATIVE_SEVERITY_CONFIDENCE_SCORES = {
    "very low": 0.1,
    "low": 0.25,
    "medium": 0.6,
    "moderate": 0.6,
    "high": 0.9,
    "very high": 0.98,
}


class ReviewResponseParseError(RuntimeError):
    """Raised when the LLM response cannot be parsed into a review result."""


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def build_review_messages(incident: dict[str, Any]) -> list[dict[str, str]]:
    """Build the chat messages list for an incident review LLM call."""
    return [
        {
            "role": "system",
            "content": textwrap.dedent(f"""\
                You are an editorial reviewer for an AI incident database.
                
                # INSTRUCTIONS
                - Evaluate the provided incident and determine if it is a legitimate AI failure.
                - Choose one or more categories from the approved taxonomy only.
                - Write substantive narrative sections for the forensic fields.
                
                # FORENSIC NARRATIVE REQUIREMENTS
                - `what_happened_en`: at least {FORENSIC_MIN_WORD_COUNTS['what_happened_en']} words
                - `ai_failure_point_en`: at least {FORENSIC_MIN_WORD_COUNTS['ai_failure_point_en']} words
                - `why_it_matters_en`: at least {FORENSIC_MIN_WORD_COUNTS['why_it_matters_en']} words
                
                # EVALUATION RULES
                - `score`: A float between 0.0 and 1.0 indicating your confidence that the incident is a legitimate, real-world AI failure (0.0=fake/spam/unrelated, 1.0=definitely legitimate).
                - `needs_escalation`: Set to `true` when source quality is weak, date or company attribution remains unresolved, severity is materially unclear, evidence conflicts, or you believe human review or a stronger second pass is required.
                - `severity_confidence`: A float between 0.0 and 1.0 (not a word or label).
                
                # SEVERITY RUBRIC (Impact-First)
                1 = Minor, quickly reversible, no meaningful external harm.
                2 = Real but limited impact, localized and reversible.
                3 = Clear operational or business impact requiring rollback or manual intervention.
                4 = Major real-world or sensitive-domain harm involving privacy, legal, regulatory, financial, or broad safety consequences. (Safety-critical incidents start at 4 unless clearly minor. Broad privacy breach, major legal/regulatory action, or major financial harm is at least 4.)
                5 = Catastrophic irreversible harm or major systemic safety failure. (Serious injury or death is 5.)
                *Note: Near misses in safety-critical systems may raise severity by one level, but do not replace actual harm.*
                
                # OUTPUT FORMAT
                Return valid JSON only. Use EXACTLY this JSON shape:
                {{
                    "verdict": "approved|rejected|pending_review",
                    "score": 0.0,
                    "reasoning": "...",
                    "source_quality_summary": "...",
                    "date_confirmed": true,
                    "company_confirmed": true,
                    "headline_en": "...",
                    "reality_summary_en": "...",
                    "incident_summary_en": "...",
                    "what_happened_en": "...",
                    "ai_failure_point_en": "...",
                    "why_it_matters_en": "...",
                    "evidence_summary_en": "...",
                    "categories": ["Hallucinations"],
                    "suggested_severity_score": 3,
                    "severity_confidence": 0.8,
                    "severity_reasoning": "...",
                    "severity_flags": ["..."],
                    "needs_escalation": false
                }}
            """),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "incident_id": incident["id"],
                    "external_id": incident.get("external_id"),
                    "company": incident["company_involved"],
                    "incident_topic": incident.get("incident_topic"),
                    "approved_categories": list(INCIDENT_CATEGORY_TAXONOMY),
                    "incident_date": incident["date_logged"],
                    "headline": incident["headline"],
                    "reality_summary": incident["reality_summary"],
                    "editorial_input": {
                        "legitimacy_flag": incident.get("legitimacy_flag"),
                        "confidence_level": incident.get("confidence_level"),
                        "import_notes": incident.get("import_notes"),
                    },
                    "sources": [
                        {
                            "source_url": source["source_url"],
                            "canonical_url": source.get("canonical_url"),
                            "fetch_status": source.get("fetch_status"),
                            "http_status": source.get("http_status"),
                            "evidence_text": source.get("evidence_text"),
                        }
                        for source in incident.get("sources", [])
                    ],
                }
            ),
        },
    ]


def build_review_response_format(*, base_url: str | None = None) -> dict[str, Any]:
    """Return the response_format config for the review LLM call."""
    del base_url
    return {"type": "json_object"}


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def parse_review_result(
    *,
    incident_id: str,
    model: str,
    content: str,
) -> "IncidentReviewResult":
    """Parse raw JSON content string into an IncidentReviewResult."""
    from app.services.incident_review import IncidentReviewResult

    payload = json.loads(content)
    categories, invalid_categories = _parse_review_categories(payload.get("categories"))
    severity_confidence, invalid_severity_confidence = (
        _parse_optional_severity_confidence(payload.get("severity_confidence"))
    )
    incident_summary_en = _parse_required_review_text_field(
        payload,
        "incident_summary_en",
    )
    what_happened_en = _parse_required_review_text_field(
        payload,
        "what_happened_en",
        min_words=FORENSIC_MIN_WORD_COUNTS["what_happened_en"],
    )
    ai_failure_point_en = _parse_required_review_text_field(
        payload,
        "ai_failure_point_en",
        min_words=FORENSIC_MIN_WORD_COUNTS["ai_failure_point_en"],
    )
    why_it_matters_en = _parse_required_review_text_field(
        payload,
        "why_it_matters_en",
        min_words=FORENSIC_MIN_WORD_COUNTS["why_it_matters_en"],
    )
    evidence_summary_en = _parse_required_review_text_field(
        payload,
        "evidence_summary_en",
    )
    return IncidentReviewResult(
        incident_id=incident_id,
        verdict=payload["verdict"],
        score=float(payload["score"]),
        reasoning=payload["reasoning"],
        source_quality_summary=payload["source_quality_summary"],
        date_confirmed=bool(payload["date_confirmed"]),
        company_confirmed=bool(payload["company_confirmed"]),
        headline_en=payload["headline_en"],
        reality_summary_en=payload["reality_summary_en"],
        incident_summary_en=incident_summary_en,
        what_happened_en=what_happened_en,
        ai_failure_point_en=ai_failure_point_en,
        why_it_matters_en=why_it_matters_en,
        evidence_summary_en=evidence_summary_en,
        categories=categories,
        suggested_severity_score=(
            int(payload["suggested_severity_score"])
            if payload.get("suggested_severity_score") is not None
            else None
        ),
        severity_confidence=severity_confidence,
        severity_reasoning=payload.get("severity_reasoning"),
        severity_flags=[
            str(flag) for flag in payload.get("severity_flags", []) if str(flag)
        ],
        needs_escalation=(
            bool(payload["needs_escalation"])
            or invalid_categories
            or invalid_severity_confidence
        ),
        reviewed_model=model,
    )


def parse_review_result_from_provider_payload(
    *,
    incident_id: str,
    payload: Any,
) -> "IncidentReviewResult":
    """Extract and parse a review result from an OpenAI-compatible response."""
    try:
        if isinstance(payload, dict):
            model = payload["model"]
            content = payload["choices"][0]["message"]["content"]
        else:
            model = payload.model
            content = payload.choices[0].message.content
    except (AttributeError, KeyError, IndexError, TypeError) as exc:
        raise ReviewResponseParseError(
            "Review provider returned an unexpected response shape"
        ) from exc
    if not isinstance(content, str):
        raise ReviewResponseParseError(
            "Expected structured review content from the review provider"
        )
    try:
        return parse_review_result(
            incident_id=incident_id,
            model=model,
            content=content,
        )
    except json.JSONDecodeError as exc:
        raise ReviewResponseParseError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Internal parsing helpers
# ---------------------------------------------------------------------------

def _parse_review_categories(value: Any) -> tuple[list[str] | None, bool]:
    if not isinstance(value, list):
        return None, True
    categories = normalize_incident_categories(
        [str(category) for category in value if isinstance(category, str)]
    )
    if len(categories) != len(value) or not categories:
        return None, True
    return categories, False


def _parse_required_review_text_field(
    payload: dict[str, Any],
    field_name: str,
    *,
    min_words: int = 0,
) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str):
        raise ReviewResponseParseError(
            f"Expected {field_name} to be a string in the structured review output"
        )
    normalized = " ".join(value.split())
    if not normalized:
        raise ReviewResponseParseError(
            f"Expected {field_name} to be a non-empty string in the structured review output"
        )
    if min_words > 0 and _count_words(normalized) < min_words:
        raise ReviewResponseParseError(
            f"Expected {field_name} to contain at least {min_words} words"
        )
    return normalized


def _count_words(value: str) -> int:
    return len([part for part in value.split(" ") if part])


def _parse_optional_severity_confidence(value: Any) -> tuple[float | None, bool]:
    if value is None:
        return None, False
    if isinstance(value, bool):
        return None, True
    if isinstance(value, (int, float)):
        return _normalize_confidence_number(float(value))
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None, False
        normalized = raw.lower().replace("_", " ").replace("-", " ")
        if normalized in QUALITATIVE_SEVERITY_CONFIDENCE_SCORES:
            return QUALITATIVE_SEVERITY_CONFIDENCE_SCORES[normalized], False
        if raw.endswith("%"):
            try:
                return _normalize_confidence_number(float(raw[:-1]) / 100.0)
            except ValueError:
                return None, True
        try:
            return _normalize_confidence_number(float(raw))
        except ValueError:
            return None, True
    return None, True


def _normalize_confidence_number(value: float) -> tuple[float | None, bool]:
    if 0.0 <= value <= 1.0:
        return value, False
    if 1.0 < value <= 100.0:
        return value / 100.0, False
    return None, True
