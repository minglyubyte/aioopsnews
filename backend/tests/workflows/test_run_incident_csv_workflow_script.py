from __future__ import annotations

import argparse
import json
import logging

from app.core.config import Settings
from app.scripts import run_incident_csv_workflow as workflow_script


class _StubRepository:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


async def _async_summary(summary):
    return summary


def test_workflow_script_logs_start_and_finish(
    monkeypatch,
    caplog,
    capsys,
    tmp_path,
) -> None:
    repository = _StubRepository()
    inbox_dir = tmp_path / "inbox"
    archive_dir = tmp_path / "archive"
    summary = {
        "files_found": 1,
        "files_imported": 1,
        "files_failed": 0,
        "incidents_imported": 2,
        "reviews_attempted": 2,
        "reviews_completed": 2,
        "reviews_failed": 0,
        "review_failures": [],
        "approved": 1,
        "pending_review": 1,
        "rejected": 0,
        "translations_completed": 1,
        "translations_failed": 0,
        "file_results": [],
    }

    monkeypatch.setattr(
        workflow_script,
        "get_settings",
        lambda: Settings(
            database_url="postgresql://example/db",
            openai_api_key="test-openai-key",
            deepseek_api_key="test-deepseek-key",
        ),
    )
    monkeypatch.setattr(
        workflow_script,
        "build_incident_repository",
        lambda database_url: repository,
    )
    monkeypatch.setattr(
        workflow_script.argparse.ArgumentParser,
        "parse_args",
        lambda self: argparse.Namespace(
            inbox_dir=inbox_dir,
            archive_dir=archive_dir,
            dry_run=False,
        ),
    )
    monkeypatch.setattr(
        workflow_script,
        "HttpIncidentSourceFetcher",
        lambda: object(),
    )
    monkeypatch.setattr(
        workflow_script,
        "AsyncOpenAIIncidentReviewClient",
        lambda api_key: object(),
    )
    monkeypatch.setattr(
        workflow_script,
        "OpenAIIncidentReviewClient",
        lambda api_key: object(),
    )
    monkeypatch.setattr(
        workflow_script,
        "OpenAIIncidentEmbeddingClient",
        lambda api_key: object(),
    )
    monkeypatch.setattr(
        workflow_script,
        "OpenAIIncidentDuplicateJudgeClient",
        lambda api_key: object(),
    )
    monkeypatch.setattr(
        workflow_script,
        "DeepSeekIncidentTranslationClient",
        lambda api_key, model: object(),
    )
    monkeypatch.setattr(
        workflow_script,
        "run_incident_csv_workflow",
        lambda **kwargs: _async_summary(summary),
    )

    caplog.set_level(logging.INFO)

    exit_code = workflow_script.main()

    assert exit_code == 0
    assert repository.closed is True
    assert "Starting incident CSV workflow" in caplog.text
    assert "Completed incident CSV workflow" in caplog.text
    stdout = capsys.readouterr().out
    assert json.loads(stdout) == summary
