from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from io import StringIO
from urllib.parse import urlparse

from app.core.incident_metadata import (
    EVIDENCE_TIERS,
    PUBLICATION_TRACKS,
    SOURCE_FAMILIES,
    SOURCE_ORIGINS,
)
from app.db.repository_protocol import IncidentRepository

ALLOWED_LEGITIMACY_FLAGS = {"ACCEPT", "REVIEW", "REJECT"}
ALLOWED_CONFIDENCE_LEVELS = {"low", "medium", "high"}
REQUIRED_COLUMNS = {
    "incident_id",
    "company",
    "incident_date",
    "incident_topic",
    "incident_description",
    "source_links",
    "legitimacy_flag",
    "confidence_level",
}


class IncidentImportValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedIncidentImportRow:
    line_number: int
    ref_number: str | None
    incident_id: str
    company: str
    incident_date: str
    incident_topic: str
    incident_description: str
    mapped_claim: str | None
    source_links: list[str]
    legitimacy_flag: str
    confidence_level: str
    publication_track: str | None
    evidence_tier: str | None
    source_family: str | None
    verification_summary: str | None
    source_origin: str | None
    source_registry_key: str | None
    primary_source_evidence_text: str | None
    primary_source_raw_payload: dict[str, object] | None
    notes: str | None


@dataclass(frozen=True)
class IncidentImportSummary:
    validated: int
    inserted: int
    approved: int
    pending_review: int
    pending_llm_review: int


def parse_incidents_csv_text(csv_text: str) -> list[ParsedIncidentImportRow]:
    reader = csv.DictReader(StringIO(csv_text))
    fieldnames = set(reader.fieldnames or [])
    missing_columns = REQUIRED_COLUMNS - fieldnames
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise IncidentImportValidationError(
            f"Missing required CSV columns: {missing}"
        )

    rows: list[ParsedIncidentImportRow] = []
    seen_incident_ids: set[str] = set()
    for line_number, raw_row in enumerate(reader, start=2):
        row = {key: (value or "").strip() for key, value in raw_row.items()}
        if not any(row.values()):
            continue

        for column in REQUIRED_COLUMNS:
            if not row[column]:
                raise IncidentImportValidationError(
                    "Invalid incident import at line "
                    f"{line_number}: {column} is required"
                )

        _validate_iso_date(row["incident_date"], line_number)
        source_links = _parse_source_links(
            row["source_links"],
            line_number=line_number,
        )
        if len(source_links) < 3:
            raise IncidentImportValidationError(
                "Invalid incident import at line "
                f"{line_number}: source_links must contain at least 3 "
                "distinct valid URLs"
            )

        incident_id = row["incident_id"]
        if incident_id in seen_incident_ids:
            raise IncidentImportValidationError(
                "Invalid incident import at line "
                f"{line_number}: duplicate incident_id {incident_id}"
            )
        seen_incident_ids.add(incident_id)

        legitimacy_flag = row["legitimacy_flag"]
        if legitimacy_flag not in ALLOWED_LEGITIMACY_FLAGS:
            raise IncidentImportValidationError(
                "Invalid incident import at line "
                f"{line_number}: legitimacy_flag must be one of "
                f"{', '.join(sorted(ALLOWED_LEGITIMACY_FLAGS))}"
            )

        confidence_level = row["confidence_level"]
        if confidence_level not in ALLOWED_CONFIDENCE_LEVELS:
            raise IncidentImportValidationError(
                "Invalid incident import at line "
                f"{line_number}: confidence_level must be one of "
                f"{', '.join(sorted(ALLOWED_CONFIDENCE_LEVELS))}"
            )

        publication_track = _parse_optional_choice(
            row.get("publication_track"),
            allowed=PUBLICATION_TRACKS,
            column="publication_track",
            line_number=line_number,
        )
        evidence_tier = _parse_optional_choice(
            row.get("evidence_tier"),
            allowed=EVIDENCE_TIERS,
            column="evidence_tier",
            line_number=line_number,
        )
        source_family = _parse_optional_choice(
            row.get("source_family"),
            allowed=SOURCE_FAMILIES,
            column="source_family",
            line_number=line_number,
        )
        source_origin = _parse_optional_choice(
            row.get("source_origin"),
            allowed=SOURCE_ORIGINS,
            column="source_origin",
            line_number=line_number,
        )
        primary_source_raw_payload = _parse_optional_json_object(
            row.get("primary_source_raw_payload_json"),
            column="primary_source_raw_payload_json",
            line_number=line_number,
        )

        rows.append(
            ParsedIncidentImportRow(
                line_number=line_number,
                ref_number=row.get("ref_number") or None,
                incident_id=incident_id,
                company=row["company"],
                incident_date=row["incident_date"],
                incident_topic=row["incident_topic"],
                incident_description=row["incident_description"],
                mapped_claim=row.get("mapped_claim") or None,
                source_links=source_links,
                legitimacy_flag=legitimacy_flag,
                confidence_level=confidence_level,
                publication_track=publication_track,
                evidence_tier=evidence_tier,
                source_family=source_family,
                verification_summary=row.get("verification_summary") or None,
                source_origin=source_origin,
                source_registry_key=row.get("source_registry_key") or None,
                primary_source_evidence_text=(
                    row.get("primary_source_evidence_text") or None
                ),
                primary_source_raw_payload=primary_source_raw_payload,
                notes=row.get("notes") or None,
            )
        )

    return rows


