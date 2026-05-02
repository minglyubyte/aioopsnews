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


def test_get_settings_defaults_primary_review_to_deepseek(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    backend_dir = repo_root / "backend"
    backend_dir.mkdir(parents=True)
    (repo_root / ".env").write_text(
        "DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_reality_check\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(backend_dir)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PRIMARY_REVIEW_API_KEY", raising=False)
    monkeypatch.delenv("PRIMARY_REVIEW_BASE_URL", raising=False)
    monkeypatch.delenv("PRIMARY_REVIEW_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_PRIMARY_REVIEW_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    settings = get_settings()

    assert settings.primary_review_model == "deepseek-v4-flash"
    assert settings.openai_primary_review_model == "deepseek-v4-flash"
    assert settings.primary_review_base_url == "https://api.deepseek.com/v1"
    assert settings.primary_review_api_key is None


def test_get_settings_prefers_provider_neutral_primary_review_values(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    backend_dir = repo_root / "backend"
    backend_dir.mkdir(parents=True)
    (repo_root / ".env").write_text(
        "DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_reality_check\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(backend_dir)
    monkeypatch.setenv("PRIMARY_REVIEW_API_KEY", "primary-key")
    monkeypatch.setenv("PRIMARY_REVIEW_BASE_URL", "https://deepseek.example/v1")
    monkeypatch.setenv("PRIMARY_REVIEW_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

    settings = get_settings()

    assert settings.primary_review_api_key == "primary-key"
    assert settings.primary_review_base_url == "https://deepseek.example/v1"
    assert settings.primary_review_model == "deepseek-v4-flash"
    assert settings.openai_primary_review_model == "deepseek-v4-flash"
    assert settings.deepseek_api_key == "deepseek-key"
    assert settings.openai_api_key == "openai-key"


def test_get_settings_preserves_legacy_openai_primary_review_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    backend_dir = repo_root / "backend"
    backend_dir.mkdir(parents=True)
    (repo_root / ".env").write_text(
        "DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_reality_check\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(backend_dir)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PRIMARY_REVIEW_MODEL", raising=False)
    monkeypatch.delenv("PRIMARY_REVIEW_API_KEY", raising=False)
    monkeypatch.delenv("PRIMARY_REVIEW_BASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_PRIMARY_REVIEW_MODEL", "gpt-5.4-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

    settings = get_settings()

    assert settings.primary_review_model == "gpt-5.4-mini"
    assert settings.openai_primary_review_model == "gpt-5.4-mini"
    assert settings.primary_review_api_key == "openai-key"
    assert settings.primary_review_base_url == "https://api.openai.com/v1"


def test_get_settings_does_not_reuse_openai_key_for_primary_review(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    backend_dir = repo_root / "backend"
    backend_dir.mkdir(parents=True)
    (repo_root / ".env").write_text(
        "DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_reality_check\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(backend_dir)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.delenv("PRIMARY_REVIEW_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    settings = get_settings()

    assert settings.openai_api_key == "openai-key"
    assert settings.primary_review_api_key is None
