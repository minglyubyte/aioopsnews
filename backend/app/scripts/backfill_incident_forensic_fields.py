from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Iterable

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.services.incident_query import IncidentQueryFilters
from app.services.incident_review import (
    AUTO_APPROVAL_LEGITIMACY_THRESHOLD,
    AsyncCompatibleIncidentReviewClient,
    CompatibleIncidentReviewClient,
    FORENSIC_MIN_WORD_COUNTS,
    IncidentReviewResult,
    _now_isoformat,
    _resolve_review_decision,
)
from app.services.incident_translation import (
    DeepSeekIncidentTranslationClient,
    translate_incident_copy,
)

FORENSIC_EN_FIELDS = (
    "incident_summary_en",
    "what_happened_en",
    "ai_failure_point_en",
    "why_it_matters_en",
    "evidence_summary_en",
)
FORENSIC_ZH_FIELDS = (
    "incident_summary_zh",
    "what_happened_zh",
    "ai_failure_point_zh",
    "why_it_matters_zh",
    "evidence_summary_zh",
)


def _iter_public_incident_ids(repository) -> Iterable[str]:
    page = 1
    while True:
        items = repository.list_public_incidents(
            IncidentQueryFilters(page=page, page_size=100)
        )
        if not items:
            return
        for item in items:
            incident_id = item.get("id")
            if isinstance(incident_id, str) and incident_id:
                yield incident_id
        if len(items) < 100:
            return
        page += 1


def _missing_forensic_fields(incident: dict[str, object]) -> list[str]:
    analysis = incident.get("analysis")
    analysis_fields = analysis if isinstance(analysis, dict) else incident
    missing: list[str] = []
    for field_name in (*FORENSIC_EN_FIELDS, *FORENSIC_ZH_FIELDS):
        value = analysis_fields.get(field_name)
        if not isinstance(value, str) or not value.strip():
            missing.append(field_name)
            continue
        min_words = FORENSIC_MIN_WORD_COUNTS.get(field_name)
        if min_words is not None and len(value.split()) < min_words:
            missing.append(field_name)
    return missing


def _missing_result_fields(result: IncidentReviewResult) -> list[str]:
    missing: list[str] = []
    for field_name in FORENSIC_EN_FIELDS:
        value = getattr(result, field_name)
        if not isinstance(value, str) or not value.strip():
            missing.append(field_name)
            continue
        min_words = FORENSIC_MIN_WORD_COUNTS.get(field_name)
        if min_words is not None and len(value.split()) < min_words:
            missing.append(field_name)
    return missing


def _coerce_categories(incident: dict[str, object], result: IncidentReviewResult) -> list[str]:
    incident_categories = incident.get("categories")
    if isinstance(incident_categories, list):
        categories = [str(category) for category in incident_categories if str(category)]
        if categories:
            return categories
    return list(result.categories or [])


def _coerce_severity_score(
    incident: dict[str, object],
    result: IncidentReviewResult,
) -> int:
    severity_score = incident.get("severity_score")
    if isinstance(severity_score, int):
        return severity_score
    if result.suggested_severity_score is not None:
        return result.suggested_severity_score
    return 1


