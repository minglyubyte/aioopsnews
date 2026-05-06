from __future__ import annotations

from datetime import date
from uuid import UUID

import app.db.postgres_repository as postgres_repository
from app.db._serializers import group_sources_by_incident, serialize_llm_pending_row
from app.db.postgres_repository import PostgresIncidentRepository


def test_llm_pending_serializer_returns_json_safe_uuid_strings() -> None:
    incident_id = UUID("6a72c8c3-e5f4-4a7f-9974-5a2a87856344")
    source_id = UUID("55334442-d676-465c-946e-212bd177deef")
    row = {
        "id": incident_id,
        "external_id": "ca-dmv-waymo-2026-04-12-1",
        "headline": "Waymo collision report",
        "headline_en": "Waymo collision report",
        "headline_zh": None,
        "date_logged": date(2026, 4, 12),
        "company_involved": "Waymo",
        "company_involved_zh": None,
        "incident_topic": "autonomous_vehicle",
        "claimant_name": None,
        "categories": [],
        "severity_score": 1,
        "reality_summary": "California DMV published a collision report.",
        "reality_summary_en": "California DMV published a collision report.",
        "reality_summary_zh": None,
        "status": "pending_llm_review",
        "publication_track": "verified_accident",
        "evidence_tier": "official_documented",
        "source_family": "autonomous_vehicle",
        "verification_summary": "Fixed verified source.",
        "suggested_severity_score": None,
        "review_notes": None,
        "severity_confidence": None,
        "severity_reasoning": None,
        "severity_flags": [],
        "severity_model": None,
        "severity_decision_source": None,
        "legitimacy_flag": "REVIEW",
        "confidence_level": "high",
        "import_notes": None,
        "translation_status": "not_requested",
        "review_batch_id": None,
        "review_model": None,
        "duplicate_status": None,
        "duplicate_of_incident_id": None,
        "canonical_incident_id": None,
        "embedding_model": None,
        "embedding_vector": None,
    }

    serialized = serialize_llm_pending_row(
        row,
        sources=group_sources_by_incident(
            [
                {
                    "id": source_id,
                    "incident_id": incident_id,
                    "source_url": "https://www.dmv.ca.gov/report.pdf",
                    "source_type": "official",
                    "publisher": "California DMV",
                    "title": "Report",
                    "fetch_status": "fetched",
                    "http_status": 200,
                    "evidence_text": "Evidence",
                    "fetch_error": None,
                    "source_origin": "fixed_verified_source",
                    "source_registry_key": "ca_dmv_av_collisions",
                    "raw_source_payload": {},
                }
            ]
        )[str(incident_id)],
    )

    assert serialized["id"] == str(incident_id)
    assert serialized["date_logged"] == "2026-04-12"
    assert serialized["sources"][0]["id"] == str(source_id)


class _StubResult:
    def __init__(
        self,
        row: dict[str, object] | None = None,
        rows: list[dict[str, object]] | None = None,
    ) -> None:
        self._row = row
        self._rows = rows or []
        self.rowcount = 1 if row is not None else 1

    def fetchone(self) -> dict[str, object] | None:
        return self._row

    def fetchall(self) -> list[dict[str, object]]:
        return self._rows


