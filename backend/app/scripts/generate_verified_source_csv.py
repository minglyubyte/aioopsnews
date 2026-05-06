from __future__ import annotations

import argparse
import csv
import re
from io import StringIO
from pathlib import Path

from app.scrapers.verified_sources import (
    CA_DMV_COLLISION_REPORTS_URL,
    CHARLOTIN_DOWNLOAD_URL,
    CHARLOTIN_HOME_URL,
    EDRM_JUDICIAL_ORDERS_URL,
    NHTSA_SGO_URL,
    fetch_verified_source_records,
)
from app.workflows.dual_track_ingestion import (
    VerifiedSourceRecord,
    normalize_verified_source_record,
)

FIELDNAMES = [
    "ref_number",
    "incident_id",
    "company",
    "incident_date",
    "incident_topic",
    "incident_description",
    "mapped_claim",
    "source_links",
    "legitimacy_flag",
    "confidence_level",
    "notes",
    "publication_track",
    "evidence_tier",
    "source_family",
    "verification_summary",
    "source_origin",
    "source_registry_key",
]

SUPPLEMENTAL_SOURCE_LINKS = {
    "ca_dmv_av_collisions": [
        CA_DMV_COLLISION_REPORTS_URL,
        NHTSA_SGO_URL,
    ],
    "nhtsa_data": [
        NHTSA_SGO_URL,
        "https://www.nhtsa.gov/data",
    ],
    "damien_charlotin_hallucinations": [
        CHARLOTIN_HOME_URL,
        CHARLOTIN_DOWNLOAD_URL,
        "https://www.damiencharlotin.com/",
    ],
    "edrm_judicial_orders": [
        EDRM_JUDICIAL_ORDERS_URL,
        "https://edrm.net/2024/04/edrm-announces-genai-judicial-orders-repository/",
        "https://edrm.net/",
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate incident import CSV rows from fixed verified sources."
    )
    parser.add_argument(
        "--sources",
        default="all",
        help="Comma-separated source registry keys, or 'all'.",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="Only include records on or after this YYYY-MM-DD date.",
    )
    parser.add_argument(
        "--limit-per-source",
        type=int,
        default=50,
        help="Maximum rows to generate per source.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("app/imports/inbox/verified-source-auto.csv"),
        help="Output CSV path.",
    )
    args = parser.parse_args()

    sources = None if args.sources == "all" else _split_sources(args.sources)
    records = fetch_verified_source_records(
        sources=sources,
        since=args.since,
        limit_per_source=args.limit_per_source,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(records_to_incident_csv(records), encoding="utf-8")
    print(f"wrote={args.out} records={len(records)}")
    return 0


def records_to_incident_csv(records: list[VerifiedSourceRecord]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    for index, record in enumerate(records, start=1):
        candidate = normalize_verified_source_record(record)
        row = {
                "ref_number": str(index),
                "incident_id": record.external_id,
                "company": record.company,
                "incident_date": record.incident_date,
                "incident_topic": candidate.source_family,
                "incident_description": record.summary,
                "mapped_claim": "",
                "source_links": " | ".join(_source_links_for(record)),
                "legitimacy_flag": "REVIEW",
                "confidence_level": "high",
                "notes": (
                    f"Generated from {record.publisher}; source="
                    f"{record.source_url}"
                ),
                "publication_track": candidate.publication_track,
                "evidence_tier": candidate.evidence_tier,
                "source_family": candidate.source_family,
                "verification_summary": candidate.verification_summary,
                "source_origin": candidate.sources[0].source_origin,
                "source_registry_key": candidate.sources[0].source_registry_key,
            }
        writer.writerow({key: _clean_cell(value) for key, value in row.items()})
    return output.getvalue()


def _source_links_for(record: VerifiedSourceRecord) -> list[str]:
    links: list[str] = []
    for link in (
        record.source_url,
        *SUPPLEMENTAL_SOURCE_LINKS.get(record.source_registry_key, []),
    ):
        if link not in links:
            links.append(link)
    return links


def _split_sources(value: str) -> list[str]:
    return [source.strip() for source in value.split(",") if source.strip()]


def _clean_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


if __name__ == "__main__":
    raise SystemExit(main())
