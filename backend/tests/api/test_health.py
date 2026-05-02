from fastapi.testclient import TestClient

from app.app_factory import create_app
from app.core.config import Settings


def test_health_returns_ok() -> None:
    client = TestClient(create_app(incident_repository=object()))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_app_closes_repository_on_shutdown() -> None:
    class ClosableRepository:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    repository = ClosableRepository()

    with TestClient(create_app(incident_repository=repository)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert repository.closed is True


def test_create_app_preserves_provider_neutral_primary_review_settings(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.app_factory.get_settings",
        lambda: Settings(
            database_url="postgresql://example/db",
            admin_api_token="admin-token",
            openai_api_key="openai-key",
            openai_embedding_model="text-embedding-3-small",
            primary_review_api_key="primary-key",
            primary_review_base_url="https://api.deepseek.com/v1",
            primary_review_model="deepseek-v4-flash",
            escalation_review_model="deepseek-v4-pro",
            deepseek_api_key="deepseek-key",
            deepseek_translation_model="deepseek-v4-flash",
        ),
    )

    app = create_app(
        database_url="postgresql://override/db",
        admin_api_token="override-admin",
        incident_repository=object(),
        incident_translation_client=object(),
    )

    assert app.state.settings.database_url == "postgresql://override/db"
    assert app.state.settings.admin_api_token == "override-admin"
    assert app.state.settings.primary_review_api_key == "primary-key"
    assert app.state.settings.primary_review_base_url == "https://api.deepseek.com/v1"
    assert app.state.settings.primary_review_model == "deepseek-v4-flash"
    assert app.state.settings.escalation_review_model == "deepseek-v4-pro"
