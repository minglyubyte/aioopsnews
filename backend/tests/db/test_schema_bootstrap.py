from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from app.db.postgres_repository import _POSTGRES_SCHEMA
from app.models.claim import ClaimRecord
from app.models.incident import IncidentRecord
from app.models.source import IncidentSourceRecord

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_product_docs_are_reorganized_into_four_canonical_files() -> None:
    product_docs = sorted(
        path.name for path in (REPO_ROOT / "docs" / "product").glob("*.md")
    )

    assert product_docs == [
        "daily-runner.md",
        "database-schema.md",
        "mvp.md",
        "prod-spec.md",
    ]


def test_product_decision_record_captures_mvp_foundation() -> None:
    decision_record = (
        REPO_ROOT / "docs" / "product" / "prod-spec.md"
    ).read_text()

    lowered = decision_record.lower()

    assert "trusted source list" in lowered
    assert "taxonomy" in lowered
    assert "claims table" in lowered
    assert "manual review" in lowered
    assert "primary sources" in lowered


def test_postgres_schema_defines_claim_sources_notes_and_core_tables() -> None:
    normalized = _POSTGRES_SCHEMA.lower()

    assert "create table if not exists claims" in normalized
    assert "notes text" in normalized
    assert "create table if not exists claim_sources" in normalized
    assert "create table if not exists incident_logs" in normalized
    assert "create table if not exists incident_sources" in normalized
    assert "references claims(id)" in normalized
    assert "severity_score integer not null" in normalized
    assert "suggested_severity_score integer" in normalized
    assert "source_kind text not null" in normalized
    assert "external_id text" in normalized
    assert "incident_topic text" in normalized
    assert "severity_confidence double precision" in normalized
    assert "severity_reasoning text" in normalized
    assert "severity_flags text" in normalized
    assert "severity_model text" in normalized
    assert "severity_decision_source text" in normalized
    assert "legitimacy_score double precision" in normalized
    assert "legitimacy_label text" in normalized
    assert "legitimacy_reasoning text" in normalized
    assert "legitimacy_reasoning_zh text" in normalized
    assert "source_validation_summary text" in normalized
    assert "source_validation_summary_zh text" in normalized
    assert "headline_en text" in normalized
    assert "headline_zh text" in normalized
    assert "company_involved_zh text" in normalized
    assert "reality_summary_en text" in normalized
    assert "reality_summary_zh text" in normalized
    assert "translation_status text" in normalized
    assert "translated_at timestamptz" in normalized
    assert "review_batch_id text" in normalized
    assert "review_model text" in normalized
    assert "duplicate_status text" in normalized
    assert "duplicate_of_incident_id text references incident_logs(id)" in normalized
    assert "canonical_incident_id text references incident_logs(id)" in normalized
    assert "embedding_model text" in normalized
    assert "embedding_vector text" in normalized
    assert "reviewed_at timestamptz" in normalized
    assert "severity_suggested_at timestamptz" in normalized
    assert "canonical_url text" in normalized
    assert "fetch_status text" in normalized
    assert "http_status integer" in normalized
    assert "evidence_text text" in normalized
    assert "create table if not exists incident_duplicate_candidates" in normalized


def test_initial_migration_bootstraps_same_core_tables() -> None:
    migration_path = (
        REPO_ROOT
        / "infra"
        / "supabase"
        / "migrations"
        / "20260429170000_initial_incident_schema.sql"
    )

    migration_sql = migration_path.read_text().lower()

    assert "create table if not exists claims" in migration_sql
    assert "notes text" in migration_sql
    assert "create table if not exists claim_sources" in migration_sql
    assert "create table if not exists incident_logs" in migration_sql
    assert "create table if not exists incident_sources" in migration_sql
    assert "external_id text" in migration_sql
    assert "incident_topic text" in migration_sql
    assert "suggested_severity_score integer" in migration_sql
    assert "legitimacy_score" in migration_sql
    assert "severity_confidence" in migration_sql
    assert "severity_reasoning text" in migration_sql
    assert "severity_flags text" in migration_sql
    assert "severity_model text" in migration_sql
    assert "severity_decision_source text" in migration_sql
    assert "headline_zh text" in migration_sql
    assert "company_involved_zh text" in migration_sql
    assert "legitimacy_reasoning_zh text" in migration_sql
    assert "source_validation_summary_zh text" in migration_sql
    assert "translation_status text" in migration_sql
    assert "review_batch_id text" in migration_sql
    assert "review_model text" in migration_sql
    assert "duplicate_status text" in migration_sql
    assert "embedding_model text" in migration_sql
    assert "create table if not exists incident_duplicate_candidates" in migration_sql
    assert "canonical_url text" in migration_sql


