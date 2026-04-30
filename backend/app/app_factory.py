from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.incidents import router as incidents_router
from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository


@asynccontextmanager
async def _lifespan(app: FastAPI):
    yield

    close_repository = getattr(app.state.incident_repository, "close", None)
    if callable(close_repository):
        close_repository()


def create_app(
    database_url: str | None = None,
    admin_api_token: str | None = None,
    incident_repository=None,
) -> FastAPI:
    settings = get_settings()
    effective_settings = settings.__class__(
        database_url=database_url or settings.database_url,
        admin_api_token=admin_api_token or settings.admin_api_token,
    )
    app = FastAPI(title="AI Reality Check API", lifespan=_lifespan)
    app.state.settings = effective_settings
    app.state.incident_repository = incident_repository or build_incident_repository(
        effective_settings.database_url
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(incidents_router)
    app.include_router(admin_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
