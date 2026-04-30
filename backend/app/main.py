from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.incidents import router as incidents_router
from app.core.config import get_settings
from app.db.sqlite_repository import SQLiteIncidentRepository


def create_app(
    database_url: str | None = None,
    admin_api_token: str | None = None,
) -> FastAPI:
    settings = get_settings()
    effective_settings = settings.__class__(
        database_url=database_url or settings.database_url,
        admin_api_token=admin_api_token or settings.admin_api_token,
    )
    app = FastAPI(title="AI Reality Check API")
    app.state.settings = effective_settings

    app.state.incident_repository = SQLiteIncidentRepository(
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


app = create_app()
