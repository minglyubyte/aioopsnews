from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from io import StringIO
from urllib.parse import urlparse

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
