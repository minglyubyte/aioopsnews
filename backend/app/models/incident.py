from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

IncidentStatus = Literal[
    "pending_llm_review",
    "pending_llm_escalation",
    "pending_duplicate_review",
    "pending_review",
    "pending_editor_review",
    "approved",
    "rejected",
    "duplicate_confirmed",
    "needs_rework",
    "draft",
]


class IncidentRecord(BaseModel):
    id: str
    external_id: str | None = None
    headline: str
    headline_en: str | None = None
    headline_zh: str | None = None
    date_logged: date
    company_involved: str
    incident_topic: str | None = None
    claimant_name: str | None = None
    categories: list[str] = Field(default_factory=list)
    severity_score: int = Field(ge=1, le=5)
    suggested_severity_score: int | None = Field(default=None, ge=1, le=5)
    reality_summary: str
    reality_summary_en: str | None = None
    reality_summary_zh: str | None = None
    status: IncidentStatus = "pending_review"
    ingestion_run_id: str | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    severity_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    severity_reasoning: str | None = None
    severity_flags: list[str] = Field(default_factory=list)
    severity_model: str | None = None
    severity_decision_source: str | None = None
    review_notes: str | None = None
    matched_claim_id: str | None = None
    claim_match_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    legitimacy_score: float | None = Field(default=None, ge=0.0, le=1.0)
    legitimacy_label: str | None = None
    legitimacy_reasoning: str | None = None
    legitimacy_reasoning_zh: str | None = None
    source_validation_summary: str | None = None
    source_validation_summary_zh: str | None = None
    legitimacy_flag: str | None = None
    confidence_level: str | None = None
    import_notes: str | None = None
    translation_status: str | None = None
    review_batch_id: str | None = None
    review_model: str | None = None
    duplicate_status: str | None = None
    duplicate_of_incident_id: str | None = None
    canonical_incident_id: str | None = None
    embedding_model: str | None = None
    embedding_vector: list[float] | None = None
    created_at: datetime | None = None
    reviewed_at: datetime | None = None
    severity_suggested_at: datetime | None = None
    translated_at: datetime | None = None
    updated_at: datetime | None = None
