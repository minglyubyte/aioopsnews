from __future__ import annotations

from hmac import compare_digest
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.incidents import IncidentAnalysisResponse, IncidentSourceResponse
from app.core.config import Settings
from app.services.incident_translation import translate_incident_copy

router = APIRouter(prefix="/admin", tags=["admin"])


ReviewStatus = Literal[
    "pending_review",
    "approved",
    "rejected",
    "needs_rework",
]


class AdminIncidentResponse(BaseModel):
    id: str
    headline: str
    headline_en: str | None = None
    headline_zh: str | None = None
    date_logged: str
    company_involved: str
    company_involved_zh: str | None = None
    incident_topic: str | None = None
    claimant_name: str | None = None
    categories: list[str]
    severity_score: int
    suggested_severity_score: int | None = None
    severity_confidence: float | None = None
    severity_reasoning: str | None = None
    severity_flags: list[str] = Field(default_factory=list)
    severity_model: str | None = None
    severity_decision_source: str | None = None
    reality_summary: str
    reality_summary_en: str | None = None
    reality_summary_zh: str | None = None
    status: str
    publication_track: str
    evidence_tier: str
    source_family: str
    verification_summary: str
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
    duplicate_status: str | None = None
    duplicate_of_incident_id: str | None = None
    canonical_incident_id: str | None = None
    duplicate_candidates: list[dict[str, object]] = Field(default_factory=list)
    sources: list[IncidentSourceResponse]
    analysis: IncidentAnalysisResponse | None = None


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

    if updated_incident["status"] == "approved":
        translation = translate_incident_copy(
            company_involved_en=updated_incident["company_involved"],
            headline_en=updated_incident["headline"],
            reality_summary_en=updated_incident["reality_summary"],
            legitimacy_reasoning_en=updated_incident.get("legitimacy_reasoning") or "",
            source_validation_summary_en=(
                updated_incident.get("source_validation_summary") or ""
            ),
            incident_summary_en=updated_incident.get("incident_summary_en") or "",
            what_happened_en=updated_incident.get("what_happened_en") or "",
            ai_failure_point_en=updated_incident.get("ai_failure_point_en") or "",
            why_it_matters_en=updated_incident.get("why_it_matters_en") or "",
            evidence_summary_en=updated_incident.get("evidence_summary_en") or "",
            client=translation_client,
        )
        translated_incident = repository.update_incident_translation(
            incident_id=incident_id,
            company_involved_zh=translation.company_involved_zh,
            headline_zh=translation.headline_zh,
            reality_summary_zh=translation.reality_summary_zh,
            legitimacy_reasoning_zh=translation.legitimacy_reasoning_zh,
            source_validation_summary_zh=translation.source_validation_summary_zh,
            translation_status=translation.status,
            translated_at="2026-04-30T12:00:00",
            incident_summary_zh=translation.incident_summary_zh,
            what_happened_zh=translation.what_happened_zh,
            ai_failure_point_zh=translation.ai_failure_point_zh,
            why_it_matters_zh=translation.why_it_matters_zh,
            evidence_summary_zh=translation.evidence_summary_zh,
        )
        if translated_incident is not None:
            updated_incident = translated_incident

    return AdminIncidentResponse(**updated_incident)


@router.post(
    "/incidents/{incident_id}/upgrade-to-accident",
    response_model=AdminIncidentResponse,
)
def upgrade_admin_incident_to_accident(
    incident_id: str,
    _authorized: None = Depends(require_admin_token),
    repository=Depends(get_incident_repository),
) -> AdminIncidentResponse:
    upgraded_incident = repository.upgrade_watch_incident_to_verified_accident(
        incident_id
    )
    if upgraded_incident is None:
        raise HTTPException(status_code=404, detail="AI news item not found")
    return AdminIncidentResponse(**upgraded_incident)
