from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

IncidentStatus = Literal[
    "pending_review",
    "approved",
    "rejected",
    "needs_rework",
    "draft",
]


class IncidentRecord(BaseModel):
    id: str
    headline: str
    date_logged: date
    company_involved: str
    claimant_name: str | None = None
    categories: list[str] = Field(default_factory=list)
    severity_score: int = Field(ge=1, le=5)
    reality_summary: str
    status: IncidentStatus = "pending_review"
    ingestion_run_id: str | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    review_notes: str | None = None
    matched_claim_id: str | None = None
    claim_match_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    created_at: datetime | None = None
    updated_at: datetime | None = None
