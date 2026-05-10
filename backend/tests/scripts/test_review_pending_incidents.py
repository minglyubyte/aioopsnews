from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any

import pytest

from app.core.config import Settings
from app.scripts import review_pending_incidents as review_script


class _StubRepository:
    def __init__(self, pending: list[dict] | None = None) -> None:
        self.closed = False
        self._pending = pending or []

    def list_incidents_pending_llm_review(
        self,
        *,
        source_registry_keys: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return self._pending

    def close(self) -> None:
        self.closed = True


def test_review_script_dry_run_lists_pending(monkeypatch, capsys) -> None:
    pending = [
        {"id": "incident-1", "external_id": "ext-1"},
        {"id": "incident-2", "external_id": "ext-2"},
    ]
    repository = _StubRepository(pending=pending)

    monkeypatch.setattr(
        review_script,
        "get_settings",
        lambda: Settings(database_url="postgresql://example/db"),
    )
    monkeypatch.setattr(
        review_script,
        "build_incident_repository",
        lambda database_url: repository,
    )
    monkeypatch.setattr(
        review_script.argparse.ArgumentParser,
        "parse_args",
        lambda self: argparse.Namespace(
            dry_run=True,
            max_reviews=None,
            source_registry_keys=None,
            review_concurrency=None,
            backoff_max_seconds=60.0,
        ),
    )

    exit_code = review_script.main()

    assert exit_code == 0
    assert repository.closed is True
    output = json.loads(capsys.readouterr().out)
    assert output["dry_run"] is True
    assert output["pending_incidents_found"] == 2
    assert output["incident_ids"] == ["incident-1", "incident-2"]


def test_review_script_dry_run_respects_max_reviews(monkeypatch, capsys) -> None:
    pending = [
        {"id": f"incident-{i}", "external_id": f"ext-{i}"}
        for i in range(10)
    ]
    repository = _StubRepository(pending=pending)

    monkeypatch.setattr(
        review_script,
        "get_settings",
        lambda: Settings(database_url="postgresql://example/db"),
    )
    monkeypatch.setattr(
        review_script,
        "build_incident_repository",
        lambda database_url: repository,
    )
    monkeypatch.setattr(
        review_script.argparse.ArgumentParser,
        "parse_args",
        lambda self: argparse.Namespace(
            dry_run=True,
            max_reviews=3,
            source_registry_keys=None,
            review_concurrency=None,
            backoff_max_seconds=60.0,
        ),
    )

    exit_code = review_script.main()

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["pending_incidents_found"] == 3


def test_review_script_requires_credentials_for_live_run(monkeypatch) -> None:
    monkeypatch.setattr(
        review_script,
        "get_settings",
        lambda: Settings(
            database_url="postgresql://example/db",
            primary_review_api_key=None,
            openai_api_key=None,
            deepseek_api_key=None,
        ),
    )
    monkeypatch.setattr(
        review_script,
        "build_incident_repository",
        lambda database_url: _StubRepository(),
    )
    monkeypatch.setattr(
        review_script.argparse.ArgumentParser,
        "parse_args",
        lambda self: argparse.Namespace(
            dry_run=False,
            max_reviews=None,
            source_registry_keys=None,
            review_concurrency=None,
            backoff_max_seconds=60.0,
        ),
    )

    with pytest.raises(ValueError, match="Credentials missing"):
        review_script.main()
