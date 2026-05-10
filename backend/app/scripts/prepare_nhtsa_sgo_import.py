from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

from app.db.repository_protocol import IncidentRepository
from app.scripts.generate_verified_source_csv import records_to_incident_csv
from app.scrapers.verified_sources import NHTSA_SGO_URL
from app.workflows.dual_track_ingestion import VerifiedSourceRecord


DEFAULT_INPUT_DIR = Path("app/imports/nhtsa")
DEFAULT_OUTPUT_PATH = Path("app/imports/inbox/verified-source-nhtsa-tesla.csv")
NO_NEW_REPORT_TYPE = "No New or Updated Incident Reports"
VERIFIED_NOT_ENGAGED = "Verified Not Engaged"
NHTSA_EVIDENCE_FIELDNAMES = [
    "primary_source_evidence_text",
    "primary_source_raw_payload_json",
]


@dataclass(frozen=True)
class _PreparedNhtsaRow:
    source_kind: str
    source_file: str
    row: dict[str, str]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a Tesla-first NHTSA SGO incident import CSV."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory containing NHTSA SGO CSV exports.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output incident import CSV path.",
    )
    parser.add_argument(
        "--company-filter",
        default="tesla",
        help="Case-insensitive company/make substring to include.",
    )
    parser.add_argument(
        "--include-verified-not-engaged",
        action="store_true",
        help="Include rows whose latest report says automation was not engaged.",
    )
    args = parser.parse_args()

    records = prepare_nhtsa_sgo_records(
        input_dir=args.input_dir,
        company_filter=args.company_filter,
        exclude_verified_not_engaged=not args.include_verified_not_engaged,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(records_to_nhtsa_import_csv(records), encoding="utf-8")
    print(f"wrote={args.out} records={len(records)}")
    return 0


def prepare_nhtsa_sgo_records(
    *,
    input_dir: Path,
    company_filter: str = "tesla",
    exclude_verified_not_engaged: bool = True,
) -> list[VerifiedSourceRecord]:
    latest_rows: dict[str, tuple[tuple[float, str, str, int], _PreparedNhtsaRow]] = {}
    for csv_path in sorted(input_dir.glob("SGO-2021-01_Incident_Reports_*.csv")):
        source_kind = _source_kind_from_filename(csv_path.name)
        for row in _read_csv_rows(csv_path):
            report_id = _field(row, "Report ID")
            if not report_id:
                continue
            if _field(row, "Report Type") == NO_NEW_REPORT_TYPE:
                continue
            sort_key = (
                _parse_report_version(_field(row, "Report Version")),
                _sortable_date(_field(row, "Report Submission Date")),
                _sortable_date(_field(row, "Incident Date")),
                _source_kind_priority(source_kind),
            )
            prepared = _PreparedNhtsaRow(
                source_kind=source_kind,
                source_file=csv_path.name,
                row=row,
            )
            if report_id not in latest_rows or sort_key > latest_rows[report_id][0]:
                latest_rows[report_id] = (sort_key, prepared)

    records: list[VerifiedSourceRecord] = []
    company_filter_lower = company_filter.lower()
    for _, prepared in sorted(latest_rows.values(), key=lambda item: item[0]):
        row = prepared.row
        company = _field(row, "Reporting Entity") or "Unknown vehicle operator"
        make = _field(row, "Make")
        if company_filter_lower not in f"{company} {make}".lower():
            continue
        engagement_status = _engagement_status(row)
        if exclude_verified_not_engaged and engagement_status == VERIFIED_NOT_ENGAGED:
            continue
        records.append(_record_from_prepared_row(prepared))
    return records


def records_to_nhtsa_import_csv(records: list[VerifiedSourceRecord]) -> str:
    base_csv = records_to_incident_csv(records)
    reader = csv.DictReader(StringIO(base_csv))
    fieldnames = [*(reader.fieldnames or []), *NHTSA_EVIDENCE_FIELDNAMES]
    records_by_external_id = {record.external_id: record for record in records}
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in reader:
        record = records_by_external_id[row["incident_id"]]
        row["primary_source_evidence_text"] = nhtsa_csv_evidence_text(record)
        row["primary_source_raw_payload_json"] = json.dumps(
            record.raw_payload,
            ensure_ascii=False,
            sort_keys=True,
        )
        writer.writerow(row)
    return output.getvalue()


def nhtsa_csv_evidence_text(record: VerifiedSourceRecord) -> str:
    payload = record.raw_payload
    fields = [
        ("Report ID", _payload_field(payload, "Report ID") or record.external_id),
        ("Report Version", _payload_field(payload, "Report Version")),
        ("Report Type", _payload_field(payload, "Report Type")),
        ("Reporting Entity", _payload_field(payload, "Reporting Entity")),
        ("Incident Date", record.incident_date),
        (
            "Automation System Engaged",
            _payload_field(payload, "Automation System Engaged?"),
        ),
        ("Engagement Status", _engagement_status(payload)),
        ("Make", _payload_field(payload, "Make")),
        ("Model", _payload_field(payload, "Model")),
        (
            "Highest Injury Severity Alleged",
            _payload_field(payload, "Highest Injury Severity Alleged"),
        ),
        ("Crash With", _payload_field(payload, "Crash With")),
        ("State", _payload_field(payload, "State")),
        ("Narrative", _clean_summary_text(_payload_field(payload, "Narrative"))),
    ]
    lines = ["NHTSA Standing General Order CSV report"]
    lines.extend(f"{label}: {value or 'Unknown'}" for label, value in fields)
    return "\n".join(lines)


def backfill_nhtsa_source_evidence(
    repository: IncidentRepository,
    *,
    csv_text: str,
) -> dict[str, int]:
    evidence_by_external_id = _nhtsa_evidence_from_import_csv(csv_text)
    summary = {"matched": 0, "updated": 0, "missing": 0}
    incidents = repository.list_incidents_pending_llm_review(
        source_registry_keys=["nhtsa_data"],
    )
    for incident in incidents:
        external_id = str(incident.get("external_id") or "")
        evidence = evidence_by_external_id.get(external_id)
        if evidence is None:
            continue
        summary["matched"] += 1
        source = _primary_nhtsa_source(incident.get("sources", []))
        if source is None:
            summary["missing"] += 1
            continue
        repository.update_incident_source_evidence(
            source_id=str(source["id"]),
            canonical_url=str(source["source_url"]),
            fetch_status="fetched",
            http_status=None,
            evidence_text=str(evidence["evidence_text"]),
            fetch_error=None,
            fetched_at=datetime.now(UTC).isoformat(),
            raw_source_payload=evidence["raw_source_payload"],
        )
        summary["updated"] += 1
    return summary


def _record_from_prepared_row(prepared: _PreparedNhtsaRow) -> VerifiedSourceRecord:
    row = prepared.row
    report_id = _field(row, "Report ID")
    company = _field(row, "Reporting Entity") or "Unknown vehicle operator"
    incident_date = _parse_nhtsa_date(
        _field(row, "Incident Date")
        or _field(row, "Incident Month")
        or _field(row, "Report Submission Date")
    )
    make = _field(row, "Make")
    model = _field(row, "Model")
    vehicle = " ".join(part for part in (make, model) if part)
    engagement_status = _engagement_status(row)
    injury = _field(row, "Highest Injury Severity Alleged")
    crash_with = _field(row, "Crash With")
    state = _field(row, "State")
    narrative = _clean_summary_text(_field(row, "Narrative"))
    details = [
        f"NHTSA SGO {prepared.source_kind} incident report {report_id}.",
        f"Report type: {_field(row, 'Report Type') or 'Unknown'}.",
        f"Engagement status: {engagement_status or 'Unknown'}.",
    ]
    if vehicle:
        details.append(f"Vehicle: {vehicle}.")
    if injury:
        details.append(f"Highest injury severity alleged: {injury}.")
    if crash_with:
        details.append(f"Crash with: {crash_with}.")
    if state:
        details.append(f"State: {state}.")
    if narrative:
        details.append(f"Narrative: {narrative}")
    return VerifiedSourceRecord(
        source_registry_key="nhtsa_data",
        external_id=f"nhtsa-sgo-{_slug(report_id)}",
        title=f"NHTSA SGO {prepared.source_kind} crash report {report_id}",
        incident_date=incident_date,
        company=company,
        summary=" ".join(details),
        source_url=f"{NHTSA_SGO_URL}#report-{_slug(report_id)}",
        publisher="NHTSA",
        raw_payload={
            **row,
            "report_id": report_id,
            "report_version": _field(row, "Report Version"),
            "source_file": prepared.source_file,
            "source_kind": prepared.source_kind,
        },
    )


def _nhtsa_evidence_from_import_csv(csv_text: str) -> dict[str, dict[str, object]]:
    reader = csv.DictReader(StringIO(csv_text))
    evidence_by_external_id: dict[str, dict[str, object]] = {}
    for row in reader:
        incident_id = (row.get("incident_id") or "").strip()
        evidence_text = row.get("primary_source_evidence_text") or ""
        raw_payload_json = row.get("primary_source_raw_payload_json") or ""
        if not incident_id or not evidence_text or not raw_payload_json:
            continue
        raw_payload = json.loads(raw_payload_json)
        if not isinstance(raw_payload, dict):
            continue
        evidence_by_external_id[incident_id] = {
            "evidence_text": evidence_text,
            "raw_source_payload": raw_payload,
        }
    return evidence_by_external_id


def _primary_nhtsa_source(
    sources: list[dict[str, object]],
) -> dict[str, object] | None:
    nhtsa_sources = [
        source
        for source in sources
        if source.get("source_registry_key") == "nhtsa_data"
    ]
    for source in nhtsa_sources:
        if "#report-" in str(source.get("source_url") or ""):
            return source
    return nhtsa_sources[0] if nhtsa_sources else None


def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    text = _read_text_with_fallback(csv_path)
    return [
        {key: value or "" for key, value in row.items() if key is not None}
        for row in csv.DictReader(text.splitlines())
    ]


def _read_text_with_fallback(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _source_kind_from_filename(filename: str) -> str:
    lowered = filename.lower()
    if "adas" in lowered:
        return "ADAS"
    if "ads" in lowered:
        return "ADS"
    return "OTHER"


def _source_kind_priority(source_kind: str) -> int:
    return {"ADAS": 1, "ADS": 2, "OTHER": 3}.get(source_kind, 0)


def _field(row: dict[str, str], name: str) -> str:
    normalized_name = _normalize_key(name)
    for key, value in row.items():
        if _normalize_key(key) == normalized_name:
            return value.strip()
    return ""


def _payload_field(payload: dict[str, object], name: str) -> str:
    string_payload = {key: str(value or "") for key, value in payload.items()}
    return _field(string_payload, name)


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _engagement_status(row: dict[str, object]) -> str:
    return (
        _payload_field(row, "Engagement Status")
        or _payload_field(row, "Automation System Engaged?")
        or "Unknown"
    )


def _parse_report_version(value: str) -> float:
    if not value:
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _sortable_date(value: str) -> str:
    if not value:
        return "0000-00-00"
    try:
        return _parse_nhtsa_date(value)
    except ValueError:
        return "0000-00-00"


def _parse_nhtsa_date(value: str) -> str:
    stripped = value.strip()
    month_match = re.fullmatch(r"([A-Za-z]{3,9})-(\d{4})", stripped)
    if month_match:
        month_name, year = month_match.groups()
        for fmt in ("%b", "%B"):
            try:
                month = datetime.strptime(month_name, fmt).month
                return f"{int(year):04d}-{month:02d}-01"
            except ValueError:
                continue
    from app.scrapers.verified_sources import _parse_flexible_date

    return _parse_flexible_date(stripped)


def _clean_summary_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
