from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.incidents import router as incidents_router
from app.core.config import get_settings
from app.db.repository_factory import build_incident_repository
from app.services.incident_translation import (
    DeepSeekIncidentTranslationClient,
    DisabledIncidentTranslationClient,
)


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
    incident_translation_client=None,
) -> FastAPI:
    settings = get_settings()
    effective_settings = settings.__class__(
        database_url=database_url or settings.database_url,
        admin_api_token=admin_api_token or settings.admin_api_token,
        openai_api_key=settings.openai_api_key,
        openai_primary_review_model=settings.openai_primary_review_model,
        openai_escalation_review_model=settings.openai_escalation_review_model,
        openai_embedding_model=settings.openai_embedding_model,
        deepseek_api_key=settings.deepseek_api_key,
        deepseek_translation_model=settings.deepseek_translation_model,
    )
    app = FastAPI(title="AI Reality Check API", lifespan=_lifespan)
    app.state.settings = effective_settings
    app.state.incident_repository = incident_repository or build_incident_repository(
        effective_settings.database_url
    )
    app.state.incident_translation_client = (
        incident_translation_client
        or (
            DeepSeekIncidentTranslationClient(
                api_key=effective_settings.deepseek_api_key,
                model=effective_settings.deepseek_translation_model,
            )
            if effective_settings.deepseek_api_key
            else DisabledIncidentTranslationClient()
        )
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
