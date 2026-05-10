from __future__ import annotations

import argparse
import json

import pytest

from app.core.config import Settings
from app.scripts import scrape_verified_sources as scrape_script


class _StubRepository:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_scrape_script_runs_workflow_and_prints_summary(
    monkeypatch,
    capsys,
) -> None:
    repository = _StubRepository()
    fetch_calls: list[dict] = []
    workflow_calls: list[dict] = []
    verified_records = [object()]
    expected_summary = {
        "records_seen": 1,
        "incidents_created": 1,
        "incidents_skipped_existing": 0,
        "evidence_fetch_attempted": 0,
        "evidence_fetch_succeeded": 0,
        "evidence_fetch_failed": 0,
    }

    monkeypatch.setattr(
        scrape_script,
        "get_settings",
        lambda: Settings(database_url="postgresql://example/db"),
    )
    monkeypatch.setattr(
        scrape_script,
        "build_incident_repository",
        lambda database_url: repository,
    )
    monkeypatch.setattr(
        scrape_script.argparse.ArgumentParser,
        "parse_args",
        lambda self: argparse.Namespace(
            dry_run=False,
            sources="all",
            since=None,
            limit_per_source=50,
            skip_evidence_fetch=False,
        ),
    )
    monkeypatch.setattr(
        scrape_script,
        "fetch_verified_source_records",
        lambda **kwargs: fetch_calls.append(kwargs) or verified_records,
    )
    monkeypatch.setattr(
        scrape_script,
        "HttpIncidentSourceFetcher",
        lambda: object(),
    )
    monkeypatch.setattr(
        scrape_script,
        "run_verified_source_scrape",
        lambda **kwargs: workflow_calls.append(kwargs) or expected_summary,
    )

    exit_code = scrape_script.main()

    assert exit_code == 0
    assert repository.closed is True
    assert fetch_calls == [{"sources": None, "since": None, "limit_per_source": 50}]
    assert workflow_calls[0]["repository"] is repository
    assert workflow_calls[0]["verified_records"] == verified_records
    assert workflow_calls[0]["dry_run"] is False
    assert workflow_calls[0]["skip_evidence_fetch"] is False
    assert json.loads(capsys.readouterr().out) == expected_summary


def test_scrape_script_passes_source_filter(monkeypatch, capsys) -> None:
    repository = _StubRepository()
    fetch_calls: list[dict] = []

    monkeypatch.setattr(
        scrape_script,
        "get_settings",
        lambda: Settings(database_url="postgresql://example/db"),
    )
    monkeypatch.setattr(
        scrape_script,
        "build_incident_repository",
        lambda database_url: repository,
    )
    monkeypatch.setattr(
        scrape_script.argparse.ArgumentParser,
        "parse_args",
        lambda self: argparse.Namespace(
            dry_run=True,
            sources="ca_dmv_av_collisions,nhtsa_data",
            since="2026-01-01",
            limit_per_source=10,
            skip_evidence_fetch=False,
        ),
    )
    monkeypatch.setattr(
        scrape_script,
        "fetch_verified_source_records",
        lambda **kwargs: fetch_calls.append(kwargs) or [],
    )
    monkeypatch.setattr(
        scrape_script,
        "HttpIncidentSourceFetcher",
        lambda: object(),
    )
    monkeypatch.setattr(
        scrape_script,
        "run_verified_source_scrape",
        lambda **kwargs: {
            "records_seen": 0,
            "incidents_created": 0,
            "incidents_skipped_existing": 0,
            "evidence_fetch_attempted": 0,
            "evidence_fetch_succeeded": 0,
            "evidence_fetch_failed": 0,
        },
    )

    assert scrape_script.main() == 0
    assert fetch_calls[0]["sources"] == ["ca_dmv_av_collisions", "nhtsa_data"]
    assert fetch_calls[0]["since"] == "2026-01-01"
    assert fetch_calls[0]["limit_per_source"] == 10