class _StubConnection:
    def __init__(self) -> None:
        self.executed: list[str] = []
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.incident_row: dict[str, object] = {
            "id": "incident-1",
            "external_id": None,
            "headline": "Updated headline",
            "headline_en": "Updated headline",
            "headline_zh": None,
            "date_logged": "2026-04-30",
            "company_involved": "OpenAI",
            "company_involved_zh": "开放人工智能",
            "incident_topic": None,
            "claimant_name": None,
            "categories": ["Hallucinations"],
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
            "severity_flags": [],
            "severity_model": "gpt-5.4-mini",
            "severity_decision_source": None,
            "legitimacy_reasoning": "Rejected.",
            "legitimacy_reasoning_zh": None,
            "source_validation_summary": "Weak sources.",
            "source_validation_summary_zh": None,
            "incident_summary_en": None,
            "incident_summary_zh": None,
            "what_happened_en": None,
            "what_happened_zh": None,
            "ai_failure_point_en": None,
            "ai_failure_point_zh": None,
            "why_it_matters_en": None,
            "why_it_matters_zh": None,
            "evidence_summary_en": None,
            "evidence_summary_zh": None,
            "translation_status": None,
            "publication_track": "accident_watch",
            "evidence_tier": "reported_unconfirmed",
            "source_family": "model_governance",
            "verification_summary": (
                "Fresh schema row with classified evidence metadata."
            ),
            "review_batch_id": "batch-1",
            "review_model": "gpt-5.4-mini",
            "duplicate_status": None,
            "duplicate_of_incident_id": None,
            "canonical_incident_id": None,
            "claim_id": None,
            "claim_claimant_name": None,
            "claim_company_involved": None,
            "original_claim": None,
            "claim_date": None,
            "claim_topic": None,
            "claim_status": None,
        }

    def __enter__(self) -> "_StubConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def commit(self) -> None:
        return None

    def execute(self, query: str, *args, **kwargs) -> _StubResult:
        self.executed.append(query)
        self.calls.append((query, args))
        if (
            args
            and "update incident_logs" in query
            and "severity_suggested_at" in query
        ):
            params = args[0]
            self.incident_row.update(
                {
                    "status": params[0],
                    "headline": params[1],
                    "headline_en": params[2],
                    "reality_summary": params[3],
                    "reality_summary_en": params[4],
                    "categories": params[5],
                    "severity_score": params[6],
                    "suggested_severity_score": params[7],
                    "severity_confidence": params[8],
                    "severity_reasoning": params[9],
                    "severity_flags": params[10],
                    "severity_model": params[11],
                    "severity_decision_source": params[12],
                    "legitimacy_score": params[13],
                    "legitimacy_label": params[14],
                    "legitimacy_reasoning": params[15],
                    "source_validation_summary": params[16],
                    "incident_summary_en": params[17],
                    "what_happened_en": params[18],
                    "ai_failure_point_en": params[19],
                    "why_it_matters_en": params[20],
                    "evidence_summary_en": params[21],
                    "review_model": params[22],
                    "review_batch_id": params[23],
                    "reviewed_at": params[24],
                    "severity_suggested_at": params[25],
                }
            )
        if args and "update incident_logs" in query and "translated_at = %s" in query:
            params = args[0]
            self.incident_row.update(
                {
                    "company_involved_zh": params[0],
                    "headline_zh": params[1],
                    "reality_summary_zh": params[2],
                    "legitimacy_reasoning_zh": params[3],
                    "source_validation_summary_zh": params[4],
                    "incident_summary_zh": params[5],
                    "what_happened_zh": params[6],
                    "ai_failure_point_zh": params[7],
                    "why_it_matters_zh": params[8],
                    "evidence_summary_zh": params[9],
                    "translation_status": params[10],
                    "translated_at": params[11],
                }
            )
        if "select count(*) as count from incident_logs" in query:
            return _StubResult({"count": 1})
        if "select count(*) as total_count" in query:
            return _StubResult({"total_count": 1})
        if "max(incident_logs.date_logged) as newest_logged" in query:
            return _StubResult(
                {
                    "newest_logged": "2026-04-30",
                    "oldest_logged": "2026-04-30",
                    "highest_severity": 3,
                }
            )
        if "group by category.value" in query:
            return _StubResult(rows=[{"category": "Hallucinations", "count": 1}])
        if "group by incident_logs.company_involved" in query:
            return _StubResult(
                rows=[
                    {
                        "company": "OpenAI",
                        "company_zh": "开放人工智能",
                        "count": 1,
                    }
                ]
            )
        if (
            "from incident_logs" in query
            and "order by incident_logs.date_logged desc" in query
        ):
            return _StubResult(
                rows=[
                    {
                        "id": "incident-1",
                        "headline": "Updated headline",
                        "headline_en": "Updated headline",
                        "headline_zh": None,
                        "date_logged": "2026-04-30",
                        "company_involved": "OpenAI",
                        "company_involved_zh": "开放人工智能",
                        "incident_topic": None,
                        "claimant_name": None,
                        "categories": ["Hallucinations"],
                        "severity_score": 3,
                        "reality_summary": "Updated summary",
                        "reality_summary_en": "Updated summary",
                        "reality_summary_zh": None,
                        "status": "approved",
                        "translation_status": "completed",
                        "publication_track": "accident_watch",
                        "evidence_tier": "reported_unconfirmed",
                        "source_family": "model_governance",
                        "verification_summary": (
                            "Fresh schema row with classified evidence metadata."
                        ),
                    }
                ]
            )
        if "from incident_logs" in query and (
            "where id = %s" in query or "where incident_logs.id = %s" in query
        ):
            row = dict(self.incident_row)
            if "company_involved_zh" in query:
                row["company_involved_zh"] = "开放人工智能"
            return _StubResult(row)
        if "from incident_sources" in query:
            return _StubResult(
                rows=[
                    {
                        "id": "source-1",
                        "incident_id": "incident-1",
                        "source_url": "https://example.com/source",
                        "source_type": "primary",
                        "publisher": "Example News",
                        "title": "Updated headline",
                    }
                ]
            )
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


