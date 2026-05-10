from __future__ import annotations

import csv
from io import StringIO

from app.scripts import prepare_nhtsa_sgo_import as script
from app.services.incident_import import (
    import_incidents_csv_text,
    parse_incidents_csv_text,
)
from tests.support.fakes import InMemoryIncidentRepository


def test_prepare_tesla_records_selects_latest_report_version_across_files(
    tmp_path,
) -> None:
    adas_path = tmp_path / "SGO-2021-01_Incident_Reports_ADAS.csv"
    other_path = tmp_path / "SGO-2021-01_Incident_Reports_OTHER.csv"
    adas_path.write_text(
        "\n".join(
            [
                (
                    "Report ID,Report Version,Reporting Entity,Report Type,"
                    "Report Submission Date,Make,Model,Automation System Engaged?,"
                    "Engagement Status,Incident Date,State,Crash With,"
                    "Highest Injury Severity Alleged,Narrative"
                ),
                (
                    "13781-11042,1,Tesla Inc,1-Day,JUN-2025,Tesla,Model Y,"
                    "Unknown see Narrative,,MAY-2025,CA,Pedestrian,Serious,"
                    "Initial report."
                ),
            ]
        ),
        encoding="utf-8",
    )
    other_path.write_text(
        "\n".join(
            [
                (
                    "Report ID,Report Version,Reporting Entity,Report Type,"
                    "Report Submission Date,Make,Model,Automation System Engaged?,"
                    "Engagement Status,Incident Date,State,Crash With,"
                    "Highest Injury Severity Alleged,Narrative"
                ),
                (
                    "13781-11042,2,Tesla Inc,Update,JUN-2025,TESLA,Model Y,"
                    "Unknown see Narrative,Verified Not Engaged,MAY-2025,CA,"
                    "Pedestrian,Moderate W/ Hospitalization,Latest update."
                ),
            ]
        ),
        encoding="utf-8",
    )

    records = script.prepare_nhtsa_sgo_records(
        input_dir=tmp_path,
        company_filter="tesla",
        exclude_verified_not_engaged=False,
    )

    assert len(records) == 1
    assert records[0].external_id == "nhtsa-sgo-13781-11042"
    assert records[0].incident_date == "2025-05-01"
    assert records[0].company == "Tesla Inc"
    assert "Engagement status: Verified Not Engaged." in records[0].summary
    assert records[0].raw_payload["report_version"] == "2"
    assert records[0].raw_payload["source_file"] == other_path.name


def test_prepare_tesla_records_excludes_latest_verified_not_engaged(
    tmp_path,
) -> None:
    csv_path = tmp_path / "SGO-2021-01_Incident_Reports_ADAS.csv"
    csv_path.write_text(
        "\n".join(
            [
                (
                    "Report ID,Report Version,Reporting Entity,Report Type,"
                    "Report Submission Date,Make,Model,Automation System Engaged?,"
                    "Engagement Status,Incident Date,Narrative"
                ),
                (
                    "tesla-1,1,Tesla Inc,5-Day,JAN-2026,TESLA,Model 3,"
                    "ADAS,Verified Not Engaged,DEC-2025,Not engaged."
                ),
                (
                    "tesla-2,1,Tesla Inc,5-Day,JAN-2026,TESLA,Model Y,"
                    "ADAS,Verified Engaged,DEC-2025,Engaged."
                ),
                (
                    "gm-1,1,General Motors LLC,5-Day,JAN-2026,GMC,Yukon,"
                    "ADAS,Verified Engaged,DEC-2025,GM report."
                ),
                (
                    "empty-1,1,Tesla Inc,No New or Updated Incident Reports,"
                    "JAN-2026,TESLA,,ADAS,,DEC-2025,"
                ),
            ]
        ),
        encoding="utf-8",
    )

    records = script.prepare_nhtsa_sgo_records(input_dir=tmp_path)

    assert [record.external_id for record in records] == ["nhtsa-sgo-tesla-2"]
    assert records[0].incident_date == "2025-12-01"


def test_prepare_tesla_records_reads_cp1252_csv(tmp_path) -> None:
    csv_path = tmp_path / "SGO-2021-01_Incident_Reports_ADAS.csv"
    csv_path.write_bytes(
        "\n".join(
            [
                (
                    "Report ID,Report Version,Reporting Entity,Report Type,"
                    "Report Submission Date,Make,Model,Automation System Engaged?,"
                    "Engagement Status,Incident Date,Narrative"
                ),
                (
                    "tesla-2,1,Tesla Inc,5-Day,JAN-2026,TESLA,Model Y,"
                    "ADAS,Verified Engaged,DEC-2025,Driver’s narrative."
                ),
            ]
        ).encode("cp1252")
    )

    records = script.prepare_nhtsa_sgo_records(input_dir=tmp_path)

    assert len(records) == 1
    assert "Driver’s narrative." in records[0].summary


