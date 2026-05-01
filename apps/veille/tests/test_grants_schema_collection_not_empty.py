from fastapi.testclient import TestClient

from main import app


def test_grant_schema_declared_collection_has_renderable_items():
    client = TestClient(app)

    schema_response = client.get("/Grant")
    assert schema_response.status_code == 200
    schema = schema_response.json()

    collection_path = schema.get("collection") or f"/{schema.get('title', 'Grant').lower()}s"
    collection_response = client.get(f"{collection_path}?limit=20&offset=0")

    assert collection_response.status_code == 200
    payload = collection_response.json()
    assert payload["data"], f"{collection_path} should return grants for schema-driven UI rendering."
