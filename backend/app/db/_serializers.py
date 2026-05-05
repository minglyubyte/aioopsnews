"""Shared row-to-dict serialization helpers for incident repository data.

Every read method in PostgresIncidentRepository previously maintained its
own inline dict-literal to convert a database row into a Python dictionary.
This module centralises those mappings so that field additions/renames only
require a single change.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.incident_metadata import (
    DEFAULT_EVIDENCE_TIER,
    DEFAULT_PUBLICATION_TRACK,
    DEFAULT_SOURCE_FAMILY,
    DEFAULT_VERIFICATION_SUMMARY,
)


# ---------------------------------------------------------------------------
# Low-level field parsers
# ---------------------------------------------------------------------------

def parse_text_array(value: str | None) -> list[str]:
    """Parse a JSON text array stored in a text column."""
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item)]


def parse_optional_json_object(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def sanitize_reader_text(value: Any) -> str | None:
    """Strip whitespace from a reader-facing text field; return *None* if empty."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# ---------------------------------------------------------------------------
# Shared base field extractors
# ---------------------------------------------------------------------------

def _base_incident_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Fields common to virtually every incident serialization."""
    return {
        "id": row["id"],
        "headline": row["headline"],
        "headline_en": row.get("headline_en"),
        "headline_zh": row.get("headline_zh"),
        "date_logged": row["date_logged"],
        "company_involved": row["company_involved"],
        "incident_topic": row.get("incident_topic"),
        "claimant_name": row.get("claimant_name"),
        "categories": json.loads(row["categories"]),
        "severity_score": row["severity_score"],
        "reality_summary": row["reality_summary"],
        "reality_summary_en": row.get("reality_summary_en"),
        "reality_summary_zh": row.get("reality_summary_zh"),
        "status": row["status"],
        **_dual_track_fields(row),
    }


def _dual_track_fields(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "publication_track": row.get("publication_track")
        or DEFAULT_PUBLICATION_TRACK,
        "evidence_tier": row.get("evidence_tier") or DEFAULT_EVIDENCE_TIER,
        "source_family": row.get("source_family") or DEFAULT_SOURCE_FAMILY,
        "verification_summary": row.get("verification_summary")
        or DEFAULT_VERIFICATION_SUMMARY,
    }


def _review_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Fields that carry review/legitimacy metadata."""
    return {
        "review_notes": row.get("review_notes"),
        "legitimacy_score": row.get("legitimacy_score"),
        "legitimacy_label": row.get("legitimacy_label"),
        "severity_confidence": row.get("severity_confidence"),
        "severity_reasoning": row.get("severity_reasoning"),
        "severity_flags": parse_text_array(row.get("severity_flags")),
        "severity_model": row.get("severity_model"),
        "severity_decision_source": row.get("severity_decision_source"),
        "legitimacy_reasoning": row.get("legitimacy_reasoning"),
        "source_validation_summary": row.get("source_validation_summary"),
    }


def _duplicate_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Fields related to duplicate detection."""
    return {
        "duplicate_status": row.get("duplicate_status"),
        "duplicate_of_incident_id": row.get("duplicate_of_incident_id"),
        "canonical_incident_id": row.get("canonical_incident_id"),
    }


def _batch_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Fields related to LLM review batching."""
    return {
        "translation_status": row.get("translation_status"),
        "review_batch_id": row.get("review_batch_id"),
        "review_model": row.get("review_model"),
    }


# ---------------------------------------------------------------------------
# Public serializers (called by repository read methods)
# ---------------------------------------------------------------------------

