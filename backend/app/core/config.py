from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str
    admin_api_token: str = "dev-admin-token"
    openai_api_key: str | None = None
    openai_primary_review_model: str = "deepseek-v4-flash"
    openai_escalation_review_model: str = "gpt-5.2"
    openai_embedding_model: str = "text-embedding-3-small"
    primary_review_api_key: str | None = None
    primary_review_base_url: str = "https://api.deepseek.com"
    primary_review_model: str = "deepseek-v4-flash"
    deepseek_api_key: str | None = None
    deepseek_translation_model: str = "deepseek-v4-flash"


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


def get_settings() -> Settings:
    _load_dotenv_defaults()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is required and must point to PostgreSQL")

    openai_api_key = os.getenv("OPENAI_API_KEY")
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    primary_review_model = os.getenv(
        "PRIMARY_REVIEW_MODEL",
        os.getenv("OPENAI_PRIMARY_REVIEW_MODEL", "deepseek-v4-flash"),
    )

    return Settings(
        database_url=database_url,
        admin_api_token=os.getenv(
            "ADMIN_API_TOKEN",
            "dev-admin-token",
        ),
        openai_api_key=openai_api_key,
        openai_primary_review_model=primary_review_model,
        openai_escalation_review_model=os.getenv(
            "OPENAI_ESCALATION_REVIEW_MODEL",
            "gpt-5.2",
        ),
        openai_embedding_model=os.getenv(
            "OPENAI_EMBEDDING_MODEL",
            "text-embedding-3-small",
        ),
        primary_review_api_key=os.getenv(
            "PRIMARY_REVIEW_API_KEY",
            deepseek_api_key or openai_api_key,
        ),
        primary_review_base_url=os.getenv(
            "PRIMARY_REVIEW_BASE_URL",
            "https://api.deepseek.com",
        ),
        primary_review_model=primary_review_model,
        deepseek_api_key=deepseek_api_key,
        deepseek_translation_model=os.getenv(
            "DEEPSEEK_TRANSLATION_MODEL",
            "deepseek-v4-flash",
        ),
    )
