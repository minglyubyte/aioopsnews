from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str
    admin_api_token: str = "dev-admin-token"
    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    primary_review_api_key: str | None = None
    primary_review_base_url: str = "https://api.deepseek.com/v1"
    primary_review_model: str = "deepseek-v4-flash"
    escalation_review_model: str = "deepseek-v4-pro"
    deepseek_api_key: str | None = None
    deepseek_translation_model: str = "deepseek-v4-flash"
    review_max_output_tokens: int = 8000
    review_response_parse_max_attempts: int = 3
    forensic_min_word_count_what_happened: int = 100
    forensic_min_word_count_ai_failure_point: int = 100
    forensic_min_word_count_why_it_matters: int = 100


def _load_dotenv_defaults() -> None:
    for directory in (Path.cwd(), *Path.cwd().parents):
        dotenv_path = directory / ".env"
        if not dotenv_path.exists():
            continue

        for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

        break


def _get_optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _get_int_env(name: str, default: int) -> int:
    value = _get_optional_env(name)
    if value is None:
        return default
    return int(value)


def get_settings() -> Settings:
    _load_dotenv_defaults()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is required and must point to PostgreSQL")

    openai_api_key = _get_optional_env("OPENAI_API_KEY")
    deepseek_api_key_env = _get_optional_env("DEEPSEEK_API_KEY")
    primary_review_model_env = _get_optional_env("PRIMARY_REVIEW_MODEL")
    primary_review_api_key_env = _get_optional_env("PRIMARY_REVIEW_API_KEY")
    primary_review_base_url_env = _get_optional_env("PRIMARY_REVIEW_BASE_URL")
    primary_review_model = primary_review_model_env or "deepseek-v4-flash"
    primary_review_api_key = primary_review_api_key_env or deepseek_api_key_env
    primary_review_base_url = (
        primary_review_base_url_env or "https://api.deepseek.com/v1"
    )
    escalation_review_model = (
        _get_optional_env("ESCALATION_REVIEW_MODEL") or "deepseek-v4-pro"
    )
    deepseek_api_key = deepseek_api_key_env or primary_review_api_key_env

    return Settings(
        database_url=database_url,
        admin_api_token=os.getenv(
            "ADMIN_API_TOKEN",
            "dev-admin-token",
        ),
        openai_api_key=openai_api_key,
        openai_embedding_model=os.getenv(
            "OPENAI_EMBEDDING_MODEL",
            "text-embedding-3-small",
        ),
        primary_review_api_key=primary_review_api_key,
        primary_review_base_url=primary_review_base_url,
        primary_review_model=primary_review_model,
        escalation_review_model=escalation_review_model,
        deepseek_api_key=deepseek_api_key,
        deepseek_translation_model=os.getenv(
            "DEEPSEEK_TRANSLATION_MODEL",
            "deepseek-v4-flash",
        ),
        review_max_output_tokens=_get_int_env("REVIEW_MAX_OUTPUT_TOKENS", 8000),
        review_response_parse_max_attempts=_get_int_env(
            "REVIEW_RESPONSE_PARSE_MAX_ATTEMPTS",
            3,
        ),
        forensic_min_word_count_what_happened=max(
            _get_int_env("FORENSIC_MIN_WORD_COUNT_WHAT_HAPPENED", 100),
            100,
        ),
        forensic_min_word_count_ai_failure_point=max(
            _get_int_env("FORENSIC_MIN_WORD_COUNT_AI_FAILURE_POINT", 100),
            100,
        ),
        forensic_min_word_count_why_it_matters=max(
            _get_int_env("FORENSIC_MIN_WORD_COUNT_WHY_IT_MATTERS", 100),
            100,
        ),
    )
