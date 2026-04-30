from __future__ import annotations

import argparse
from pathlib import Path

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.services.incident_import import import_incidents_csv_text


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import AI incident rows from a CSV file into PostgreSQL."
    )
    parser.add_argument("csv_path", type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the CSV without writing any database rows.",
    )
    args = parser.parse_args()

    settings = get_settings()
    repository = build_incident_repository(settings.database_url)
    csv_text = args.csv_path.read_text(encoding="utf-8")
    summary = import_incidents_csv_text(
        repository,
        csv_text,
        dry_run=args.dry_run,
    )

    print(
        " ".join(
            [
                f"validated={summary.validated}",
                f"inserted={summary.inserted}",
                f"approved={summary.approved}",
                f"pending_review={summary.pending_review}",
                f"pending_llm_review={summary.pending_llm_review}",
            ]
        )
    )
    print(f"dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
