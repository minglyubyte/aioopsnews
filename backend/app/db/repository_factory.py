from __future__ import annotations

from app.db.postgres_repository import PostgresIncidentRepository


def build_incident_repository(database_url: str):
    if database_url.startswith(("postgresql://", "postgres://")):
        return PostgresIncidentRepository(database_url)

    raise ValueError("Unsupported DATABASE_URL scheme. Expected postgresql://")
