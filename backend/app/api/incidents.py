from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.services.incident_query import get_filter_values, list_public_incidents

router = APIRouter()


class IncidentSourceResponse(BaseModel):
    id: str
    source_url: str
    source_type: str
    publisher: str | None = None
    title: str | None = None


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
def get_incidents(repository=Depends(get_incident_repository)) -> IncidentFeedResponse:
    return IncidentFeedResponse(items=list_public_incidents(repository))


@router.get("/filters", response_model=IncidentFilterResponse)
def get_filters(repository=Depends(get_incident_repository)) -> IncidentFilterResponse:
    return IncidentFilterResponse(**get_filter_values(repository))