def import_incidents_csv_text(
    repository: IncidentRepository,
    csv_text: str,
    *,
    dry_run: bool,
) -> IncidentImportSummary:
    rows = parse_incidents_csv_text(csv_text)
    if dry_run:
        return IncidentImportSummary(
            validated=len(rows),
            inserted=0,
            approved=0,
            pending_review=0,
            pending_llm_review=0,
        )

    existing_claim_ids = {claim.id for claim in repository.list_claims()}
    inserted = 0
    pending_review = 0
    approved = 0
    pending_llm_review = 0

    for row in rows:
        status = "pending_llm_review"
        matched_claim_id = (
            row.mapped_claim if row.mapped_claim in existing_claim_ids else None
        )
        source_evidence_texts = _primary_source_values(
            row.source_links,
            row.primary_source_evidence_text,
        )
        raw_source_payloads = _primary_source_values(
            row.source_links,
            row.primary_source_raw_payload,
        )

        repository.upsert_incident_import_row(
            external_id=row.incident_id,
            headline=_build_headline(row),
            date_logged=row.incident_date,
            company_involved=row.company,
            incident_topic=row.incident_topic,
            reality_summary=row.incident_description,
            status=status,
            source_links=row.source_links,
            legitimacy_score=None,
            legitimacy_label=None,
            legitimacy_reasoning=(
                "Imported from curated CSV; awaiting source verification and "
                "LLM legitimacy review."
            ),
            source_validation_summary=(
                f"Validated {len(row.source_links)} distinct sources."
            ),
            legitimacy_flag=row.legitimacy_flag,
            confidence_level=row.confidence_level,
            import_notes=row.notes,
            matched_claim_id=matched_claim_id,
            headline_zh=None,
            reality_summary_zh=None,
            translation_status="not_requested",
            publication_track=row.publication_track,
            evidence_tier=row.evidence_tier,
            source_family=row.source_family,
            verification_summary=row.verification_summary,
            source_origin=row.source_origin,
            source_registry_key=row.source_registry_key,
            source_evidence_texts=source_evidence_texts,
            raw_source_payloads=raw_source_payloads,
        )
        inserted += 1
        pending_llm_review += 1

    return IncidentImportSummary(
        validated=len(rows),
        inserted=inserted,
        approved=approved,
        pending_review=pending_review,
        pending_llm_review=pending_llm_review,
    )


def _parse_source_links(value: str, *, line_number: int) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in value.split("|"):
        link = item.strip()
        if not link:
            continue
        parsed = urlparse(link)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise IncidentImportValidationError(
                "Invalid incident import at line "
                f"{line_number}: {link} must be a valid "
                "http:// or https:// URL"
            )
        if link not in seen:
            seen.add(link)
            deduped.append(link)
    return deduped


def _parse_optional_choice(
    value: str | None,
    *,
    allowed: set[str],
    column: str,
    line_number: int,
) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip()
    if normalized not in allowed:
        raise IncidentImportValidationError(
            "Invalid incident import at line "
            f"{line_number}: {column} must be one of "
            f"{', '.join(sorted(allowed))}"
        )
    return normalized


def _parse_optional_json_object(
    value: str | None,
    *,
    column: str,
    line_number: int,
) -> dict[str, object] | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise IncidentImportValidationError(
            "Invalid incident import at line "
            f"{line_number}: {column} must be valid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise IncidentImportValidationError(
            "Invalid incident import at line "
            f"{line_number}: {column} must be a JSON object"
        )
    return parsed


def _primary_source_values(
    source_links: list[str],
    value: object | None,
) -> list[object | None] | None:
    if value is None:
        return None
    return [value, *([None] * (len(source_links) - 1))]


def _validate_iso_date(value: str, line_number: int) -> None:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise IncidentImportValidationError(
            "Invalid incident import at line "
            f"{line_number}: incident_date must be a real YYYY-MM-DD date"
        ) from exc


def _build_headline(row: ParsedIncidentImportRow) -> str:
    return f"{row.company}: {row.incident_description}"
