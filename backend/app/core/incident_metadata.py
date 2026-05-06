from __future__ import annotations

from typing import Literal

PublicationTrack = Literal["verified_accident", "accident_watch"]
EvidenceTier = Literal[
    "official_documented",
    "court_or_regulator",
    "company_confirmed",
    "reported_unconfirmed",
    "developing",
]
SourceFamily = Literal[
    "autonomous_vehicle",
    "legal_hallucination",
    "coding_failure",
    "security_privacy",
    "customer_support",
    "healthcare_benefits",
    "education_public_sector",
    "model_governance",
    "other",
]
SourceOrigin = Literal[
    "fixed_verified_source",
    "search_discovery",
    "manual_import",
]

DEFAULT_PUBLICATION_TRACK: PublicationTrack = "accident_watch"
DEFAULT_EVIDENCE_TIER: EvidenceTier = "developing"
DEFAULT_SOURCE_FAMILY: SourceFamily = "other"
DEFAULT_VERIFICATION_SUMMARY = (
    "Evidence metadata has not been classified yet."
)

PUBLICATION_TRACKS: tuple[PublicationTrack, ...] = (
    "verified_accident",
    "accident_watch",
)
EVIDENCE_TIERS: tuple[EvidenceTier, ...] = (
    "official_documented",
    "court_or_regulator",
    "company_confirmed",
    "reported_unconfirmed",
    "developing",
)
SOURCE_FAMILIES: tuple[SourceFamily, ...] = (
    "autonomous_vehicle",
    "legal_hallucination",
    "coding_failure",
    "security_privacy",
    "customer_support",
    "healthcare_benefits",
    "education_public_sector",
    "model_governance",
    "other",
)
SOURCE_ORIGINS: tuple[SourceOrigin, ...] = (
    "fixed_verified_source",
    "search_discovery",
    "manual_import",
)
