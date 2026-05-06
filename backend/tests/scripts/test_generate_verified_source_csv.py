from __future__ import annotations

import argparse
import csv
from io import StringIO

from app.scripts import generate_verified_source_csv as script
from app.services.incident_import import parse_incidents_csv_text
from app.workflows.dual_track_ingestion import VerifiedSourceRecord


def test_records_to_incident_csv_writes_importable_dual_track_rows() -> None:
    records = [
        VerifiedSourceRecord(
            source_registry_key="ca_dmv_av_collisions",
            external_id="ca-dmv-waymo-2026-04-12-2",
            title="Waymo April 12, 2026 (2) collision report",
            incident_date="2026-04-12",
            company="Waymo",
            summary="California DMV listed an AV collision report.",
            source_url="https://www.dmv.ca.gov/portal/file/waymo_041226-2-pdf/",
            publisher="California DMV",
            raw_payload={"index_text": "Waymo April 12, 2026 (2) (PDF)"},
        )
    ]

    csv_text = script.records_to_incident_csv(records)
    rows = list(csv.DictReader(StringIO(csv_text)))
    parsed_rows = parse_incidents_csv_text(csv_text)

    assert len(parsed_rows) == 1
    assert rows[0]["incident_id"] == "ca-dmv-waymo-2026-04-12-2"
    assert rows[0]["publication_track"] == "verified_accident"
    assert rows[0]["evidence_tier"] == "official_documented"
    assert rows[0]["source_family"] == "autonomous_vehicle"
    assert rows[0]["source_origin"] == "fixed_verified_source"
    assert rows[0]["source_registry_key"] == "ca_dmv_av_collisions"
    assert len(parsed_rows[0].source_links) == 3


def test_generate_verified_source_csv_main_fetches_and_writes_file(
    monkeypatch,
    tmp_path,
) -> None:
    out_path = tmp_path / "verified-source-auto.csv"
    records = [
        VerifiedSourceRecord(
            source_registry_key="damien_charlotin_hallucinations",
            external_id="damien-hallucination-braun-v-day-2026-04-30",
            title="Braun v. Day",
            incident_date="2026-04-30",
            company="Legal filing",
            summary="Court identified fabricated citations.",
            source_url="https://www.courtlistener.com/docket/68095239/braun-v-day/",
            publisher="Damien Charlotin AI Hallucination Cases",
            raw_payload={"case": "Braun v. Day"},
        )
    ]
    fetch_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        script.argparse.ArgumentParser,
        "parse_args",
        lambda self: argparse.Namespace(
            sources="all",
            since="2026-01-01",
            limit_per_source=10,
            out=out_path,
        ),
    )
    monkeypatch.setattr(
        script,
        "fetch_verified_source_records",
        lambda **kwargs: fetch_calls.append(kwargs) or records,
    )

    exit_code = script.main()

    assert exit_code == 0
    assert fetch_calls == [
        {
            "sources": None,
            "since": "2026-01-01",
            "limit_per_source": 10,
        }
    ]
    assert out_path.exists()
    assert parse_incidents_csv_text(out_path.read_text(encoding="utf-8"))
