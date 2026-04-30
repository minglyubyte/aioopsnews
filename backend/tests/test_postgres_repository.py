from __future__ import annotations

import app.db.postgres_repository as postgres_repository
from app.db.postgres_repository import PostgresIncidentRepository


class _StubResult:
    def __init__(self, row: dict[str, object] | None = None) -> None:
        self._row = row

    def fetchone(self) -> dict[str, object] | None:
        return self._row


class _StubConnection:
    def __init__(self) -> None:
        self.executed: list[str] = []

    def __enter__(self) -> "_StubConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, query: str, *args, **kwargs) -> _StubResult:
        self.executed.append(query)
        if "select count(*) as count from incident_logs" in query:
            return _StubResult({"count": 1})
        return _StubResult()


def test_postgres_repository_bootstraps_with_connection_pool(monkeypatch) -> None:
    connection = _StubConnection()
    direct_connect_calls: list[str] = []

    class StubConnectionPool:
        def __init__(self, conninfo: str, kwargs: dict[str, object]) -> None:
            self.conninfo = conninfo
            self.kwargs = kwargs
            self.closed = False
            self.connection_calls = 0

        def connection(self) -> _StubConnection:
            self.connection_calls += 1
            return connection

        def close(self) -> None:
            self.closed = True

    def fail_direct_connect(*args, **kwargs):
        direct_connect_calls.append("called")
        raise AssertionError("Repository should use psycopg_pool instead of connect()")

    import psycopg

    monkeypatch.setattr(postgres_repository, "ConnectionPool", StubConnectionPool)
    monkeypatch.setattr(psycopg, "connect", fail_direct_connect)

    repository = PostgresIncidentRepository(
        "postgresql://postgres:postgres@localhost:5432/ai_reality_check"
    )

    assert isinstance(repository._pool, StubConnectionPool)
    assert repository._pool.conninfo.endswith("/ai_reality_check")
    assert repository._pool.connection_calls == 1
    assert direct_connect_calls == []

    repository.close()

    assert repository._pool.closed is True
