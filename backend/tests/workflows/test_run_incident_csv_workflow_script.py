from __future__ import annotations

import argparse
import json
import logging

import pytest

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
    review_client_calls: list[dict[str, str]] = []
    escalation_client_calls: list[dict[str, str]] = []
    embedding_client_calls: list[dict[str, str]] = []
    duplicate_judge_client_calls: list[dict[str, str]] = []
    translation_client_calls: list[dict[str, str]] = []
    workflow_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        workflow_script,
        "get_settings",
        lambda: Settings(
            database_url="postgresql://example/db",
            openai_api_key="test-openai-key",
            primary_review_api_key="test-primary-key",
            primary_review_base_url="https://deepseek.example/v1",
            primary_review_model="deepseek-v4-flash",
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
        lambda **kwargs: review_client_calls.append(kwargs) or object(),
    )
    monkeypatch.setattr(
        workflow_script,
        "OpenAIIncidentReviewClient",
        lambda **kwargs: escalation_client_calls.append(kwargs) or object(),
    )
    monkeypatch.setattr(
        workflow_script,
        "OpenAIIncidentEmbeddingClient",
        lambda **kwargs: embedding_client_calls.append(kwargs) or object(),
    )
    monkeypatch.setattr(
        workflow_script,
        "OpenAIIncidentDuplicateJudgeClient",
        lambda **kwargs: duplicate_judge_client_calls.append(kwargs) or object(),
    )
    monkeypatch.setattr(
        workflow_script,
        "DeepSeekIncidentTranslationClient",
        lambda **kwargs: translation_client_calls.append(kwargs) or object(),
    )
    monkeypatch.setattr(
        workflow_script,
        "run_incident_csv_workflow",
        lambda **kwargs: workflow_calls.append(kwargs) or _async_summary(summary),
    )

    caplog.set_level(logging.INFO)

    exit_code = workflow_script.main()

    assert exit_code == 0
    assert repository.closed is True
    assert "Starting incident CSV workflow" in caplog.text
    assert "Completed incident CSV workflow" in caplog.text
    assert review_client_calls == [
        {
            "api_key": "test-primary-key",
            "base_url": "https://deepseek.example/v1",
        }
    ]
    assert escalation_client_calls == [{"api_key": "test-openai-key"}]
    assert embedding_client_calls == [{"api_key": "test-openai-key"}]
    assert duplicate_judge_client_calls == [{"api_key": "test-openai-key"}]
    assert translation_client_calls == [
        {
            "api_key": "test-deepseek-key",
            "model": "deepseek-v4-flash",
        }
    ]
    assert workflow_calls[0]["primary_model"] == "deepseek-v4-flash"
    stdout = capsys.readouterr().out
    assert json.loads(stdout) == summary


def test_workflow_script_fails_fast_without_primary_review_credentials(
    monkeypatch,
    tmp_path,
) -> None:
    repository = _StubRepository()
    build_repository_calls: list[str] = []

    monkeypatch.setattr(
        workflow_script,
        "get_settings",
        lambda: Settings(
            database_url="postgresql://example/db",
            openai_api_key="test-openai-key",
            primary_review_api_key=None,
            primary_review_base_url="https://api.deepseek.com/v1",
            primary_review_model="deepseek-v4-flash",
            deepseek_api_key="test-deepseek-key",
        ),
    )
    monkeypatch.setattr(
        workflow_script,
        "build_incident_repository",
        lambda database_url: build_repository_calls.append(database_url) or repository,
    )
    monkeypatch.setattr(
        workflow_script.argparse.ArgumentParser,
        "parse_args",
        lambda self: argparse.Namespace(
            inbox_dir=tmp_path / "inbox",
            archive_dir=tmp_path / "archive",
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
        "OpenAIIncidentReviewClient",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        workflow_script,
        "OpenAIIncidentEmbeddingClient",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        workflow_script,
        "OpenAIIncidentDuplicateJudgeClient",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        workflow_script,
        "DeepSeekIncidentTranslationClient",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        workflow_script,
        "run_incident_csv_workflow",
        lambda **kwargs: _async_summary(
            {
                "files_found": 0,
                "files_imported": 0,
                "files_failed": 0,
                "incidents_imported": 0,
                "reviews_attempted": 0,
                "reviews_completed": 0,
                "reviews_failed": 0,
                "review_failures": [],
                "approved": 0,
                "pending_review": 0,
                "rejected": 0,
                "translations_completed": 0,
                "translations_failed": 0,
                "file_results": [],
            }
        ),
    )

    with pytest.raises(ValueError) as exc_info:
        workflow_script.main()

    assert build_repository_calls == []
    assert repository.closed is False
    assert "PRIMARY_REVIEW_API_KEY" in str(exc_info.value)
