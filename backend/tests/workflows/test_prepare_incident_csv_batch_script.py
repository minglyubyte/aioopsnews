from __future__ import annotations

import csv
from io import StringIO

from app.scripts.prepare_incident_csv_batch import select_next_unimported_rows


class _ExistingExternalIdRepository:
    def __init__(self, existing: set[str]) -> None:
        self.existing = existing

    def incident_exists_by_external_id(self, external_id: str) -> bool:
        return external_id in self.existing


def test_select_next_unimported_rows_excludes_existing_and_limits_to_batch_size() -> (
    None
):
    source_csv = StringIO()
    writer = csv.DictWriter(
        source_csv,
        fieldnames=[
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
        ],
    )
    writer.writeheader()
    for index in range(1, 6):
        writer.writerow(
            {
                "ref_number": str(index),
                "incident_id": f"accident-{index}",
                "company": "Example AI",
                "incident_date": f"2026-05-0{index}",
                "incident_topic": "autonomous system",
                "incident_description": f"Accident {index}",
                "mapped_claim": "",
                "source_links": "https://example.com/source",
                "legitimacy_flag": "REVIEW",
                "confidence_level": "medium",
                "notes": "",
            }
        )

    selected = select_next_unimported_rows(
        source_csv.getvalue(),
        repository=_ExistingExternalIdRepository({"accident-1", "accident-3"}),
        batch_size=2,
    )

    assert [row["incident_id"] for row in selected.rows] == [
        "accident-2",
        "accident-4",
    ]
    assert selected.total_unimported_seen == 2
    assert selected.skipped_existing == 2
