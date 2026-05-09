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
    monkeypatch.delenv("ESCALATION_REVIEW_MODEL", raising=False)
    monkeypatch.delenv("REVIEW_MAX_OUTPUT_TOKENS", raising=False)
    monkeypatch.delenv("REVIEW_RESPONSE_PARSE_MAX_ATTEMPTS", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    settings = get_settings()

    assert settings.primary_review_model == "deepseek-v4-flash"
    assert settings.escalation_review_model == "deepseek-v4-pro"
    assert settings.primary_review_base_url == "https://api.deepseek.com/v1"
    assert settings.primary_review_api_key is None
    assert settings.review_max_output_tokens == 8000
    assert settings.review_response_parse_max_attempts == 3
    assert settings.review_concurrency == 10


def test_get_settings_uses_deepseek_key_for_default_primary_review_path(
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
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")

    settings = get_settings()

    assert settings.primary_review_model == "deepseek-v4-flash"
    assert settings.primary_review_base_url == "https://api.deepseek.com/v1"
    assert settings.primary_review_api_key == "deepseek-key"
    assert settings.deepseek_api_key == "deepseek-key"


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
    assert settings.escalation_review_model == "deepseek-v4-pro"
    assert settings.deepseek_api_key == "deepseek-key"
    assert settings.openai_api_key == "openai-key"


def test_get_settings_uses_primary_review_key_for_deepseek_translation_when_needed(
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
    monkeypatch.setenv("PRIMARY_REVIEW_API_KEY", "primary-key")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    settings = get_settings()

    assert settings.primary_review_api_key == "primary-key"
    assert settings.deepseek_api_key == "primary-key"


def test_get_settings_allows_explicit_escalation_review_model_override(
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
    monkeypatch.setenv("ESCALATION_REVIEW_MODEL", "deepseek-v4-pro")

    settings = get_settings()

    assert settings.escalation_review_model == "deepseek-v4-pro"


def test_get_settings_allows_explicit_review_runtime_overrides(
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
    monkeypatch.setenv("REVIEW_MAX_OUTPUT_TOKENS", "9000")
    monkeypatch.setenv("REVIEW_RESPONSE_PARSE_MAX_ATTEMPTS", "4")
    monkeypatch.setenv("REVIEW_CONCURRENCY", "12")
    monkeypatch.setenv("FORENSIC_MIN_WORD_COUNT_WHAT_HAPPENED", "80")
    monkeypatch.setenv("FORENSIC_MIN_WORD_COUNT_AI_FAILURE_POINT", "70")
    monkeypatch.setenv("FORENSIC_MIN_WORD_COUNT_WHY_IT_MATTERS", "60")

    settings = get_settings()

    assert settings.review_max_output_tokens == 9000
    assert settings.review_response_parse_max_attempts == 4
    assert settings.review_concurrency == 12
    assert settings.forensic_min_word_count_what_happened == 80
    assert settings.forensic_min_word_count_ai_failure_point == 70
    assert settings.forensic_min_word_count_why_it_matters == 60


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
    assert settings.deepseek_api_key is None


def test_get_settings_reads_ai_news_search_configuration(
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
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "brave-key")
    monkeypatch.setenv("AI_NEWS_DAILY_RESULT_LIMIT", "4")
    monkeypatch.setenv("AI_NEWS_FRESHNESS", "pw")

    settings = get_settings()

    assert settings.brave_search_api_key == "brave-key"
    assert settings.ai_news_daily_result_limit == 4
    assert settings.ai_news_freshness == "pw"