async def _backfill(args: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    primary_review_api_key = (
        settings.primary_review_api_key or settings.deepseek_api_key
    )
    if not primary_review_api_key:
        raise ValueError(
            "Missing PRIMARY_REVIEW_API_KEY and DEEPSEEK_API_KEY for review backfill."
        )
    if not settings.deepseek_api_key:
        raise ValueError("Missing DEEPSEEK_API_KEY for translation backfill.")

    repository = build_incident_repository(settings.database_url)
    try:
        review_client = AsyncCompatibleIncidentReviewClient(
            api_key=primary_review_api_key,
            base_url=settings.primary_review_base_url,
            max_output_tokens=settings.review_max_output_tokens,
            response_parse_max_attempts=settings.review_response_parse_max_attempts,
        )
        escalation_client = CompatibleIncidentReviewClient(
            api_key=primary_review_api_key,
            base_url=settings.primary_review_base_url,
            max_output_tokens=settings.review_max_output_tokens,
            response_parse_max_attempts=settings.review_response_parse_max_attempts,
        )
        translation_client = DeepSeekIncidentTranslationClient(
            api_key=settings.deepseek_api_key,
            model="deepseek-v4-flash",
        )

        candidates: list[dict[str, object]] = []
        for incident_id in _iter_public_incident_ids(repository):
            incident = repository.get_incident(incident_id)
            public_incident = repository.get_public_incident(incident_id)
            if incident is None or public_incident is None:
                continue
            missing_fields = _missing_forensic_fields(public_incident)
            if missing_fields:
                candidates.append(
                    {
                        "incident": incident,
                        "missing_fields": missing_fields,
                    }
                )

        if args.limit is not None:
            candidates = candidates[: args.limit]

        if args.dry_run:
            return {
                "dry_run": True,
                "candidates_found": len(candidates),
                "updated": 0,
                "failures": [],
                "updated_items": [],
                "candidate_items": [
                    {
                        "id": str(candidate["incident"]["id"]),
                        "external_id": str(
                            candidate["incident"].get("external_id") or ""
                        ),
                        "missing_fields": list(candidate["missing_fields"]),
                    }
                    for candidate in candidates
                ],
            }

        updated: list[dict[str, object]] = []
        failures: list[dict[str, str]] = []
        for candidate in candidates:
            incident = candidate["incident"]
            try:
                initial_result = await review_client.review_incident(
                    incident=incident,
                    model=settings.primary_review_model,
                )
                decision = _resolve_review_decision(
                    incident=incident,
                    initial_result=initial_result,
                    escalation_client=escalation_client,
                    escalation_model=settings.escalation_review_model,
                    approval_threshold=AUTO_APPROVAL_LEGITIMACY_THRESHOLD,
                )
                result = decision.result
                missing_result_fields = _missing_result_fields(result)
                if missing_result_fields:
                    raise RuntimeError(
                        "review result missing fields: "
                        + ", ".join(missing_result_fields)
                    )
                translation = translate_incident_copy(
                    company_involved_en=str(incident.get("company_involved") or ""),
                    headline_en=str(
                        incident.get("headline_en")
                        or incident.get("headline")
                        or result.headline_en
                    ),
                    reality_summary_en=str(
                        incident.get("reality_summary_en")
                        or incident.get("reality_summary")
                        or result.reality_summary_en
                    ),
                    legitimacy_reasoning_en=str(
                        incident.get("legitimacy_reasoning") or result.reasoning
                    ),
                    source_validation_summary_en=str(
                        incident.get("source_validation_summary")
                        or result.source_quality_summary
                    ),
                    incident_summary_en=result.incident_summary_en or "",
                    what_happened_en=result.what_happened_en or "",
                    ai_failure_point_en=result.ai_failure_point_en or "",
                    why_it_matters_en=result.why_it_matters_en or "",
                    evidence_summary_en=result.evidence_summary_en or "",
                    client=translation_client,
                )
                reviewed_at = _now_isoformat()
                repository.apply_incident_review_result(
                    incident_id=str(incident["id"]),
                    status=str(incident.get("status") or "approved"),
                    legitimacy_score=float(
                        incident.get("legitimacy_score") or result.score
                    ),
                    legitimacy_label=str(
                        incident.get("legitimacy_label") or result.verdict
                    ),
                    legitimacy_reasoning=str(
                        incident.get("legitimacy_reasoning") or result.reasoning
                    ),
                    source_validation_summary=str(
                        incident.get("source_validation_summary")
                        or result.source_quality_summary
                    ),
                    headline_en=str(
                        incident.get("headline_en")
                        or incident.get("headline")
                        or result.headline_en
                    ),
                    reality_summary_en=str(
                        incident.get("reality_summary_en")
                        or incident.get("reality_summary")
                        or result.reality_summary_en
                    ),
                    categories=_coerce_categories(incident, result),
                    severity_score=_coerce_severity_score(incident, result),
                    suggested_severity_score=(
                        int(incident["suggested_severity_score"])
                        if isinstance(incident.get("suggested_severity_score"), int)
                        else result.suggested_severity_score
                    ),
                    severity_confidence=(
                        float(incident["severity_confidence"])
                        if isinstance(incident.get("severity_confidence"), (int, float))
                        else result.severity_confidence
                    ),
                    severity_reasoning=(
                        str(incident["severity_reasoning"])
                        if isinstance(incident.get("severity_reasoning"), str)
                        and incident["severity_reasoning"]
                        else result.severity_reasoning
                    ),
                    severity_flags=[
                        str(flag)
                        for flag in incident.get("severity_flags", [])
                        if str(flag)
                    ]
                    or list(result.severity_flags or []),
                    severity_model=str(
                        incident.get("severity_model") or result.reviewed_model
                    ),
                    severity_decision_source=(
                        str(incident["severity_decision_source"])
                        if isinstance(incident.get("severity_decision_source"), str)
                        and incident["severity_decision_source"]
                        else None
                    ),
                    severity_suggested_at=str(
                        incident.get("severity_suggested_at") or reviewed_at
                    ),
                    review_model=result.reviewed_model,
                    review_batch_id=(
                        str(incident["review_batch_id"])
                        if isinstance(incident.get("review_batch_id"), str)
                        and incident["review_batch_id"]
                        else None
                    ),
                    reviewed_at=reviewed_at,
                    incident_summary_en=result.incident_summary_en,
                    what_happened_en=result.what_happened_en,
                    ai_failure_point_en=result.ai_failure_point_en,
                    why_it_matters_en=result.why_it_matters_en,
                    evidence_summary_en=result.evidence_summary_en,
                )
                repository.update_incident_translation(
                    incident_id=str(incident["id"]),
                    company_involved_zh=(
                        str(incident["company_involved_zh"])
                        if isinstance(incident.get("company_involved_zh"), str)
                        and incident["company_involved_zh"]
                        else translation.company_involved_zh
                    ),
                    headline_zh=(
                        str(incident["headline_zh"])
                        if isinstance(incident.get("headline_zh"), str)
                        and incident["headline_zh"]
                        else translation.headline_zh
                    ),
                    reality_summary_zh=(
                        str(incident["reality_summary_zh"])
                        if isinstance(incident.get("reality_summary_zh"), str)
                        and incident["reality_summary_zh"]
                        else translation.reality_summary_zh
                    ),
                    legitimacy_reasoning_zh=(
                        str(incident["legitimacy_reasoning_zh"])
                        if isinstance(incident.get("legitimacy_reasoning_zh"), str)
                        and incident["legitimacy_reasoning_zh"]
                        else translation.legitimacy_reasoning_zh
                    ),
                    source_validation_summary_zh=(
                        str(incident["source_validation_summary_zh"])
                        if isinstance(incident.get("source_validation_summary_zh"), str)
                        and incident["source_validation_summary_zh"]
                        else translation.source_validation_summary_zh
                    ),
                    translation_status="completed",
                    translated_at=reviewed_at,
                    incident_summary_zh=translation.incident_summary_zh,
                    what_happened_zh=translation.what_happened_zh,
                    ai_failure_point_zh=translation.ai_failure_point_zh,
                    why_it_matters_zh=translation.why_it_matters_zh,
                    evidence_summary_zh=translation.evidence_summary_zh,
                )
                updated.append(
                    {
                        "id": str(incident["id"]),
                        "external_id": str(incident.get("external_id") or ""),
                        "headline_en": str(
                            incident.get("headline_en")
                            or incident.get("headline")
                            or result.headline_en
                        ),
                        "escalated": decision.escalated,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    {
                        "id": str(incident["id"]),
                        "external_id": str(incident.get("external_id") or ""),
                        "error": str(exc),
                    }
                )

        return {
            "dry_run": False,
            "candidates_found": len(candidates),
            "updated": len(updated),
            "failures": failures,
            "updated_items": updated,
        }
    finally:
        repository.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill structured forensic incident fields for approved incidents "
            "that are still missing them."
        )
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of approved incidents to backfill.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report which incidents need backfill without writing updates.",
    )
    args = parser.parse_args()

    summary = asyncio.run(_backfill(args))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not summary["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
