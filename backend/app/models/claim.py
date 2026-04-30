from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

ClaimStatus = Literal["seeded", "pending_review", "approved", "rejected", "archived"]


class ClaimRecord(BaseModel):
    id: str
    claimant_name: str
    company_involved: str
    original_claim: str
    claim_date: date
    claim_topic: str
    status: ClaimStatus = "seeded"
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