def test_prepare_nhtsa_import_csv_is_importable(tmp_path) -> None:
    records = _prepare_single_tesla_record(tmp_path)

    csv_text = script.records_to_nhtsa_import_csv(records)
    imported_rows = parse_incidents_csv_text(csv_text)
    raw_rows = list(csv.DictReader(StringIO(csv_text)))

    assert len(imported_rows) == 1
    assert raw_rows[0]["incident_id"] == "nhtsa-sgo-tesla-2"
    assert raw_rows[0]["source_registry_key"] == "nhtsa_data"
    assert raw_rows[0]["publication_track"] == "verified_accident"
    assert raw_rows[0]["evidence_tier"] == "official_documented"
    assert raw_rows[0]["source_family"] == "autonomous_vehicle"
    assert raw_rows[0]["source_origin"] == "fixed_verified_source"
    assert "primary_source_evidence_text" in raw_rows[0]
    assert "Report ID: tesla-2" in raw_rows[0]["primary_source_evidence_text"]
    assert "Narrative: Vehicle reported a crash." in raw_rows[0][
        "primary_source_evidence_text"
    ]
    assert '"Report ID": "tesla-2"' in raw_rows[0]["primary_source_raw_payload_json"]
    assert len(imported_rows[0].source_links) == 3


def test_nhtsa_import_persists_primary_source_evidence_and_payload(
    tmp_path,
) -> None:
    records = _prepare_single_tesla_record(tmp_path)
    repository = InMemoryIncidentRepository()

    import_incidents_csv_text(
        repository,
        script.records_to_nhtsa_import_csv(records),
        dry_run=False,
    )

    incident = next(iter(repository.incidents.values()))
    primary_source = incident["sources"][0]
    supplemental_source = incident["sources"][1]
    assert incident["status"] == "pending_llm_review"
    assert primary_source["fetch_status"] == "fetched"
    assert primary_source["http_status"] is None
    assert primary_source["canonical_url"] == primary_source["source_url"]
    assert "Report ID: tesla-2" in primary_source["evidence_text"]
    assert primary_source["raw_source_payload"]["Report ID"] == "tesla-2"
    assert supplemental_source["evidence_text"] is None
    assert supplemental_source["raw_source_payload"] is None


def test_backfill_nhtsa_source_evidence_updates_existing_pending_rows(
    tmp_path,
) -> None:
    records = _prepare_single_tesla_record(tmp_path)
    csv_text = script.records_to_nhtsa_import_csv(records)
    repository = InMemoryIncidentRepository()
    import_incidents_csv_text(repository, csv_text, dry_run=False)
    incident = next(iter(repository.incidents.values()))
    incident["status"] = "pending_llm_review"
    primary_source = incident["sources"][0]
    primary_source["fetch_status"] = None
    primary_source["evidence_text"] = None
    primary_source["raw_source_payload"] = None

    summary = script.backfill_nhtsa_source_evidence(
        repository,
        csv_text=csv_text,
    )

    assert summary == {"matched": 1, "updated": 1, "missing": 0}
    assert incident["status"] == "pending_llm_review"
    assert primary_source["fetch_status"] == "fetched"
    assert "Report ID: tesla-2" in primary_source["evidence_text"]
    assert primary_source["raw_source_payload"]["Report ID"] == "tesla-2"


def _prepare_single_tesla_record(tmp_path):
    csv_path = tmp_path / "SGO-2021-01_Incident_Reports_ADAS.csv"
    csv_path.write_text(
        "\n".join(
            [
                (
                    "Report ID,Report Version,Reporting Entity,Report Type,"
                    "Report Submission Date,Make,Model,Automation System Engaged?,"
                    "Engagement Status,Incident Date,State,Crash With,"
                    "Highest Injury Severity Alleged,Narrative"
                ),
                (
                    "tesla-2,1,Tesla Inc,5-Day,JAN-2026,TESLA,Model Y,"
                    "ADAS,Verified Engaged,DEC-2025,CA,Passenger Car,"
                    "Serious,Vehicle reported a crash."
                ),
            ]
        ),
        encoding="utf-8",
    )
    return script.prepare_nhtsa_sgo_records(input_dir=tmp_path)
