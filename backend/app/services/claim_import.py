from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from io import StringIO
from urllib.parse import urlparse
from uuid import UUID, uuid4

from app.db.repository_protocol import IncidentRepository

ALLOWED_CLAIM_STATUSES = {
    "seeded",
    "pending_review",
    "approved",
    "rejected",
    "archived",
}

REQUIRED_COLUMNS = {
    "claimant_name",
    "company_involved",
    "original_claim",
    "claim_date",
    "claim_topic",
}


class ClaimImportValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedClaimImportRow:
    line_number: int
    claim_id: str | None
    claimant_name: str
    company_involved: str
    original_claim: str
    claim_date: str
    claim_topic: str
    status: str | None
    primary_source_links: list[str]
    secondary_source_links: list[str]
    notes: str | None


@dataclass(frozen=True)
class ClaimImportSummary:
    validated: int
    inserted: int


def parse_claims_csv_text(csv_text: str) -> list[ParsedClaimImportRow]:
    reader = csv.DictReader(StringIO(csv_text))
    fieldnames = set(reader.fieldnames or [])
    missing_columns = REQUIRED_COLUMNS - fieldnames
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ClaimImportValidationError(f"Missing required CSV columns: {missing}")

    rows: list[ParsedClaimImportRow] = []
    seen_ids: set[str] = set()
    for line_number, raw_row in enumerate(reader, start=2):
        row = {key: (value or "").strip() for key, value in raw_row.items()}
        if not any(row.values()):
            continue

        for column in REQUIRED_COLUMNS:
            if not row[column]:
                raise ClaimImportValidationError(
                    f"Invalid claim import at line {line_number}: {column} is required"
                )

        if row.get("status") and row["status"] not in ALLOWED_CLAIM_STATUSES:
            raise ClaimImportValidationError(
                f"Invalid claim import at line {line_number}: status must be one of "
                f"{', '.join(sorted(ALLOWED_CLAIM_STATUSES))}"
            )

        _validate_iso_date(row["claim_date"], line_number)
        primary_links = _parse_link_list(
            row.get("primary_source_links", ""),
            line_number=line_number,
        )
        secondary_links = _parse_link_list(
            row.get("secondary_source_links", ""),
            line_number=line_number,
        )

        claim_id = row.get("id") or None
        if claim_id:
            _validate_uuid(claim_id, line_number)
            if claim_id in seen_ids:
                raise ClaimImportValidationError(
                    "Invalid claim import at line "
                    f"{line_number}: duplicate id {claim_id}"
                )
            seen_ids.add(claim_id)

        rows.append(
            ParsedClaimImportRow(
                line_number=line_number,
                claim_id=claim_id,
                claimant_name=row["claimant_name"],
                company_involved=row["company_involved"],
                original_claim=row["original_claim"],
                claim_date=row["claim_date"],
                claim_topic=row["claim_topic"],
                status=row.get("status") or None,
                primary_source_links=primary_links,
                secondary_source_links=secondary_links,
                notes=row.get("notes") or None,
            )
        )

    return rows


def import_claims_csv_text(
    repository: IncidentRepository,
    csv_text: str,
    *,
    dry_run: bool,
    default_status: str = "approved",
) -> ClaimImportSummary:
    if default_status not in ALLOWED_CLAIM_STATUSES:
        raise ClaimImportValidationError(
            f"default_status must be one of {', '.join(sorted(ALLOWED_CLAIM_STATUSES))}"
        )

    rows = parse_claims_csv_text(csv_text)
    if dry_run:
        return ClaimImportSummary(validated=len(rows), inserted=0)

    inserted = 0
    for row in rows:
        claim_id = row.claim_id or _generate_claim_id()
        repository.upsert_claim_import_row(
            claim_id=claim_id,
            claimant_name=row.claimant_name,
            company_involved=row.company_involved,
            original_claim=row.original_claim,
            claim_date=row.claim_date,
            claim_topic=row.claim_topic,
            status=row.status or default_status,
            notes=row.notes,
            primary_source_links=row.primary_source_links,
            secondary_source_links=row.secondary_source_links,
        )
        inserted += 1

    return ClaimImportSummary(validated=len(rows), inserted=inserted)


def _parse_link_list(value: str, *, line_number: int) -> list[str]:
    if not value:
        return []

    deduped: list[str] = []
    seen: set[str] = set()
    for item in value.split("|"):
        link = item.strip()
        if not link:
            continue
        parsed = urlparse(link)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ClaimImportValidationError(
                f"Invalid claim import at line {line_number}: "
                f"{link} must be a valid http:// or https:// URL"
            )
        if link not in seen:
            seen.add(link)
            deduped.append(link)

    return deduped


def _validate_iso_date(value: str, line_number: int) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ClaimImportValidationError(
            f"Invalid claim import at line {line_number}: "
            "claim_date must use YYYY-MM-DD"
        )


def _validate_uuid(value: str, line_number: int) -> None:
    try:
        UUID(value)
    except ValueError as exc:
        raise ClaimImportValidationError(
            f"Invalid claim import at line {line_number}: id must be a UUID"
        ) from exc


def _generate_claim_id() -> str:
    return str(uuid4())
