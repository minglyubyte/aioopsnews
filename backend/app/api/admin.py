from __future__ import annotations

from hmac import compare_digest
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.incidents import IncidentSourceResponse
from app.core.config import Settings
from app.services.incident_translation import translate_incident_copy

router = APIRouter(prefix="/admin", tags=["admin"])


ReviewStatus = Literal["pending_review", "approved", "rejected", "needs_rework"]


class AdminIncidentResponse(BaseModel):
    id: str
    headline: str
    headline_en: str | None = None
    headline_zh: str | None = None
    date_logged: str
    company_involved: str
    incident_topic: str | None = None
    claimant_name: str | None = None
    categories: list[str]
    severity_score: int
    reality_summary: str
    reality_summary_en: str | None = None
    reality_summary_zh: str | None = None
    status: str
    matched_claim_id: str | None = None
    claim_match_confidence: float | None = None
    review_notes: str | None = None
    legitimacy_score: float | None = None
    legitimacy_label: str | None = None
    legitimacy_reasoning: str | None = None
    source_validation_summary: str | None = None
    translation_status: str | None = None
    review_batch_id: str | None = None
    review_model: str | None = None
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


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_translation_client(request: Request):
    return request.app.state.incident_translation_client


def require_admin_token(
    x_admin_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if x_admin_token is None or not compare_digest(
        x_admin_token,
        settings.admin_api_token,
    ):
        raise HTTPException(status_code=401, detail="Admin access required")


@router.get("/incidents", response_model=AdminIncidentQueueResponse)
def get_admin_incidents(
    _authorized: None = Depends(require_admin_token),
    repository=Depends(get_incident_repository),
) -> AdminIncidentQueueResponse:
    return AdminIncidentQueueResponse(items=repository.list_review_queue())


@router.patch("/incidents/{incident_id}", response_model=AdminIncidentResponse)
def patch_admin_incident(
    incident_id: str,
    update: AdminIncidentUpdateRequest,
    _authorized: None = Depends(require_admin_token),
    repository=Depends(get_incident_repository),
    translation_client=Depends(get_translation_client),
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

    if (
        updated_incident["status"] == "approved"
        and updated_incident.get("translation_status") != "completed"
    ):
        translation = translate_incident_copy(
            headline_en=updated_incident.get("headline_en")
            or updated_incident["headline"],
            reality_summary_en=updated_incident.get("reality_summary_en")
            or updated_incident["reality_summary"],
            client=translation_client,
        )
        translated_incident = repository.update_incident_translation(
            incident_id=incident_id,
            headline_zh=translation.headline_zh,
            reality_summary_zh=translation.reality_summary_zh,
            translation_status=translation.status,
            translated_at="2026-04-30T12:00:00",
        )
        if translated_incident is not None:
            updated_incident = translated_incident

    return AdminIncidentResponse(**updated_incident)
