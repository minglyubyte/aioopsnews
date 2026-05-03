"""Typed dictionary definitions for incident data flowing through the system.

These TypedDicts document the shape of incident dictionaries returned by
the repository layer and consumed by the service layer.  They replace the
pervasive ``dict[str, Any]`` pattern with explicit field declarations,
giving IDE autocompletion and static type-checker coverage.

Usage
-----
Import the appropriate TypedDict as a type annotation::

    from app.models.incident_dict import IncidentDict

    def process(incident: IncidentDict) -> None:
        print(incident["id"])           # ✅  type-safe
        print(incident["nonexistent"])  # ❌  caught by mypy/pyright

All fields marked ``NotRequired`` may be absent from a given dict; callers
should use ``.get()`` for those fields.
"""

from __future__ import annotations

from typing import Any

try:
    from typing import NotRequired, TypedDict
except ImportError:
    # Python 3.10 fallback
    from typing_extensions import NotRequired, TypedDict


# ---------------------------------------------------------------------------
# Source row
# ---------------------------------------------------------------------------

class IncidentSourceDict(TypedDict):
    """A single row from the ``incident_sources`` table."""

    id: str
    source_url: str
    source_type: str
    publisher: str | None
    title: str | None
    canonical_url: NotRequired[str | None]
    fetch_status: NotRequired[str | None]
    http_status: NotRequired[int | None]
    evidence_text: NotRequired[str | None]
    fetch_error: NotRequired[str | None]


# ---------------------------------------------------------------------------
# Duplicate candidate row
# ---------------------------------------------------------------------------

class DuplicateCandidateDict(TypedDict):
    """A single row from ``incident_duplicate_candidates``."""

    candidate_incident_id: str
    embedding_score: float
    llm_verdict: str
    confidence: float
    reasoning: str | None
    status: str


# ---------------------------------------------------------------------------
# Core incident (fields present in every serialization)
# ---------------------------------------------------------------------------

class IncidentBaseDict(TypedDict):
    """Fields common to virtually every incident serialization."""

    id: str
    headline: str
    date_logged: str
    company_involved: str
    claimant_name: str | None
    categories: list[str]
    severity_score: int
    reality_summary: str
    status: str
    headline_en: NotRequired[str | None]
    headline_zh: NotRequired[str | None]
    incident_topic: NotRequired[str | None]
    reality_summary_en: NotRequired[str | None]
    reality_summary_zh: NotRequired[str | None]


# ---------------------------------------------------------------------------
# Internal incident (full detail, returned by get_incident)
# ---------------------------------------------------------------------------

class IncidentDict(TypedDict, total=False):
    """Full incident shape used internally by the service layer.

    All fields from the base plus review metadata, duplicate info, embeddings,
    sources, and translation fields.  ``total=False`` is used because different
    serialization paths include different subsets of fields.
    """

    # ── identity ──────────────────────────────────────────────────────────
    id: str
    external_id: str | None
    headline: str
    headline_en: str | None
    headline_zh: str | None
    date_logged: str
    company_involved: str
    company_involved_zh: str | None
    incident_topic: str | None
    claimant_name: str | None
    categories: list[str]
    severity_score: int
    suggested_severity_score: int | None
    reality_summary: str
    reality_summary_en: str | None
    reality_summary_zh: str | None
    status: str

    # ── review metadata ───────────────────────────────────────────────────
    review_notes: str | None
    matched_claim_id: str | None
    claim_match_confidence: float | None
    legitimacy_score: float | None
    legitimacy_label: str | None
    legitimacy_reasoning: str | None
    legitimacy_reasoning_zh: str | None
    source_validation_summary: str | None
    source_validation_summary_zh: str | None
    severity_confidence: float | None
    severity_reasoning: str | None
    severity_flags: list[str]
    severity_model: str | None
    severity_decision_source: str | None

    # ── forensic analysis fields ──────────────────────────────────────────
    incident_summary_en: str | None
    incident_summary_zh: str | None
    what_happened_en: str | None
    what_happened_zh: str | None
    ai_failure_point_en: str | None
    ai_failure_point_zh: str | None
    why_it_matters_en: str | None
    why_it_matters_zh: str | None
    evidence_summary_en: str | None
    evidence_summary_zh: str | None

    # ── ingestion / review pipeline ───────────────────────────────────────
    legitimacy_flag: str | None
    confidence_level: str | None
    import_notes: str | None
    translation_status: str | None
    review_batch_id: str | None
    review_model: str | None

    # ── duplicate detection ───────────────────────────────────────────────
    duplicate_status: str | None
    duplicate_of_incident_id: str | None
    canonical_incident_id: str | None
    embedding_model: str | None
    embedding_vector: list[float] | None

    # ── relations (populated by serializers) ──────────────────────────────
    sources: list[IncidentSourceDict]
    duplicate_candidates: list[DuplicateCandidateDict]


# ---------------------------------------------------------------------------
# Public-facing shapes (subset for API consumers)
# ---------------------------------------------------------------------------

class PublicArchiveItemDict(TypedDict):
    """Shape returned by ``serialize_public_archive_row``."""

    id: str
    headline: str
    headline_en: str
    headline_zh: str | None
    date_logged: str
    company_involved: str
    company_involved_zh: NotRequired[str | None]
    incident_topic: str | None
    claimant_name: str | None
    categories: list[str]
    severity_score: int
    archive_summary: str
    archive_summary_en: str
    archive_summary_zh: str | None
    status: str
    translation_status: str | None


class PublicClaimPayloadDict(TypedDict):
    """Shape for the ``matched_claim`` field in public detail view."""

    id: str
    claimant_name: str
    company_involved: str
    original_claim: str
    claim_date: str
    claim_topic: str
    match_confidence: float


class IncidentAnalysisDict(TypedDict):
    """The ``analysis`` sub-object in a public incident detail."""

    incident_summary_en: str | None
    incident_summary_zh: str | None
    what_happened_en: str | None
    what_happened_zh: str | None
    ai_failure_point_en: str | None
    ai_failure_point_zh: str | None
    why_it_matters_en: str | None
    why_it_matters_zh: str | None
    evidence_summary_en: str | None
    evidence_summary_zh: str | None


class PublicDetailDict(TypedDict):
    """Shape returned by ``serialize_public_detail_row``."""

    id: str
    headline: str
    headline_en: str
    headline_zh: str | None
    date_logged: str
    company_involved: str
    company_involved_zh: str | None
    incident_topic: str | None
    claimant_name: str | None
    categories: list[str]
    severity_score: int
    reality_summary: str
    reality_summary_en: str
    reality_summary_zh: str | None
    status: str
    translation_status: str | None
    analysis: IncidentAnalysisDict
    matched_claim: PublicClaimPayloadDict | None
    sources: list[IncidentSourceDict]
