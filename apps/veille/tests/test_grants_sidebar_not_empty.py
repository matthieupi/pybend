from fastapi.testclient import TestClient

from main import app


def test_grants_sidebar_collection_returns_items():
    client = TestClient(app)

    response = client.get("/grants?limit=20&offset=0")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"], "The Veille sidebar grants list should not be empty."
