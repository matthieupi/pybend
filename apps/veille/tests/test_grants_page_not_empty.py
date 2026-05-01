from fastapi.testclient import TestClient

from main import app


def test_grants_page_collection_reports_nonzero_total():
    client = TestClient(app)

    response = client.get("/grants?limit=5&offset=0")

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["total"] > 0, "The grants page should have grants to render."
    assert len(payload["data"]) > 0
