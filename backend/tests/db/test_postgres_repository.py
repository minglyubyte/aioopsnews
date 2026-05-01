from __future__ import annotations

import app.db.postgres_repository as postgres_repository
from app.db.postgres_repository import PostgresIncidentRepository


class _StubResult:
    def __init__(self, row: dict[str, object] | None = None) -> None:
        self._row = row
        self.rowcount = 1 if row is not None else 1

    def fetchone(self) -> dict[str, object] | None:
        return self._row

    def fetchall(self) -> list[dict[str, object]]:
        return []


class _StubConnection:
    def __init__(self) -> None:
        self.executed: list[str] = []
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def __enter__(self) -> "_StubConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def commit(self) -> None:
        return None

    def execute(self, query: str, *args, **kwargs) -> _StubResult:
        self.executed.append(query)
        self.calls.append((query, args))
        if "select count(*) as count from incident_logs" in query:
            return _StubResult({"count": 1})
        if "where id = %s" in query and "from incident_logs" in query:
            row = {
                "id": "incident-1",
                "external_id": None,
                "headline": "Updated headline",
                "headline_en": "Updated headline",
                "headline_zh": None,
                "date_logged": "2026-04-30",
                "company_involved": "OpenAI",
                "incident_topic": None,
                "claimant_name": None,
                "categories": '["Hallucinations"]',
                "severity_score": 3,
                "suggested_severity_score": None,
                "reality_summary": "Updated summary",
                "reality_summary_en": "Updated summary",
                "reality_summary_zh": None,
                "status": "rejected",
                "matched_claim_id": None,
                "claim_match_confidence": None,
                "review_notes": None,
                "legitimacy_score": 0.2,
                "legitimacy_label": "rejected",
                "severity_confidence": 0.1,
                "severity_reasoning": "Not enough evidence.",
                "severity_flags": "[]",
                "severity_model": "gpt-5.4-mini",
                "severity_decision_source": None,
                "legitimacy_reasoning": "Rejected.",
                "source_validation_summary": "Weak sources.",
                "translation_status": None,
                "review_batch_id": "batch-1",
                "review_model": "gpt-5.4-mini",
                "duplicate_status": None,
                "duplicate_of_incident_id": None,
                "canonical_incident_id": None,
            }
            if "legitimacy_reasoning_zh" in query:
                row["legitimacy_reasoning_zh"] = None
            if "source_validation_summary_zh" in query:
                row["source_validation_summary_zh"] = None
            return _StubResult(row)
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


def test_apply_incident_review_result_uses_python_decided_severity_score(
    monkeypatch,
) -> None:
    connection = _StubConnection()

    class StubConnectionPool:
        def __init__(self, conninfo: str, kwargs: dict[str, object]) -> None:
            self.conninfo = conninfo
            self.kwargs = kwargs

        def connection(self) -> _StubConnection:
            return connection

        def close(self) -> None:
            return None

    monkeypatch.setattr(postgres_repository, "ConnectionPool", StubConnectionPool)

    repository = PostgresIncidentRepository(
        "postgresql://postgres:postgres@localhost:5432/ai_reality_check"
    )

    repository.apply_incident_review_result(
        incident_id="incident-1",
        status="rejected",
        legitimacy_score=0.2,
        legitimacy_label="rejected",
        legitimacy_reasoning="Rejected.",
        source_validation_summary="Weak sources.",
        headline_en="Updated headline",
        reality_summary_en="Updated summary",
        categories=["Hallucinations"],
        severity_score=3,
        suggested_severity_score=None,
        severity_confidence=0.1,
        severity_reasoning="Not enough evidence.",
        severity_flags=[],
        severity_model="gpt-5.4-mini",
        severity_decision_source=None,
        severity_suggested_at="2026-04-30T12:00:00+00:00",
        review_model="gpt-5.4-mini",
        review_batch_id="batch-1",
        reviewed_at="2026-04-30T12:00:00+00:00",
    )

    update_query, update_args = next(
        (query, args)
        for query, args in connection.calls
        if "update incident_logs" in query
    )
    params = update_args[0]
    assert "is not null" not in update_query
    assert params[6] == 3
    assert params[7] is None


def test_apply_admin_review_selects_translation_fields(monkeypatch) -> None:
    connection = _StubConnection()

    class StubConnectionPool:
        def __init__(self, conninfo: str, kwargs: dict[str, object]) -> None:
            self.conninfo = conninfo
            self.kwargs = kwargs

        def connection(self) -> _StubConnection:
            return connection

        def close(self) -> None:
            return None

    monkeypatch.setattr(postgres_repository, "ConnectionPool", StubConnectionPool)

    repository = PostgresIncidentRepository(
        "postgresql://postgres:postgres@localhost:5432/ai_reality_check"
    )

    incident = repository.apply_admin_review(
        incident_id="incident-1",
        status="approved",
        company_involved="OpenAI",
        claimant_name=None,
        categories=["Hallucinations"],
        severity_score=3,
        reality_summary="Updated summary",
        matched_claim_id=None,
        claim_match_confidence=None,
        review_notes="Editor approved after review.",
    )

    assert incident is not None
    assert incident["legitimacy_reasoning_zh"] is None
    assert incident["source_validation_summary_zh"] is None