def test_incident_claim_and_source_models_capture_mvp_schema() -> None:
    claim = ClaimRecord(
        id="claim-1",
        claimant_name="OpenAI",
        company_involved="OpenAI",
        original_claim="AI agents can reliably replace entry-level analysts.",
        claim_date=date(2025, 1, 15),
        claim_topic="job automation",
        status="seeded",
        notes="Tracked from product launch remarks.",
    )
    incident = IncidentRecord(
        id="incident-1",
        external_id="inc-openai-001",
        headline="Agent rollout causes bad customer escalations",
        date_logged=date(2026, 4, 29),
        company_involved="OpenAI",
        company_involved_zh="OpenAI 中文",
        incident_topic="job automation",
        claimant_name="OpenAI",
        categories=["Job Automation Fails", "Missed Timelines"],
        severity_score=4,
        suggested_severity_score=3,
        reality_summary="A supervised launch produced repeated escalations.",
        reality_summary_en="A supervised launch produced repeated escalations.",
        reality_summary_zh="一次受监督的发布引发了反复升级。",
        status="pending_editor_review",
        confidence_score=0.82,
        severity_confidence=0.88,
        severity_reasoning="The incident caused meaningful operational disruption that required manual intervention.",
        severity_flags=["core_system_outage"],
        severity_model="gpt-5.4-mini",
        severity_decision_source="editor",
        review_notes="Needs editor confirmation on severity.",
        ingestion_run_id="run-2026-04-29",
        matched_claim_id=claim.id,
        claim_match_confidence=0.76,
        legitimacy_score=0.91,
        legitimacy_label="auto_publish",
        legitimacy_reasoning="Three strong sources support the incident.",
        legitimacy_reasoning_zh="三条强有力的来源支持这起事件。",
        source_validation_summary="Validated 3 distinct sources.",
        source_validation_summary_zh="已核实 3 个不同来源。",
        headline_en="Agent rollout causes bad customer escalations",
        headline_zh="智能体发布导致错误客户升级",
        translation_status="completed",
        import_notes="Imported from 2023 editorial batch.",
        review_batch_id="batch-123",
        review_model="gpt-5.2",
        duplicate_status="suspected",
        duplicate_of_incident_id="incident-0",
        canonical_incident_id="incident-0",
        embedding_model="text-embedding-3-small",
        embedding_vector=[0.1, 0.9],
        created_at=datetime(2026, 4, 29, 12, 0, 0),
        reviewed_at=datetime(2026, 4, 29, 12, 2, 0),
        severity_suggested_at=datetime(2026, 4, 29, 12, 1, 0),
        translated_at=datetime(2026, 4, 29, 12, 3, 0),
        updated_at=datetime(2026, 4, 29, 12, 5, 0),
    )
    source = IncidentSourceRecord(
        id="source-1",
        incident_id=incident.id,
        source_url="https://example.com/report",
        source_type="primary",
        publisher="Example News",
        title="Agent rollout goes sideways",
        published_at=datetime(2026, 4, 29, 8, 0, 0),
        is_primary=True,
    )

    assert claim.status == "seeded"
    assert claim.notes == "Tracked from product launch remarks."
    assert incident.external_id == "inc-openai-001"
    assert incident.incident_topic == "job automation"
    assert incident.matched_claim_id == claim.id
    assert incident.legitimacy_score == 0.91
    assert incident.suggested_severity_score == 3
    assert incident.translation_status == "completed"
    assert incident.review_batch_id == "batch-123"
    assert incident.review_model == "gpt-5.2"
    assert incident.severity_decision_source == "editor"
    assert incident.duplicate_status == "suspected"
    assert incident.canonical_incident_id == "incident-0"
    assert incident.embedding_model == "text-embedding-3-small"
    assert incident.headline_zh == "智能体发布导致错误客户升级"
    assert incident.company_involved_zh == "OpenAI 中文"
    assert incident.legitimacy_reasoning_zh == "三条强有力的来源支持这起事件。"
    assert incident.source_validation_summary_zh == "已核实 3 个不同来源。"
    assert incident.categories == ["Job Automation Fails", "Missed Timelines"]
    assert source.incident_id == incident.id
