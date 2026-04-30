from __future__ import annotations

import argparse

from app.core.config import Settings
from app.scripts import reconcile_incident_review_batch as reconcile_script


class _StubRepository:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_reconcile_script_reports_validating_batch_without_traceback(
    monkeypatch,
    capsys,
) -> None:
    repository = _StubRepository()

    monkeypatch.setattr(
        reconcile_script,
        "get_settings",
        lambda: Settings(
            database_url="postgresql://example/db",
            openai_api_key="test-openai-key",
            deepseek_api_key="test-deepseek-key",
        ),
    )
    monkeypatch.setattr(
        reconcile_script,
        "build_incident_repository",
        lambda database_url: repository,
    )
    monkeypatch.setattr(
        reconcile_script.argparse.ArgumentParser,
        "parse_args",
        lambda self: argparse.Namespace(
            batch_id="batch-1",
            wait_for_completion=False,
            poll_interval_seconds=30,
            max_wait_seconds=None,
        ),
    )

    class _ReviewClient:
        def get_batch_status(self, *, batch_id: str) -> str:
            return "validating"

    monkeypatch.setattr(
        reconcile_script,
        "OpenAIIncidentReviewClient",
        lambda api_key: _ReviewClient(),
    )

    exit_code = reconcile_script.main()

    assert exit_code == 1
    assert repository.closed is True
    assert "status=validating action=retry_later" in capsys.readouterr().out
