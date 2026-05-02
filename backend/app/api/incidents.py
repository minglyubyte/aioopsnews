from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.services.incident_query import (
    IncidentQueryFilters,
    get_filter_values,
    get_public_incident,
    list_public_incident_feed,
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


class PublicIncidentBaseResponse(BaseModel):
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
    status: str
    translation_status: str | None = None


class IncidentArchiveItemResponse(PublicIncidentBaseResponse):
    archive_summary: str
    archive_summary_en: str | None = None
    archive_summary_zh: str | None = None


class IncidentAnalysisResponse(BaseModel):
    incident_summary_en: str | None = None
    incident_summary_zh: str | None = None
    what_happened_en: str | None = None
    what_happened_zh: str | None = None
    ai_failure_point_en: str | None = None
    ai_failure_point_zh: str | None = None
    why_it_matters_en: str | None = None
    why_it_matters_zh: str | None = None
    evidence_summary_en: str | None = None
    evidence_summary_zh: str | None = None


class IncidentDetailResponse(PublicIncidentBaseResponse):
    reality_summary: str
    reality_summary_en: str | None = None
    reality_summary_zh: str | None = None
    analysis: IncidentAnalysisResponse
    matched_claim: MatchedClaimResponse | None = None
    sources: list[IncidentSourceResponse]


class IncidentFeedResponse(BaseModel):
    items: list[IncidentArchiveItemResponse]
    page: int
    page_size: int
    total_count: int
    total_pages: int
    has_next_page: bool
    has_previous_page: bool
    slice_summary: dict[str, object]


class IncidentFilterResponse(BaseModel):
    categories: list[str]
    claimants: list[str]
    companies: list[str]
    company_labels_zh: dict[str, str | None]
    years: list[int]
    months_by_year: dict[str, list[int]]


def get_incident_repository(request: Request):
    return request.app.state.incident_repository


@router.get("/incidents", response_model=IncidentFeedResponse)
def get_incidents(
    category: str | None = None,
    company: str | None = None,
    claimant: str | None = None,
    severity_min: int | None = Query(default=None, ge=1, le=5),
    severity_max: int | None = Query(default=None, ge=1, le=5),
    year: int | None = Query(default=None, ge=1900, le=3000),
    month: int | None = Query(default=None, ge=1, le=12),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repository=Depends(get_incident_repository),
) -> IncidentFeedResponse:
    if month is not None and year is None:
        raise HTTPException(status_code=422, detail="month requires year")

    return IncidentFeedResponse(
        **list_public_incident_feed(
            repository,
            IncidentQueryFilters(
                category=category,
                company=company,
                claimant=claimant,
                severity_min=severity_min,
                severity_max=severity_max,
                year=year,
                month=month,
                page=page,
                page_size=page_size,
            ),
        )
    )


@router.get("/incidents/{incident_id}", response_model=IncidentDetailResponse)
def get_incident_detail(
    incident_id: str,
    repository=Depends(get_incident_repository),
) -> IncidentDetailResponse:
    incident = get_public_incident(repository, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentDetailResponse(**incident)


@router.get("/filters", response_model=IncidentFilterResponse)
def get_filters(repository=Depends(get_incident_repository)) -> IncidentFilterResponse:
    return IncidentFilterResponse(**get_filter_values(repository))
