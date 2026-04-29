from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SourceType = Literal["primary", "secondary", "official", "internal"]


class IncidentSourceRecord(BaseModel):
    id: str
    incident_id: str
    source_url: str
    source_type: SourceType
    publisher: str | None = None
    title: str | None = None
    published_at: datetime | None = None
    is_primary: bool = False
    created_at: datetime | None = None
