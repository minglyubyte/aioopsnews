from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class IncidentQueryFilters:
    category: str | None = None
    company: str | None = None
    claimant: str | None = None
    severity_min: int | None = None
    severity_max: int | None = None
    year: int | None = None
    month: int | None = None
    page: int = 1
    page_size: int = 20


class IncidentReadRepository(Protocol):
    def list_public_incidents(
        self,
        filters: IncidentQueryFilters,
    ) -> list[dict[str, object]]: ...

    def get_public_incident(self, incident_id: str) -> dict[str, object] | None: ...

    def get_filter_values(self) -> dict[str, object]: ...


def list_public_incidents(
    repository: IncidentReadRepository,
    filters: IncidentQueryFilters,
) -> list[dict[str, object]]:
    return repository.list_public_incidents(filters)


def get_public_incident(
    repository: IncidentReadRepository,
    incident_id: str,
) -> dict[str, object] | None:
    return repository.get_public_incident(incident_id)


def get_filter_values(repository: IncidentReadRepository) -> dict[str, object]:
    return repository.get_filter_values()
