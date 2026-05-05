from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.core.incident_metadata import SourceOrigin

SourceType = Literal["primary", "secondary", "official", "internal"]


class IncidentSourceRecord(BaseModel):
    id: str
    incident_id: str
    source_url: str
    source_type: SourceType
    publisher: str | None = None
    title: str | None = None
    published_at: datetime | None = None
    source_origin: SourceOrigin | None = None
    source_registry_key: str | None = None
    raw_source_payload: dict[str, object] | None = None
    is_primary: bool = False
    created_at: datetime | None = None
