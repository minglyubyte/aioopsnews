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
    page: int = 1
    page_size: int = 20


class IncidentReadRepository(Protocol):
    def list_public_incidents(
        self,
        filters: IncidentQueryFilters,
    ) -> list[dict[str, object]]: ...

    def get_filter_values(self) -> dict[str, list[str]]: ...


def list_public_incidents(
    repository: IncidentReadRepository,
    filters: IncidentQueryFilters,
) -> list[dict[str, object]]:
    return repository.list_public_incidents(filters)


def get_filter_values(repository: IncidentReadRepository) -> dict[str, list[str]]:
    return repository.get_filter_values()
