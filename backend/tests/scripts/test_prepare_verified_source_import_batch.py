from __future__ import annotations

import argparse
import csv
from io import StringIO

from app.scripts import prepare_verified_source_import_batch as script
from app.services.incident_import import parse_incidents_csv_text
from app.workflows.dual_track_ingestion import VerifiedSourceRecord


class FakeRepository:
    def __init__(
        self,
        *,
        existing_count: int = 0,
        existing_external_ids: set[str] | None = None,
        existing_source_urls: set[str] | None = None,
    ) -> None:
        self.existing_count = existing_count
        self.existing_external_ids = existing_external_ids or set()
        self.existing_source_urls = existing_source_urls or set()
        self.closed = False

    def count_incidents_by_source_registry_keys(self, source_registry_keys):
        return self.existing_count

    def incident_exists_by_external_id(self, external_id: str) -> bool:
        return external_id in self.existing_external_ids

    def source_url_exists(self, source_url: str) -> bool:
        return source_url in self.existing_source_urls

    def close(self) -> None:
        self.closed = True


def _record(index: int, source: str) -> VerifiedSourceRecord:
    return VerifiedSourceRecord(
        source_registry_key=source,
        external_id=f"{source}-external-{index}",
        title=f"{source} action {index}",
        incident_date="2025-01-01",
        company=f"Company {index}",
        summary="Official agency action involving software automation.",
        source_url=f"https://example.gov/{source}/{index}",
        publisher=source.split("_", maxsplit=1)[0].upper(),
        raw_payload={"index": index},
    )


def test_select_records_to_target_skips_existing_ids_and_urls() -> None:
    records = [
        _record(1, "ftc_ai_enforcement"),
        _record(2, "ftc_ai_enforcement"),
        _record(3, "doj_ai_enforcement"),
        _record(4, "sec_ai_enforcement"),
    ]
    repository = FakeRepository(
        existing_count=498,
        existing_external_ids={"ftc_ai_enforcement-external-1"},
        existing_source_urls={"https://example.gov/doj_ai_enforcement/3"},
    )

    selection = script.select_records_for_import_target(
        records,
        repository=repository,
        sources=script.DEFAULT_AGENCY_SOURCES,
        target_total=500,
    )

    assert selection.existing_count == 498
    assert selection.generated_count == 4
    assert selection.new_eligible_count == 2
    assert selection.written_count == 2
    assert selection.projected_total == 500
    assert [record.external_id for record in selection.records] == [
        "ftc_ai_enforcement-external-2",
        "sec_ai_enforcement-external-4",
    ]


def test_write_source_named_inbox_csvs_are_importable(tmp_path) -> None:
    selection = script.VerifiedSourceImportBatchSelection(
        existing_count=48,
        generated_count=2,
        new_eligible_count=2,
        written_count=2,
        projected_total=50,
        records=[
            _record(1, "ftc_ai_enforcement"),
            _record(2, "doj_ai_enforcement"),
        ],
    )

    written = script.write_source_named_csvs(
        selection,
        out_dir=tmp_path,
        out_prefix="agency-ai-action",
    )

    assert [path.name for path in written] == [
        "agency-ai-action-doj_ai_enforcement.csv",
        "agency-ai-action-ftc_ai_enforcement.csv",
    ]
    for path in written:
        csv_text = path.read_text(encoding="utf-8")
        rows = list(csv.DictReader(StringIO(csv_text)))
        assert len(rows) == 1
        assert parse_incidents_csv_text(csv_text)


def test_main_fetches_generates_and_writes_json_summary(monkeypatch, tmp_path, capsys):
    repository = FakeRepository(existing_count=499)
    records = [
        _record(1, "ftc_ai_enforcement"),
        _record(2, "doj_ai_enforcement"),
    ]

    monkeypatch.setattr(
        script.argparse.ArgumentParser,
        "parse_args",
        lambda self: argparse.Namespace(
            sources="ftc_ai_enforcement,doj_ai_enforcement",
            target_total=500,
            limit_per_source=20,
            out_dir=tmp_path,
            out_prefix="batch",
        ),
    )
    monkeypatch.setattr(
        script,
        "get_settings",
        lambda: argparse.Namespace(database_url="postgresql://example"),
    )
    monkeypatch.setattr(
        script,
        "build_incident_repository",
        lambda database_url: repository,
    )
    monkeypatch.setattr(
        script,
        "fetch_verified_source_records",
        lambda **kwargs: records,
    )

    exit_code = script.main()

    assert exit_code == 0
    assert repository.closed is True
    assert (tmp_path / "batch-ftc_ai_enforcement.csv").exists()
    output = capsys.readouterr().out
    assert '"existing_count": 499' in output
    assert '"written_count": 1' in output
