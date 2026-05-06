from __future__ import annotations

import argparse
import json

import pytest

from app.core.config import Settings
from app.scripts import run_dual_track_daily_runner as runner_script


class _StubRepository:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_dual_track_runner_script_builds_brave_provider_and_prints_summary(
    monkeypatch,
    capsys,
) -> None:
    repository = _StubRepository()
    provider_calls: list[dict[str, object]] = []
    fetch_calls: list[dict[str, object]] = []
    runner_calls: list[dict[str, object]] = []
    verified_records = [object()]
    summary = {
        "accident_sources_seen": 0,
        "accidents_created": 0,
        "accidents_skipped_existing": 0,
        "news_queries_run": 6,
        "news_results_seen": 12,
        "news_created": 5,
        "news_duplicates_skipped": 7,
        "news_filtered": 0,
        "source_failures": 0,
    }

    monkeypatch.setattr(
        runner_script,
        "get_settings",
        lambda: Settings(
            database_url="postgresql://example/db",
            brave_search_api_key="brave-key",
            ai_news_daily_result_limit=4,
            ai_news_freshness="pw",
        ),
    )
    monkeypatch.setattr(
        runner_script,
        "build_incident_repository",
        lambda database_url: repository,
    )
    monkeypatch.setattr(
        runner_script.argparse.ArgumentParser,
        "parse_args",
        lambda self: argparse.Namespace(
            skip_news=False,
            skip_verified=False,
            verified_sources="all",
            since="2026-01-01",
            limit_per_source=5,
            dry_run=False,
        ),
    )
    monkeypatch.setattr(
        runner_script,
        "BraveNewsSearchProvider",
        lambda **kwargs: provider_calls.append(kwargs) or object(),
    )
    monkeypatch.setattr(
        runner_script,
        "run_dual_track_daily_ingestion",
        lambda **kwargs: runner_calls.append(kwargs) or summary,
    )
    monkeypatch.setattr(
        runner_script,
        "fetch_verified_source_records",
        lambda **kwargs: fetch_calls.append(kwargs) or verified_records,
    )

    exit_code = runner_script.main()

    assert exit_code == 0
    assert repository.closed is True
    assert provider_calls == [
        {
            "api_key": "brave-key",
            "result_limit": 4,
            "freshness": "pw",
        }
    ]
    assert runner_calls[0]["repository"] is repository
    assert runner_calls[0]["verified_records"] == verified_records
    assert runner_calls[0]["search_provider"] is not None
    assert runner_calls[0]["dry_run"] is False
    assert fetch_calls == [
        {
            "sources": None,
            "since": "2026-01-01",
            "limit_per_source": 5,
        }
    ]
    assert json.loads(capsys.readouterr().out) == summary


def test_dual_track_runner_script_requires_brave_key_for_news(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        runner_script,
        "get_settings",
        lambda: Settings(
            database_url="postgresql://example/db",
            brave_search_api_key=None,
        ),
    )
    monkeypatch.setattr(
        runner_script.argparse.ArgumentParser,
        "parse_args",
        lambda self: argparse.Namespace(
            skip_news=False,
            skip_verified=True,
            verified_sources="all",
            since=None,
            limit_per_source=50,
            dry_run=False,
        ),
    )

    with pytest.raises(ValueError) as exc_info:
        runner_script.main()

    assert "BRAVE_SEARCH_API_KEY" in str(exc_info.value)


def test_dual_track_runner_script_allows_skip_news_without_brave_key(
    monkeypatch,
    capsys,
) -> None:
    repository = _StubRepository()
    summary = {
        "accident_sources_seen": 0,
        "accidents_created": 0,
        "accidents_skipped_existing": 0,
        "news_queries_run": 0,
        "news_results_seen": 0,
        "news_created": 0,
        "news_duplicates_skipped": 0,
        "news_filtered": 0,
        "source_failures": 0,
    }

    monkeypatch.setattr(
        runner_script,
        "get_settings",
        lambda: Settings(
            database_url="postgresql://example/db",
            brave_search_api_key=None,
        ),
    )
    monkeypatch.setattr(
        runner_script,
        "build_incident_repository",
        lambda database_url: repository,
    )
    monkeypatch.setattr(
        runner_script.argparse.ArgumentParser,
        "parse_args",
        lambda self: argparse.Namespace(
            skip_news=True,
            skip_verified=True,
            verified_sources="all",
            since=None,
            limit_per_source=50,
            dry_run=False,
        ),
    )
    monkeypatch.setattr(
        runner_script,
        "BraveNewsSearchProvider",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("Brave provider should not be built when news is skipped")
        ),
    )
    monkeypatch.setattr(
        runner_script,
        "run_dual_track_daily_ingestion",
        lambda **kwargs: summary,
    )

    assert runner_script.main() == 0
    assert repository.closed is True
    assert json.loads(capsys.readouterr().out) == summary
