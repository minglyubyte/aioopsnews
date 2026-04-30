from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.services.incident_query import (
    IncidentQueryFilters,
    get_filter_values,
    get_public_incident,
    list_public_incidents,
)

router = APIRouter()


class IncidentSourceResponse(BaseModel):
    id: str
    source_url: str
    source_type: str
    publisher: str | None = None
    title: str | None = None


class MatchedClaimResponse(BaseModel):
    id: str
    claimant_name: str
    company_involved: str
    original_claim: str
    claim_date: str
    claim_topic: str
    match_confidence: float


class IncidentFeedItemResponse(BaseModel):
    id: str
    headline: str
    date_logged: str
    company_involved: str
    claimant_name: str | None = None
    categories: list[str]
    severity_score: int
    reality_summary: str
    status: str
    matched_claim: MatchedClaimResponse | None = None
    sources: list[IncidentSourceResponse]


class IncidentFeedResponse(BaseModel):
    items: list[IncidentFeedItemResponse]


class IncidentFilterResponse(BaseModel):
    categories: list[str]
    claimants: list[str]
    companies: list[str]


def get_incident_repository(request: Request):
    return request.app.state.incident_repository


@router.get("/incidents", response_model=IncidentFeedResponse)
def get_incidents(
    category: str | None = None,
    company: str | None = None,
    claimant: str | None = None,
    severity_min: int | None = Query(default=None, ge=1, le=5),
    severity_max: int | None = Query(default=None, ge=1, le=5),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repository=Depends(get_incident_repository),
) -> IncidentFeedResponse:
    return IncidentFeedResponse(
        items=list_public_incidents(
            repository,
            IncidentQueryFilters(
                category=category,
                company=company,
                claimant=claimant,
                severity_min=severity_min,
                severity_max=severity_max,
                page=page,
                page_size=page_size,
            ),
        )
    )


@router.get("/incidents/{incident_id}", response_model=IncidentFeedItemResponse)
def get_incident_detail(
    incident_id: str,
    repository=Depends(get_incident_repository),
) -> IncidentFeedItemResponse:
    incident = get_public_incident(repository, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentFeedItemResponse(**incident)


@router.get("/filters", response_model=IncidentFilterResponse)
def get_filters(repository=Depends(get_incident_repository)) -> IncidentFilterResponse:
    return IncidentFilterResponse(**get_filter_values(repository))
