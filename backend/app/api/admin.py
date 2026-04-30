from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.incidents import IncidentSourceResponse

router = APIRouter(prefix="/admin", tags=["admin"])


ReviewStatus = Literal["pending_review", "approved", "rejected", "needs_rework"]


class AdminIncidentResponse(BaseModel):
    id: str
    headline: str
    date_logged: str
    company_involved: str
    claimant_name: str | None = None
    categories: list[str]
    severity_score: int
    reality_summary: str
    status: str
    matched_claim_id: str | None = None
    claim_match_confidence: float | None = None
    review_notes: str | None = None
    sources: list[IncidentSourceResponse]


class AdminIncidentQueueResponse(BaseModel):
    items: list[AdminIncidentResponse]


class AdminIncidentUpdateRequest(BaseModel):
    status: ReviewStatus
    company_involved: str
    claimant_name: str | None = None
    categories: list[str] = Field(default_factory=list)
    severity_score: int = Field(ge=1, le=5)
    reality_summary: str
    matched_claim_id: str | None = None
    claim_match_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    review_notes: str


def get_incident_repository(request: Request):
    return request.app.state.incident_repository


@router.get("/incidents", response_model=AdminIncidentQueueResponse)
def get_admin_incidents(
    repository=Depends(get_incident_repository),
) -> AdminIncidentQueueResponse:
    return AdminIncidentQueueResponse(items=repository.list_review_queue())


@router.patch("/incidents/{incident_id}", response_model=AdminIncidentResponse)
def patch_admin_incident(
    incident_id: str,
    update: AdminIncidentUpdateRequest,
    repository=Depends(get_incident_repository),
) -> AdminIncidentResponse:
    updated_incident = repository.apply_admin_review(
        incident_id=incident_id,
        status=update.status,
        company_involved=update.company_involved,
        claimant_name=update.claimant_name,
        categories=update.categories,
        severity_score=update.severity_score,
        reality_summary=update.reality_summary,
        matched_claim_id=update.matched_claim_id,
        claim_match_confidence=update.claim_match_confidence,
        review_notes=update.review_notes,
    )
    if updated_incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    return AdminIncidentResponse(**updated_incident)