def serialize_review_queue_row(
    row: dict[str, Any],
    *,
    sources: list[dict[str, Any]],
    duplicate_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Serialize a row for the admin review queue (`list_review_queue`)."""
    return {
        **_base_incident_fields(row),
        "suggested_severity_score": row.get("suggested_severity_score"),
        "matched_claim_id": row.get("matched_claim_id"),
        "claim_match_confidence": row.get("claim_match_confidence"),
        "company_involved_zh": row.get("company_involved_zh"),
        **_review_fields(row),
        "legitimacy_reasoning_zh": row.get("legitimacy_reasoning_zh"),
        "source_validation_summary_zh": row.get("source_validation_summary_zh"),
        **_batch_fields(row),
        **_duplicate_fields(row),
        "duplicate_candidates": duplicate_candidates,
        "sources": sources,
        "incident_summary_en": row.get("incident_summary_en"),
        "incident_summary_zh": row.get("incident_summary_zh"),
        "what_happened_en": row.get("what_happened_en"),
        "what_happened_zh": row.get("what_happened_zh"),
        "ai_failure_point_en": row.get("ai_failure_point_en"),
        "ai_failure_point_zh": row.get("ai_failure_point_zh"),
        "why_it_matters_en": row.get("why_it_matters_en"),
        "why_it_matters_zh": row.get("why_it_matters_zh"),
        "evidence_summary_en": row.get("evidence_summary_en"),
        "evidence_summary_zh": row.get("evidence_summary_zh"),
        "analysis": {
            "incident_summary_en": row.get("incident_summary_en"),
            "incident_summary_zh": row.get("incident_summary_zh"),
            "what_happened_en": row.get("what_happened_en"),
            "what_happened_zh": row.get("what_happened_zh"),
            "ai_failure_point_en": row.get("ai_failure_point_en"),
            "ai_failure_point_zh": row.get("ai_failure_point_zh"),
            "why_it_matters_en": row.get("why_it_matters_en"),
            "why_it_matters_zh": row.get("why_it_matters_zh"),
            "evidence_summary_en": row.get("evidence_summary_en"),
            "evidence_summary_zh": row.get("evidence_summary_zh"),
        },
    }


def serialize_llm_pending_row(
    row: dict[str, Any],
    *,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """Serialize a row for LLM pending review (`list_incidents_pending_llm_review`)."""
    return {
        **_base_incident_fields(row),
        "external_id": row.get("external_id"),
        "suggested_severity_score": row.get("suggested_severity_score"),
        "review_notes": row.get("review_notes"),
        "severity_confidence": row.get("severity_confidence"),
        "severity_reasoning": row.get("severity_reasoning"),
        "severity_flags": parse_text_array(row.get("severity_flags")),
        "severity_model": row.get("severity_model"),
        "severity_decision_source": row.get("severity_decision_source"),
        "legitimacy_flag": row.get("legitimacy_flag"),
        "confidence_level": row.get("confidence_level"),
        "import_notes": row.get("import_notes"),
        **_batch_fields(row),
        "sources": sources,
        **_duplicate_fields(row),
        "embedding_model": row.get("embedding_model"),
        "embedding_vector": json.loads(row["embedding_vector"])
        if row.get("embedding_vector")
        else None,
    }


def serialize_internal_incident(
    row: dict[str, Any],
    *,
    sources: list[dict[str, Any]],
    duplicate_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Serialize a row for `get_incident` (internal, full detail)."""
    return {
        **_base_incident_fields(row),
        "external_id": row.get("external_id"),
        "suggested_severity_score": row.get("suggested_severity_score"),
        **_review_fields(row),
        "legitimacy_flag": row.get("legitimacy_flag"),
        "confidence_level": row.get("confidence_level"),
        "import_notes": row.get("import_notes"),
        **_batch_fields(row),
        **_duplicate_fields(row),
        "embedding_model": row.get("embedding_model"),
        "embedding_vector": json.loads(row["embedding_vector"])
        if row.get("embedding_vector")
        else None,
        "duplicate_candidates": duplicate_candidates,
        "sources": sources,
    }


def serialize_duplicate_search_row(
    row: dict[str, Any],
    *,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """Serialize a row for `list_duplicate_search_pool`."""
    return {
        **_base_incident_fields(row),
        "external_id": row.get("external_id"),
        **_review_fields(row),
        "legitimacy_flag": row.get("legitimacy_flag"),
        "confidence_level": row.get("confidence_level"),
        "import_notes": row.get("import_notes"),
        **_batch_fields(row),
        **_duplicate_fields(row),
        "embedding_model": row.get("embedding_model"),
        "embedding_vector": json.loads(row["embedding_vector"])
        if row.get("embedding_vector")
        else None,
        "sources": sources,
    }


def serialize_review_result_row(
    row: dict[str, Any],
    *,
    sources: list[dict[str, Any]],
    duplicate_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Serialize a row after `apply_incident_review_result`."""
    return {
        **_base_incident_fields(row),
        "suggested_severity_score": row.get("suggested_severity_score"),
        "matched_claim_id": row.get("matched_claim_id"),
        "claim_match_confidence": row.get("claim_match_confidence"),
        **_review_fields(row),
        **_batch_fields(row),
        **_duplicate_fields(row),
        "duplicate_candidates": duplicate_candidates,
        "sources": sources,
        "incident_summary_en": row.get("incident_summary_en"),
        "incident_summary_zh": row.get("incident_summary_zh"),
        "what_happened_en": row.get("what_happened_en"),
        "what_happened_zh": row.get("what_happened_zh"),
        "ai_failure_point_en": row.get("ai_failure_point_en"),
        "ai_failure_point_zh": row.get("ai_failure_point_zh"),
        "why_it_matters_en": row.get("why_it_matters_en"),
        "why_it_matters_zh": row.get("why_it_matters_zh"),
        "evidence_summary_en": row.get("evidence_summary_en"),
        "evidence_summary_zh": row.get("evidence_summary_zh"),
        "analysis": {
            "incident_summary_en": row.get("incident_summary_en"),
            "incident_summary_zh": row.get("incident_summary_zh"),
            "what_happened_en": row.get("what_happened_en"),
            "what_happened_zh": row.get("what_happened_zh"),
            "ai_failure_point_en": row.get("ai_failure_point_en"),
            "ai_failure_point_zh": row.get("ai_failure_point_zh"),
            "why_it_matters_en": row.get("why_it_matters_en"),
            "why_it_matters_zh": row.get("why_it_matters_zh"),
            "evidence_summary_en": row.get("evidence_summary_en"),
            "evidence_summary_zh": row.get("evidence_summary_zh"),
        },
    }


def serialize_translation_result_row(
    row: dict[str, Any],
    *,
    sources: list[dict[str, Any]],
    duplicate_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Serialize a row after `update_incident_translation`."""
    return {
        **_base_incident_fields(row),
        "company_involved_zh": row.get("company_involved_zh"),
        "suggested_severity_score": row.get("suggested_severity_score"),
        "matched_claim_id": row.get("matched_claim_id"),
        "claim_match_confidence": row.get("claim_match_confidence"),
        **_review_fields(row),
        "legitimacy_reasoning_zh": row.get("legitimacy_reasoning_zh"),
        "source_validation_summary_zh": row.get("source_validation_summary_zh"),
        **_batch_fields(row),
        **_duplicate_fields(row),
        "duplicate_candidates": duplicate_candidates,
        "sources": sources,
        "incident_summary_en": row.get("incident_summary_en"),
        "incident_summary_zh": row.get("incident_summary_zh"),
        "what_happened_en": row.get("what_happened_en"),
        "what_happened_zh": row.get("what_happened_zh"),
        "ai_failure_point_en": row.get("ai_failure_point_en"),
        "ai_failure_point_zh": row.get("ai_failure_point_zh"),
        "why_it_matters_en": row.get("why_it_matters_en"),
        "why_it_matters_zh": row.get("why_it_matters_zh"),
        "evidence_summary_en": row.get("evidence_summary_en"),
        "evidence_summary_zh": row.get("evidence_summary_zh"),
        "analysis": {
            "incident_summary_en": row.get("incident_summary_en"),
            "incident_summary_zh": row.get("incident_summary_zh"),
            "what_happened_en": row.get("what_happened_en"),
            "what_happened_zh": row.get("what_happened_zh"),
            "ai_failure_point_en": row.get("ai_failure_point_en"),
            "ai_failure_point_zh": row.get("ai_failure_point_zh"),
            "why_it_matters_en": row.get("why_it_matters_en"),
            "why_it_matters_zh": row.get("why_it_matters_zh"),
            "evidence_summary_en": row.get("evidence_summary_en"),
            "evidence_summary_zh": row.get("evidence_summary_zh"),
        },
    }


# ---------------------------------------------------------------------------
# Source helpers
# ---------------------------------------------------------------------------

def serialize_source_row(row: dict[str, Any]) -> dict[str, Any]:
    """Serialize a single incident_sources row."""
    return {
        "id": row["id"],
        "source_url": row["source_url"],
        "canonical_url": row.get("canonical_url"),
        "source_type": row["source_type"],
        "publisher": row["publisher"],
        "title": row["title"],
        "fetch_status": row.get("fetch_status"),
        "http_status": row.get("http_status"),
        "evidence_text": row.get("evidence_text"),
        "fetch_error": row.get("fetch_error"),
        "source_origin": row.get("source_origin"),
        "source_registry_key": row.get("source_registry_key"),
        "raw_source_payload": parse_optional_json_object(
            row.get("raw_source_payload")
        ),
    }


def group_sources_by_incident(
    source_rows: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group source rows by their incident_id, serializing each row."""
    from collections import defaultdict

    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        result[row["incident_id"]].append(serialize_source_row(row))
    return result


def serialize_duplicate_candidate_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_incident_id": row["candidate_incident_id"],
        "embedding_score": row["embedding_score"],
        "llm_verdict": row["llm_verdict"],
        "confidence": row["confidence"],
        "reasoning": row["reasoning"],
        "status": row["status"],
    }


# ---------------------------------------------------------------------------
# Public detail / claim serializers (used by get_public_incident)
# ---------------------------------------------------------------------------

def build_public_claim_payload(
    row: dict[str, Any],
    *,
    match_threshold: float,
) -> dict[str, Any] | None:
    """Build the matched_claim payload for a public incident, or None."""
    if row["claim_id"] is None:
        return None
    if row["claim_status"] != "approved":
        return None
    if row["claim_match_confidence"] is None:
        return None
    if row["claim_match_confidence"] < match_threshold:
        return None

    return {
        "id": row["claim_id"],
        "claimant_name": row["claim_claimant_name"],
        "company_involved": row["claim_company_involved"],
        "original_claim": row["original_claim"],
        "claim_date": row["claim_date"],
        "claim_topic": row["claim_topic"],
        "match_confidence": row["claim_match_confidence"],
    }


def serialize_public_archive_row(row: dict[str, Any]) -> dict[str, Any]:
    """Serialize a row for the public archive feed."""
    return {
        "id": row["id"],
        "headline": row["headline"],
        "headline_en": row.get("headline_en") or row["headline"],
        "headline_zh": row.get("headline_zh"),
        "date_logged": row["date_logged"],
        "company_involved": row["company_involved"],
        "company_involved_zh": row.get("company_involved_zh"),
        "incident_topic": row.get("incident_topic"),
        "claimant_name": row["claimant_name"],
        "categories": json.loads(row["categories"]),
        "severity_score": row["severity_score"],
        "archive_summary": row["reality_summary"],
        "archive_summary_en": row.get("reality_summary_en")
        or row["reality_summary"],
        "archive_summary_zh": row.get("reality_summary_zh"),
        "status": row["status"],
        "translation_status": row.get("translation_status"),
        **_dual_track_fields(row),
    }


def serialize_public_detail_row(
    row: dict[str, Any],
    sources: list[dict[str, Any]],
    *,
    match_threshold: float,
) -> dict[str, Any]:
    """Serialize a row for public incident detail view."""
    return {
        "id": row["id"],
        "headline": row["headline"],
        "headline_en": row.get("headline_en") or row["headline"],
        "headline_zh": row.get("headline_zh"),
        "date_logged": row["date_logged"],
        "company_involved": row["company_involved"],
        "company_involved_zh": row.get("company_involved_zh"),
        "incident_topic": row.get("incident_topic"),
        "claimant_name": row["claimant_name"],
        "categories": json.loads(row["categories"]),
        "severity_score": row["severity_score"],
        "reality_summary": row["reality_summary"],
        "reality_summary_en": row.get("reality_summary_en")
        or row["reality_summary"],
        "reality_summary_zh": row.get("reality_summary_zh"),
        "status": row["status"],
        "translation_status": row.get("translation_status"),
        **_dual_track_fields(row),
        "analysis": {
            "incident_summary_en": sanitize_reader_text(
                row.get("incident_summary_en"),
            )
            or row.get("reality_summary_en")
            or row["reality_summary"],
            "incident_summary_zh": sanitize_reader_text(
                row.get("incident_summary_zh"),
            )
            or sanitize_reader_text(
                row.get("reality_summary_zh"),
            ),
            "what_happened_en": sanitize_reader_text(
                row.get("what_happened_en"),
            ),
            "what_happened_zh": sanitize_reader_text(
                row.get("what_happened_zh"),
            ),
            "ai_failure_point_en": sanitize_reader_text(
                row.get("ai_failure_point_en"),
            ),
            "ai_failure_point_zh": sanitize_reader_text(
                row.get("ai_failure_point_zh"),
            ),
            "why_it_matters_en": sanitize_reader_text(
                row.get("why_it_matters_en"),
            )
            or sanitize_reader_text(
                row.get("legitimacy_reasoning"),
            ),
            "why_it_matters_zh": sanitize_reader_text(
                row.get("why_it_matters_zh"),
            )
            or sanitize_reader_text(
                row.get("legitimacy_reasoning_zh"),
            ),
            "evidence_summary_en": sanitize_reader_text(
                row.get("evidence_summary_en"),
            )
            or sanitize_reader_text(
                row.get("source_validation_summary"),
            )
            or _fallback_public_evidence_summary(sources, locale="en"),
            "evidence_summary_zh": sanitize_reader_text(
                row.get("evidence_summary_zh"),
            )
            or sanitize_reader_text(
                row.get("source_validation_summary_zh"),
            )
            or _fallback_public_evidence_summary(sources, locale="zh"),
        },
        "matched_claim": build_public_claim_payload(
            row, match_threshold=match_threshold
        ),
        "sources": sources,
    }


def _fallback_public_evidence_summary(
    sources: list[dict[str, Any]],
    *,
    locale: str,
) -> str | None:
    source_count = len(sources)
    if source_count == 0:
        return None

    if locale == "zh":
        if source_count == 1:
            return "已通过 1 个已链接来源核实。"
        return f"已通过 {source_count} 个已链接来源核实。"

    if source_count == 1:
        return "Supported by 1 linked source."
    return f"Supported by {source_count} linked sources."
