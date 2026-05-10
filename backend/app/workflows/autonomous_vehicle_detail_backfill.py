from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any, Protocol

from app.services.autonomous_vehicle_details import (
    assess_autonomous_vehicle_detail_quality,
    build_autonomous_vehicle_detail_copy,
)
from app.services.incident_translation import (
    IncidentTranslationClient,
    translate_incident_copy,
)


class AutonomousVehicleBackfillRepository(Protocol):
    def list_public_incidents(self, filters: Any) -> list[dict[str, Any]]: ...

    def get_public_incident(self, incident_id: str) -> dict[str, Any] | None: ...

    def update_incident_detail_copy(
        self,
        *,
        incident_id: str,
        incident_summary_en: str,
        what_happened_en: str,
        ai_failure_point_en: str,
        why_it_matters_en: str,
        evidence_summary_en: str,
    ) -> None: ...

    def update_incident_translation(
        self,
        *,
        incident_id: str,
        company_involved_zh: str,
        headline_zh: str,
        reality_summary_zh: str,
        legitimacy_reasoning_zh: str,
        source_validation_summary_zh: str,
        translation_status: str,
        translated_at: str,
        incident_summary_zh: str | None = None,
        what_happened_zh: str | None = None,
        ai_failure_point_zh: str | None = None,
        why_it_matters_zh: str | None = None,
        evidence_summary_zh: str | None = None,
    ) -> dict[str, Any] | None: ...


def select_autonomous_vehicle_detail_backfill_candidates(
    repository: AutonomousVehicleBackfillRepository,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    incidents = _approved_incidents(repository)
    candidates = [
        incident
        for incident in incidents
        if incident.get("status") == "approved"
        and incident.get("source_family") == "autonomous_vehicle"
        and _detail_quality(incident) == "insufficient"
    ]
    return candidates[:limit] if limit is not None else candidates


def _detail_quality(incident: dict[str, Any]) -> str:
    analysis = incident.get("analysis")
    if isinstance(analysis, dict) and isinstance(analysis.get("detail_quality"), str):
        return str(analysis["detail_quality"])
    return assess_autonomous_vehicle_detail_quality(incident).detail_quality


def backfill_autonomous_vehicle_details(
    repository: AutonomousVehicleBackfillRepository,
    *,
    translation_client: IncidentTranslationClient | None = None,
    translation_concurrency: int = 1,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    candidates = select_autonomous_vehicle_detail_backfill_candidates(
        repository,
        limit=limit,
    )
    summary = {
        "candidates": len(candidates),
        "updated": 0,
        "translated": 0,
        "skipped": 0,
        "translation_failed": 0,
    }
    work_items = []
    for incident in candidates:
        detail_copy = build_autonomous_vehicle_detail_copy(incident)
        if detail_copy is None:
            summary["skipped"] += 1
            continue
        work_items.append((incident, detail_copy))

    if dry_run:
        summary["updated"] = len(work_items)
        if translation_client is not None:
            summary["translated"] = len(work_items)
        return summary

    if translation_client is None:
        for incident, detail_copy in work_items:
            repository.update_incident_detail_copy(
                incident_id=str(incident["id"]),
                **detail_copy.as_dict(),
            )
            summary["updated"] += 1
        return summary

    if translation_concurrency <= 1:
        for incident, detail_copy in work_items:
            translation = _translate_detail_copy(
                incident,
                detail_copy,
                translation_client,
            )
            _apply_detail_copy_with_translation(
                repository,
                incident,
                detail_copy,
                translation,
            )
            summary["updated"] += 1
            summary["translated"] += 1
        return summary

    with ThreadPoolExecutor(max_workers=translation_concurrency) as executor:
        future_to_item = {
            executor.submit(
                _translate_detail_copy,
                incident,
                detail_copy,
                translation_client,
            ): (incident, detail_copy)
            for incident, detail_copy in work_items
        }
        for future in as_completed(future_to_item):
            incident, detail_copy = future_to_item[future]
            try:
                translation = future.result()
            except Exception:
                summary["translation_failed"] += 1
                continue
            _apply_detail_copy_with_translation(
                repository,
                incident,
                detail_copy,
                translation,
            )
            summary["updated"] += 1
            summary["translated"] += 1

    return summary


def _translate_detail_copy(
    incident: dict[str, Any],
    detail_copy: Any,
    translation_client: IncidentTranslationClient,
) -> Any:
    return translate_incident_copy(
        company_involved_en=str(incident.get("company_involved") or ""),
        headline_en=str(incident.get("headline_en") or incident["headline"]),
        reality_summary_en=str(
            incident.get("reality_summary_en") or incident["reality_summary"]
        ),
        incident_summary_en=detail_copy.incident_summary_en,
        what_happened_en=detail_copy.what_happened_en,
        ai_failure_point_en=detail_copy.ai_failure_point_en,
        why_it_matters_en=detail_copy.why_it_matters_en,
        evidence_summary_en=detail_copy.evidence_summary_en,
        legitimacy_reasoning_en=str(incident.get("legitimacy_reasoning") or ""),
        source_validation_summary_en=str(
            incident.get("source_validation_summary") or ""
        ),
        client=translation_client,
    )


def _apply_detail_copy_with_translation(
    repository: AutonomousVehicleBackfillRepository,
    incident: dict[str, Any],
    detail_copy: Any,
    translation: Any,
) -> None:
    repository.update_incident_detail_copy(
        incident_id=str(incident["id"]),
        **detail_copy.as_dict(),
    )
    repository.update_incident_translation(
        incident_id=str(incident["id"]),
        company_involved_zh=translation.company_involved_zh,
        headline_zh=translation.headline_zh,
        reality_summary_zh=translation.reality_summary_zh,
        legitimacy_reasoning_zh=translation.legitimacy_reasoning_zh,
        source_validation_summary_zh=translation.source_validation_summary_zh,
        incident_summary_zh=translation.incident_summary_zh,
        what_happened_zh=translation.what_happened_zh,
        ai_failure_point_zh=translation.ai_failure_point_zh,
        why_it_matters_zh=translation.why_it_matters_zh,
        evidence_summary_zh=translation.evidence_summary_zh,
        translation_status=translation.status,
        translated_at=_now_isoformat(),
    )


def _approved_incidents(
    repository: AutonomousVehicleBackfillRepository,
) -> list[dict[str, Any]]:
    in_memory_incidents = getattr(repository, "incidents", None)
    if isinstance(in_memory_incidents, dict):
        return list(in_memory_incidents.values())

    from app.services.incident_query import IncidentQueryFilters

    incidents: list[dict[str, Any]] = []
    page = 1
    page_size = 100
    while True:
        archive_items = repository.list_public_incidents(
            IncidentQueryFilters(
                source_family="autonomous_vehicle",
                page=page,
                page_size=page_size,
            )
        )
        for item in archive_items:
            detail = repository.get_public_incident(str(item["id"]))
            if detail is not None:
                incidents.append(detail)
        if len(archive_items) < page_size:
            break
        page += 1
    return incidents


def _now_isoformat() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()
