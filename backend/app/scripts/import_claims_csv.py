from __future__ import annotations

import argparse
from pathlib import Path

from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.services.claim_import import import_claims_csv_text


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import AI claim rows from a CSV file into PostgreSQL."
    )
    parser.add_argument("csv_path", type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the CSV without writing any database rows.",
    )
    parser.add_argument(
        "--default-status",
        default="approved",
        help="Status to use when the CSV leaves the status column blank.",
    )
    args = parser.parse_args()

    settings = get_settings()
    repository = build_incident_repository(settings.database_url)
    csv_text = args.csv_path.read_text(encoding="utf-8")
    summary = import_claims_csv_text(
        repository,
        csv_text,
        dry_run=args.dry_run,
        default_status=args.default_status,
    )

    print(f"validated={summary.validated} inserted={summary.inserted}")
    print(f"dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
