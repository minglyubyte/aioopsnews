from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from app.db.postgres_repository import _POSTGRES_SCHEMA
from app.models.claim import ClaimRecord
from app.models.incident import IncidentRecord
from app.models.source import IncidentSourceRecord

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_product_decision_record_captures_mvp_foundation() -> None:
    decision_record = (
        REPO_ROOT / "docs" / "product" / "mvp-foundation-decisions.md"
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
    assert "source_kind text not null" in normalized


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
        headline="Agent rollout causes bad customer escalations",
        date_logged=date(2026, 4, 29),
        company_involved="OpenAI",
        claimant_name="OpenAI",
        categories=["Job Automation Fails", "Missed Timelines"],
        severity_score=4,
        reality_summary="A supervised launch produced repeated escalations.",
        status="pending_review",
        confidence_score=0.82,
        review_notes="Needs editor confirmation on severity.",
        ingestion_run_id="run-2026-04-29",
        matched_claim_id=claim.id,
        claim_match_confidence=0.76,
        created_at=datetime(2026, 4, 29, 12, 0, 0),
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
    assert incident.matched_claim_id == claim.id
    assert incident.categories == ["Job Automation Fails", "Missed Timelines"]
    assert source.incident_id == incident.id
