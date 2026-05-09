from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository


@dataclass(frozen=True)
class IncidentCsvBatchSelection:
    fieldnames: list[str]
    rows: list[dict[str, str]]
    skipped_existing: int
    total_unimported_seen: int


def select_next_unimported_rows(
    csv_text: str,
    *,
    repository: Any,
    batch_size: int,
) -> IncidentCsvBatchSelection:
    reader = csv.DictReader(StringIO(csv_text))
    if reader.fieldnames is None:
        raise ValueError("Source CSV must include a header row")

    rows: list[dict[str, str]] = []
    skipped_existing = 0
    for row in reader:
        external_id = (row.get("incident_id") or "").strip()
        if not external_id:
            continue
        if repository.incident_exists_by_external_id(external_id):
            skipped_existing += 1
            continue
        rows.append(dict(row))
        if len(rows) == batch_size:
            break

    return IncidentCsvBatchSelection(
        fieldnames=list(reader.fieldnames),
        rows=rows,
        skipped_existing=skipped_existing,
        total_unimported_seen=len(rows),
    )


def write_batch_csv(selection: IncidentCsvBatchSelection, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=selection.fieldnames)
        writer.writeheader()
        writer.writerows(selection.rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a fixed-size incident CSV batch excluding imported IDs."
    )
    parser.add_argument("source_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()

    if args.batch_size < 1:
        raise ValueError("--batch-size must be at least 1")

    settings = get_settings()
    repository = build_incident_repository(settings.database_url)
    try:
        selection = select_next_unimported_rows(
            args.source_csv.read_text(encoding="utf-8"),
            repository=repository,
            batch_size=args.batch_size,
        )
        write_batch_csv(selection, args.output_csv)
    finally:
        repository.close()

    print(
        "Prepared "
        f"{len(selection.rows)} rows at {args.output_csv}; "
        f"skipped_existing={selection.skipped_existing}"
    )
    if len(selection.rows) != args.batch_size:
        raise RuntimeError(
            f"Expected {args.batch_size} rows, found {len(selection.rows)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