def test_postgres_repository_does_not_reseed_after_empty_tables(monkeypatch) -> None:
    class EmptyDatabaseConnection(_StubConnection):
        def execute(self, query: str, *args, **kwargs) -> _StubResult:
            self.executed.append(query)
            self.calls.append((query, args))
            if "select count(*) as count from incident_logs" in query:
                return _StubResult({"count": 0})
            return _StubResult()

    connection = EmptyDatabaseConnection()

    class StubConnectionPool:
        def __init__(self, conninfo: str, kwargs: dict[str, object]) -> None:
            self.conninfo = conninfo
            self.kwargs = kwargs

        def connection(self) -> _StubConnection:
            return connection

        def close(self) -> None:
            return None

    monkeypatch.setattr(postgres_repository, "ConnectionPool", StubConnectionPool)

    PostgresIncidentRepository(
        "postgresql://postgres:postgres@localhost:5432/ai_reality_check"
    )

    assert not any(
        "insert into claims" in query
        or "insert into incident_logs" in query
        or "insert into incident_sources" in query
        for query in connection.executed
    )


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

    incident = repository.apply_incident_review_result(
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
        incident_summary_en="Short incident summary.",
        what_happened_en="What happened.",
        ai_failure_point_en="Failure point.",
        why_it_matters_en="Why it matters.",
        evidence_summary_en="Evidence summary.",
    )

    update_query, update_args = next(
        (query, args)
        for query, args in connection.calls
        if args and "update incident_logs" in query
    )
    params = update_args[0]
    assert "is not null" not in update_query
    assert params[6] == 3
    assert params[7] is None
    assert "incident_summary_en = %s" in update_query
    assert params[17] == "Short incident summary."
    assert params[21] == "Evidence summary."
    assert incident is not None
    assert incident["incident_summary_en"] == "Short incident summary."
    assert incident["what_happened_en"] == "What happened."
    assert incident["ai_failure_point_en"] == "Failure point."
    assert incident["why_it_matters_en"] == "Why it matters."
    assert incident["evidence_summary_en"] == "Evidence summary."


def test_postgres_repository_writes_native_postgres_values(monkeypatch) -> None:
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
        status="approved",
        legitimacy_score=0.9,
        legitimacy_label="auto_publish",
        legitimacy_reasoning="Strong source trail.",
        source_validation_summary="Validated.",
        headline_en="Updated headline",
        reality_summary_en="Updated summary",
        categories=["Hallucinations"],
        severity_score=4,
        suggested_severity_score=4,
        severity_confidence=0.8,
        severity_reasoning="Meaningful disruption.",
        severity_flags=["core_system_outage"],
        severity_model="gpt-5.4-mini",
        severity_decision_source="primary_llm",
        severity_suggested_at="2026-04-30T12:00:00+00:00",
        review_model="gpt-5.4-mini",
        review_batch_id="batch-1",
        reviewed_at="2026-04-30T12:00:00+00:00",
    )
    repository.update_incident_embedding(
        incident_id="incident-1",
        embedding_model="text-embedding-3-small",
        embedding_vector=[0.1, 0.9],
    )

    review_params = next(
        args[0]
        for query, args in connection.calls
        if args and "severity_suggested_at = %s" in query
    )
    embedding_params = next(
        args[0]
        for query, args in connection.calls
        if args and "embedding_vector = %s" in query
    )

    assert review_params[5] == ["Hallucinations"]
    assert review_params[10] == ["core_system_outage"]
    assert embedding_params[1] == [0.1, 0.9]


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
    assert incident["company_involved_zh"] == "开放人工智能"
    assert incident["legitimacy_reasoning_zh"] is None
    assert incident["source_validation_summary_zh"] is None


