from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.scrapers.verified_sources import fetch_verified_source_records
from app.scripts.generate_verified_source_csv import records_to_incident_csv
from app.workflows.dual_track_ingestion import VerifiedSourceRecord

DEFAULT_AGENCY_SOURCES = (
    "ftc_ai_enforcement",
    "doj_ai_enforcement",
    "sec_ai_enforcement",
    "eeoc_ai_enforcement",
    "fda_ai_medical_device_warning_letters",
)


@dataclass(frozen=True)
class VerifiedSourceImportBatchSelection:
    existing_count: int
    generated_count: int
    new_eligible_count: int
    written_count: int
    projected_total: int
    records: list[VerifiedSourceRecord]


def select_records_for_import_target(
    records: list[VerifiedSourceRecord],
    *,
    repository: Any,
    sources: tuple[str, ...] | list[str],
    target_total: int,
) -> VerifiedSourceImportBatchSelection:
    existing_count = repository.count_incidents_by_source_registry_keys(list(sources))
    remaining_capacity = max(target_total - existing_count, 0)
    eligible: list[VerifiedSourceRecord] = []
    seen_external_ids: set[str] = set()
    seen_source_urls: set[str] = set()
    for record in records:
        if record.source_registry_key not in sources:
            continue
        if (
            record.external_id in seen_external_ids
            or record.source_url in seen_source_urls
        ):
            continue
        seen_external_ids.add(record.external_id)
        seen_source_urls.add(record.source_url)
        if repository.incident_exists_by_external_id(record.external_id):
            continue
        if repository.source_url_exists(record.source_url):
            continue
        eligible.append(record)

    selected = eligible[:remaining_capacity]
    return VerifiedSourceImportBatchSelection(
        existing_count=existing_count,
        generated_count=len(records),
        new_eligible_count=len(eligible),
        written_count=len(selected),
        projected_total=existing_count + len(selected),
        records=selected,
    )


def write_source_named_csvs(
    selection: VerifiedSourceImportBatchSelection,
    *,
    out_dir: Path,
    out_prefix: str,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    records_by_source: dict[str, list[VerifiedSourceRecord]] = {}
    for record in selection.records:
        records_by_source.setdefault(record.source_registry_key, []).append(record)

    written: list[Path] = []
    for source in sorted(records_by_source):
        output_path = out_dir / f"{out_prefix}-{source}.csv"
        output_path.write_text(
            records_to_incident_csv(records_by_source[source]),
            encoding="utf-8",
        )
        written.append(output_path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate source-named verified-source inbox CSVs, skipping existing "
            "DB records and writing only enough rows to reach a target total."
        )
    )
    parser.add_argument(
        "--sources",
        default=",".join(DEFAULT_AGENCY_SOURCES),
        help="Comma-separated source registry keys.",
    )
    parser.add_argument("--target-total", type=int, default=500)
    parser.add_argument("--limit-per-source", type=int, default=2500)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("app/imports/inbox"),
    )
    parser.add_argument("--out-prefix", default="agency-ai-action")
    args = parser.parse_args()

    sources = tuple(_split_sources(args.sources))
    settings = get_settings()
    repository = build_incident_repository(settings.database_url)
    try:
        records = fetch_verified_source_records(
            sources=list(sources),
            limit_per_source=args.limit_per_source,
        )
        selection = select_records_for_import_target(
            records,
            repository=repository,
            sources=sources,
            target_total=args.target_total,
        )
        written_paths = write_source_named_csvs(
            selection,
            out_dir=args.out_dir,
            out_prefix=args.out_prefix,
        )
    finally:
        repository.close()

    summary = {
        key: value
        for key, value in asdict(selection).items()
        if key != "records"
    }
    summary["sources"] = list(sources)
    summary["written_files"] = [str(path) for path in written_paths]
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _split_sources(value: str) -> list[str]:
    return [source.strip() for source in value.split(",") if source.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
