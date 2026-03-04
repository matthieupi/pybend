"""Tests for Grant CRUD operations via the API."""
import pytest
from helpers import auth_header


class TestGrantList:
    def test_list_grants_public(self, client, seed_data):
        resp = client.get("/grants")
        assert resp.status_code == 200
        body = resp.json()
        # Actor routing returns a plain list
        data = body["data"] if isinstance(body, dict) else body
        assert len(data) >= 1

    def test_list_grants_has_schema_metadata(self, client, seed_data):
        resp = client.get("/grants")
        body = resp.json()
        data = body["data"] if isinstance(body, dict) else body
        for item in data:
            assert "$schema" in item
            assert "$id" in item


class TestGrantCreate:
    def test_create_grant_authenticated(self, client, alice_token):
        resp = client.post("/grants", json={
            "title": "New Energy Grant",
            "agency": "DOE",
            "url": "https://energy.gov/new-grant",
            "description": "Renewable energy research.",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "New Energy Grant"
        assert data["agency"] == "DOE"
        assert data["status"] == "discovered"

    def test_create_grant_unauthenticated(self, client):
        resp = client.post("/grants", json={
            "title": "Unauthenticated Grant",
            "agency": "NSF",
            "url": "https://nsf.gov/test",
        })
        assert resp.status_code in (401, 403)


class TestGrantGet:
    def test_get_grant_by_id(self, client, seed_data):
        grant = seed_data["grants"][0]
        resp = client.get(f"/grants/{grant.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == grant.title
        assert data["agency"] == grant.agency

    def test_get_nonexistent_grant(self, client):
        resp = client.get("/grants/99999")
        assert resp.status_code == 404


class TestGrantUpdate:
    def test_update_grant_as_admin(self, client, admin_token, seed_data):
        grant = seed_data["grants"][0]
        resp = client.put(f"/grants/{grant.id}", json={
            "title": grant.title,
            "agency": grant.agency,
            "url": str(grant.url),
            "status": "reviewed",
        }, headers=auth_header(admin_token))
        assert resp.status_code == 200
        assert resp.json()["status"] == "reviewed"
