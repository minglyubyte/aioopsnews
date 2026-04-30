from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str
    admin_api_token: str = "dev-admin-token"
    openai_api_key: str | None = None
    openai_primary_review_model: str = "gpt-5.4-mini"
    openai_escalation_review_model: str = "gpt-5.2"
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

    return Settings(
        database_url=database_url,
        admin_api_token=os.getenv(
            "ADMIN_API_TOKEN",
            "dev-admin-token",
        ),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_primary_review_model=os.getenv(
            "OPENAI_PRIMARY_REVIEW_MODEL",
            "gpt-5.4-mini",
        ),
        openai_escalation_review_model=os.getenv(
            "OPENAI_ESCALATION_REVIEW_MODEL",
            "gpt-5.2",
        ),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        deepseek_translation_model=os.getenv(
            "DEEPSEEK_TRANSLATION_MODEL",
            "deepseek-v4-flash",
        ),
    )
