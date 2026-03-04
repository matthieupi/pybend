"""Tests for Source CRUD operations via the API."""
import pytest
from helpers import auth_header


class TestSourceList:
    def test_list_sources(self, client, seed_data, alice_token):
        resp = client.get("/sources", headers=auth_header(alice_token))
        assert resp.status_code == 200
        body = resp.json()
        data = body["data"] if isinstance(body, dict) else body
        assert len(data) >= 2


class TestSourceCreate:
    def test_create_source(self, client, alice_token):
        resp = client.post("/sources", json={
            "name": "EPA Grants",
            "url": "https://www.epa.gov/grants",
            "category": "government",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "EPA Grants"
        assert data["category"] == "government"


class TestSourceGet:
    def test_get_source_by_id(self, client, seed_data, alice_token):
        source = seed_data["sources"][0]
        resp = client.get(f"/sources/{source.id}", headers=auth_header(alice_token))
        assert resp.status_code == 200
        assert resp.json()["name"] == source.name
