from __future__ import annotations

from typing import Protocol


class IncidentReadRepository(Protocol):
    def list_public_incidents(self) -> list[dict[str, object]]: ...

    def get_filter_values(self) -> dict[str, list[str]]: ...


def list_public_incidents(
    repository: IncidentReadRepository,
) -> list[dict[str, object]]:
    return repository.list_public_incidents()


def get_filter_values(repository: IncidentReadRepository) -> dict[str, list[str]]:
    return repository.get_filter_values()
