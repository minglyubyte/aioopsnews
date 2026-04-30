from __future__ import annotations

from app.db.postgres_repository import PostgresIncidentRepository
from app.db.sqlite_repository import SQLiteIncidentRepository


def build_incident_repository(database_url: str):
    if database_url.startswith("sqlite:///"):
        return SQLiteIncidentRepository(database_url)

    if database_url.startswith(("postgresql://", "postgres://")):
        return PostgresIncidentRepository(database_url)

    raise ValueError(
        "Unsupported DATABASE_URL scheme. Expected sqlite:/// or postgresql://"
    )
