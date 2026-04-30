from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.models.claim import ClaimRecord

INTERNAL_CLAIM_MATCH_THRESHOLD = 0.8
PUBLIC_CLAIM_MATCH_THRESHOLD = 0.85

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "before",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "our",
    "the",
    "their",
    "to",
    "will",
    "without",
}


@dataclass(frozen=True)
class ClaimMatch:
    claim: ClaimRecord
    confidence: float


def match_incident_to_claim(
    *,
    claims: list[ClaimRecord],
    headline: str,
    source_summary: str,
    company_involved: str,
    categories: list[str],
    incident_date: date,
) -> ClaimMatch | None:
    incident_tokens = _tokenize(" ".join([headline, source_summary, *categories]))
    normalized_company = _normalize(company_involved)

    best_match: ClaimMatch | None = None

    for claim in claims:
        claim_company = _normalize(claim.company_involved)
        if claim_company != normalized_company:
            continue
        if claim.claim_date > incident_date:
            continue

        score = 0.6
        overlap = incident_tokens & _tokenize(claim.original_claim)
        if overlap:
            score += min(0.26, 0.13 * len(overlap))

        score += 0.05
        bounded_score = min(score, 0.99)

        if bounded_score < INTERNAL_CLAIM_MATCH_THRESHOLD:
            continue

        candidate = ClaimMatch(claim=claim, confidence=round(bounded_score, 2))
        if best_match is None or candidate.confidence > best_match.confidence:
            best_match = candidate

    return best_match


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 2 and token not in _STOPWORDS
    }
