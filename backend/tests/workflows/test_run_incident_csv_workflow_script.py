from __future__ import annotations

import argparse
import json
import logging
from types import SimpleNamespace

from app.core.config import Settings
from app.scripts import run_incident_csv_workflow as workflow_script


class _StubRepository:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_workflow_script_logs_start_and_finish(
    monkeypatch,
    caplog,
    capsys,
    tmp_path,
) -> None:
    repository = _StubRepository()
    inbox_dir = tmp_path / "inbox"
    archive_dir = tmp_path / "archive"
    summary = {"files_found": 1, "files_imported": 1}

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
            submit_new_batches=True,
            reconcile_ready_batches=True,
            wait_for_batches=False,
            poll_interval_seconds=30,
            max_wait_seconds=None,
        ),
    )
    monkeypatch.setattr(
        workflow_script,
        "HttpIncidentSourceFetcher",
        lambda: object(),
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
        lambda **kwargs: summary,
    )

    caplog.set_level(logging.INFO)

    exit_code = workflow_script.main()

    assert exit_code == 0
    assert repository.closed is True
    assert "Starting incident CSV workflow" in caplog.text
    assert "Completed incident CSV workflow" in caplog.text
    stdout = capsys.readouterr().out
    assert json.loads(stdout) == summary


def test_workflow_script_can_wait_and_reconcile_submitted_batches(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    repository = _StubRepository()
    inbox_dir = tmp_path / "inbox"
    archive_dir = tmp_path / "archive"
    initial_summary = {
        "files_found": 1,
        "files_imported": 1,
        "files_failed": 0,
        "incidents_imported": 125,
        "batches_submitted": 1,
        "batches_reconciled": 0,
        "batches_skipped": 1,
        "approved": 0,
        "pending_review": 0,
        "rejected": 0,
        "translations_completed": 0,
        "translations_failed": 0,
        "batch_results": [
            {"batch_id": "batch-1", "status": "submitted", "submitted": 125},
            {"batch_id": "batch-1", "status": "validating"},
        ],
        "file_results": [],
    }
    waited_batches: list[tuple[str, int, int | None]] = []

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
            submit_new_batches=True,
            reconcile_ready_batches=True,
            wait_for_batches=True,
            poll_interval_seconds=7,
            max_wait_seconds=90,
        ),
    )
    monkeypatch.setattr(
        workflow_script,
        "HttpIncidentSourceFetcher",
        lambda: object(),
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
        lambda **kwargs: initial_summary,
    )
    monkeypatch.setattr(
        workflow_script,
        "wait_for_batch_completion",
        lambda *,
        batch_client,
        batch_id,
        poll_interval_seconds,
        max_wait_seconds,
        logger: waited_batches.append(
            (batch_id, poll_interval_seconds, max_wait_seconds)
        )
        or "completed",
    )
    monkeypatch.setattr(
        workflow_script,
        "reconcile_incident_review_batch",
        lambda *args, **kwargs: SimpleNamespace(
            approved=3,
            pending_review=4,
            rejected=1,
            escalated=2,
        ),
    )

    exit_code = workflow_script.main()

    assert exit_code == 0
    assert repository.closed is True
    assert waited_batches == [("batch-1", 7, 90)]
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)
    assert payload["batches_reconciled"] == 1
    assert payload["approved"] == 3
    assert payload["pending_review"] == 4
    assert payload["rejected"] == 1
    assert payload["translations_completed"] == 3
    assert payload["batch_results"][-1]["status"] == "completed_after_wait"
