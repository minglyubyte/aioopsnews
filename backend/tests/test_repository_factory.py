from __future__ import annotations

from pathlib import Path

import app.db.repository_factory as repository_factory
from app.db.repository_factory import build_incident_repository
from app.db.sqlite_repository import SQLiteIncidentRepository


def test_build_incident_repository_uses_sqlite_for_sqlite_urls(
    tmp_path: Path,
) -> None:
    repository = build_incident_repository(f"sqlite:///{tmp_path / 'sqlite.db'}")

    assert isinstance(repository, SQLiteIncidentRepository)


def test_build_incident_repository_uses_postgres_for_postgresql_urls(
    monkeypatch,
) -> None:
    class StubPostgresIncidentRepository:
        def __init__(self, database_url: str) -> None:
            self.database_url = database_url

    monkeypatch.setattr(
        repository_factory,
        "PostgresIncidentRepository",
        StubPostgresIncidentRepository,
    )

    repository = build_incident_repository(
        "postgresql://postgres:postgres@localhost:5432/ai_reality_check"
    )

    assert isinstance(repository, StubPostgresIncidentRepository)
    assert repository.database_url.endswith("/ai_reality_check")


def test_build_incident_repository_rejects_unknown_schemes() -> None:
    try:
        build_incident_repository("mysql://user:pass@localhost:3306/ai_reality_check")
    except ValueError as exc:
        assert "Unsupported DATABASE_URL scheme" in str(exc)
    else:
        raise AssertionError("Expected unknown schemes to raise ValueError")
