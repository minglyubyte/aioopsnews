from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import get_settings


def test_get_settings_loads_dotenv_from_parent_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    backend_dir = repo_root / "backend"
    backend_dir.mkdir(parents=True)
    (repo_root / ".env").write_text(
        (
            "ADMIN_API_TOKEN=dotenv-token\n"
            "DATABASE_URL=postgresql://postgres:postgres@localhost:5432/from-dotenv\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(backend_dir)
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = get_settings()

    assert settings.admin_api_token == "dotenv-token"
    assert (
        settings.database_url
        == "postgresql://postgres:postgres@localhost:5432/from-dotenv"
    )


def test_get_settings_prefers_existing_environment_over_dotenv(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    backend_dir = repo_root / "backend"
    backend_dir.mkdir(parents=True)
    (repo_root / ".env").write_text(
        "ADMIN_API_TOKEN=dotenv-token\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(backend_dir)
    monkeypatch.setenv("ADMIN_API_TOKEN", "shell-token")

    settings = get_settings()

    assert settings.admin_api_token == "shell-token"


def test_get_settings_requires_database_url_when_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    backend_dir = repo_root / "backend"
    backend_dir.mkdir(parents=True)
    (repo_root / ".env").write_text("", encoding="utf-8")

    monkeypatch.chdir(backend_dir)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValueError) as exc_info:
        get_settings()

    assert "DATABASE_URL is required" in str(exc_info.value)


def test_get_settings_reads_postgres_database_url_from_dotenv(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    backend_dir = repo_root / "backend"
    backend_dir.mkdir(parents=True)
    (repo_root / ".env").write_text(
        (
            "DATABASE_URL="
            "postgresql://postgres:postgres@localhost:5432/ai_reality_check\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(backend_dir)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = get_settings()

    assert (
        settings.database_url
        == "postgresql://postgres:postgres@localhost:5432/ai_reality_check"
    )
