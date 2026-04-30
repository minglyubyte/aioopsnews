from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./data/ai_reality_check.db"
    admin_api_token: str = "dev-admin-token"


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

    return Settings(
        database_url=os.getenv(
            "DATABASE_URL",
            "sqlite:///./data/ai_reality_check.db",
        ),
        admin_api_token=os.getenv(
            "ADMIN_API_TOKEN",
            "dev-admin-token",
        ),
    )