def test_update_incident_translation_persists_company_name_translation(
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

    incident = repository.update_incident_translation(
        incident_id="incident-1",
        company_involved_zh="开放人工智能",
        headline_zh="更新后的标题",
        reality_summary_zh="更新后的摘要",
        legitimacy_reasoning_zh="中文理由",
        source_validation_summary_zh="中文证据摘要",
        translation_status="completed",
        translated_at="2026-04-30T12:00:00+00:00",
        incident_summary_zh="事件摘要",
        what_happened_zh="发生了什么",
        ai_failure_point_zh="失败点",
        why_it_matters_zh="重要性说明",
        evidence_summary_zh="证据摘要",
    )

    update_query, update_args = next(
        (query, args)
        for query, args in connection.calls
        if args and "update incident_logs" in query
    )
    params = update_args[0]

    assert "company_involved_zh = %s" in update_query
    assert incident is not None
    assert incident["company_involved_zh"] == "开放人工智能"
    assert params[0] == "开放人工智能"
    assert params[1] == "更新后的标题"
    assert "incident_summary_zh = %s" in update_query
    assert params[5] == "事件摘要"
    assert params[9] == "证据摘要"
    assert incident["incident_summary_zh"] == "事件摘要"
    assert incident["what_happened_zh"] == "发生了什么"
    assert incident["ai_failure_point_zh"] == "失败点"
    assert incident["why_it_matters_zh"] == "重要性说明"
    assert incident["evidence_summary_zh"] == "证据摘要"


def test_list_public_incident_feed_serializes_company_name_translation(
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

    feed = repository.list_public_incident_feed(
        postgres_repository.IncidentQueryFilters()
    )

    assert feed["items"][0]["company_involved_zh"] == "开放人工智能"
    assert feed["slice_summary"]["top_companies"] == [
        {"company": "OpenAI", "company_zh": "开放人工智能", "count": 1}
    ]


def test_get_public_incident_serializes_company_name_translation(
    monkeypatch,
) -> None:
    connection = _StubConnection()
    connection.incident_row["incident_summary_en"] = "Short summary."
    connection.incident_row["incident_summary_zh"] = "简短摘要。"
    connection.incident_row["what_happened_en"] = "Detailed sequence."
    connection.incident_row["what_happened_zh"] = "详细经过。"
    connection.incident_row["ai_failure_point_en"] = "Guardrail failure."
    connection.incident_row["ai_failure_point_zh"] = "护栏失效。"
    connection.incident_row["why_it_matters_en"] = "This mattered."
    connection.incident_row["why_it_matters_zh"] = "这很重要。"
    connection.incident_row["evidence_summary_en"] = "Primary report."
    connection.incident_row["evidence_summary_zh"] = "一手报告。"

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

    incident = repository.get_public_incident("incident-1")

    assert incident is not None
    assert incident["company_involved_zh"] == "开放人工智能"
    assert incident["analysis"]["incident_summary_en"] == "Short summary."
    assert incident["analysis"]["what_happened_en"] == "Detailed sequence."
    assert incident["analysis"]["ai_failure_point_en"] == "Guardrail failure."
    assert incident["analysis"]["why_it_matters_en"] == "This mattered."
    assert incident["analysis"]["evidence_summary_en"] == "Primary report."


def test_get_filter_values_returns_chinese_company_labels(monkeypatch) -> None:
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

    filters = repository.get_filter_values()

    assert filters["companies"] == ["OpenAI"]
    assert filters["company_labels_zh"] == {"OpenAI": "开放人工智能"}
