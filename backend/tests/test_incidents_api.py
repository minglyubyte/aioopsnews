from fastapi.testclient import TestClient

from app.main import app


def test_get_incidents_returns_sorted_public_feed() -> None:
    client = TestClient(app)

    response = client.get("/incidents")

    assert response.status_code == 200

    payload = response.json()

    assert payload["items"]
    assert [item["headline"] for item in payload["items"]] == [
        "Customer support bot exposes private account notes",
        "Delivery robot pilot stalls after safety interventions",
    ]
    assert all(item["status"] == "approved" for item in payload["items"])
    assert payload["items"][0]["sources"][0]["source_type"] == "primary"


def test_get_filters_returns_distinct_filter_values() -> None:
    client = TestClient(app)

    response = client.get("/filters")

    assert response.status_code == 200
    assert response.json() == {
        "categories": [
            "Autonomous Systems",
            "Privacy/Security",
        ],
        "claimants": [
            "AssistCo",
            "RoboFleet",
        ],
        "companies": [
            "AssistCo",
            "RoboFleet",
        ],
    }
