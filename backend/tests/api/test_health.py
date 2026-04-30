from fastapi.testclient import TestClient

from app.app_factory import create_app


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
