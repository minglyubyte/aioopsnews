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


def test_records_to_incident_csv_pads_duplicate_source_links() -> None:
    records = [
        VerifiedSourceRecord(
            source_registry_key="damien_charlotin_hallucinations",
            external_id="damien-hallucination-no-source-2026-05-05",
            title="Case without independent source URL",
            incident_date="2026-05-05",
            company="Legal filing",
            summary="Tracker row falls back to the tracker home page.",
            source_url="https://www.damiencharlotin.com/hallucinations/",
            publisher="Damien Charlotin AI Hallucination Cases",
            raw_payload={"case": "Case without independent source URL"},
        )
    ]

    parsed_rows = parse_incidents_csv_text(script.records_to_incident_csv(records))

    assert len(parsed_rows[0].source_links) == 3


def test_records_to_incident_csv_pads_official_ai_enforcement_links() -> None:
    records = [
        VerifiedSourceRecord(
            source_registry_key="ftc_ai_enforcement",
            external_id="ftc-ai-donotpay-2024-09-25",
            title="FTC AI enforcement action: DoNotPay",
            incident_date="2024-09-25",
            company="DoNotPay",
            summary="FTC complaint alleges deceptive AI lawyer claims.",
            source_url=(
                "https://www.ftc.gov/news-events/news/press-releases/2024/09/"
                "ftc-announces-crackdown-deceptive-ai-claims-schemes"
            ),
            publisher="FTC",
            raw_payload={"source_excerpt": "AI enforcement action"},
        ),
        VerifiedSourceRecord(
            source_registry_key="doj_ai_enforcement",
            external_id="doj-ai-realpage-2024-08-23",
            title="DOJ antitrust complaint: RealPage algorithmic pricing",
            incident_date="2024-08-23",
            company="RealPage",
            summary="DOJ complaint alleges algorithmic pricing conduct.",
            source_url="https://www.justice.gov/atr/media/1365471/dl",
            publisher="DOJ",
            raw_payload={"source_excerpt": "Complaint"},
        ),
        VerifiedSourceRecord(
            source_registry_key="sec_ai_enforcement",
            external_id="sec-ai-delphia-usa-inc-2024-03-18",
            title="SEC charges firms with AI washing",
            incident_date="2024-03-18",
            company="Delphia (USA) Inc.",
            summary="SEC order alleges false AI claims.",
            source_url="https://www.sec.gov/newsroom/press-releases/2024-36",
            publisher="SEC",
            raw_payload={"source_excerpt": "AI washing"},
        ),
        VerifiedSourceRecord(
            source_registry_key="eeoc_ai_enforcement",
            external_id="eeoc-ai-itutorgroup-2023-09-11",
            title="iTutorGroup to settle EEOC software hiring suit",
            incident_date="2023-09-11",
            company="iTutorGroup",
            summary="EEOC alleged automated software rejected older applicants.",
            source_url="https://www.eeoc.gov/newsroom/itutorgroup-pay-365000-settle-eeoc-discriminatory-hiring-suit",
            publisher="EEOC",
            raw_payload={"source_excerpt": "software hiring suit"},
        ),
        VerifiedSourceRecord(
            source_registry_key="fda_ai_medical_device_warning_letters",
            external_id="fda-ai-exer-labs-inc-2025-02-10",
            title="FDA warning letter: Exer Labs",
            incident_date="2025-02-10",
            company="Exer Labs, Inc.",
            summary="FDA warning letter cited AI algorithms in medical claims.",
            source_url="https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/exer-labs-inc-699218-02102025",
            publisher="FDA",
            raw_payload={"source_excerpt": "AI medical device warning"},
        ),
    ]

    parsed_rows = parse_incidents_csv_text(script.records_to_incident_csv(records))

    assert [len(row.source_links) for row in parsed_rows] == [3, 4, 3, 3, 3]
    assert "https://www.sec.gov/ai" in parsed_rows[2].source_links
    assert (
        "https://www.ftc.gov/news-events/news/press-releases/2025/02/"
        "ftc-finalizes-order-donotpay-prohibits-deceptive-ai-lawyer-claims-"
        "imposes-monetary-relief-requires"
        in parsed_rows[0].source_links
    )


def test_records_to_incident_csv_collapses_cell_whitespace() -> None:
    records = [
        VerifiedSourceRecord(
            source_registry_key="damien_charlotin_hallucinations",
            external_id="damien-hallucination-whitespace-2026-05-05",
            title="Whitespace case",
            incident_date="2026-05-05",
            company="Legal filing",
            summary="Court quote has trailing spaces.  \nNext line continues.",
            source_url="https://www.damiencharlotin.com/documents/example.pdf",
            publisher="Damien Charlotin AI Hallucination Cases",
            raw_payload={"case": "Whitespace case"},
        )
    ]

    csv_text = script.records_to_incident_csv(records)

    assert "  \n" not in csv_text
    assert "Court quote has trailing spaces. Next line continues." in csv_text


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
