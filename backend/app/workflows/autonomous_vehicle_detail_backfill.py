from __future__ import annotations

from typing import Any, Protocol

from app.services.autonomous_vehicle_details import (
    assess_autonomous_vehicle_detail_quality,
)


class AutonomousVehicleBackfillRepository(Protocol):
    def list_public_incidents(self, filters: Any) -> list[dict[str, Any]]: ...

    def get_public_incident(self, incident_id: str) -> dict[str, Any] | None: ...


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
        and assess_autonomous_vehicle_detail_quality(incident).detail_quality
        == "insufficient"
    ]
    return candidates[:limit] if limit is not None else candidates


def _approved_incidents(
    repository: AutonomousVehicleBackfillRepository,
) -> list[dict[str, Any]]:
    in_memory_incidents = getattr(repository, "incidents", None)
    if isinstance(in_memory_incidents, dict):
        return list(in_memory_incidents.values())

    from app.services.incident_query import IncidentQueryFilters

    archive_items = repository.list_public_incidents(
        IncidentQueryFilters(source_family="autonomous_vehicle", page_size=100)
    )
    incidents: list[dict[str, Any]] = []
    for item in archive_items:
        detail = repository.get_public_incident(str(item["id"]))
        if detail is not None:
            incidents.append(detail)
    return incidents
