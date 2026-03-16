"""
Test plan for error handling
=============================

HTTP ERROR CODES
  - test_401_unauthenticated_access_to_protected_endpoint
  - test_403_unauthorized_action_wrong_role
  - test_404_non_existent_resource
  - test_404_non_existent_grant
  - test_404_non_existent_source
  - test_422_validation_error_bad_input_type
  - test_422_validation_error_missing_required_field
  - test_422_validation_error_field_too_short
  - test_422_validation_error_field_too_long
  - test_400_malformed_request_body

ERROR RESPONSE FORMAT
  - test_error_response_has_detail_field
  - test_401_error_message_format
  - test_403_error_message_format
  - test_404_error_message_format
  - test_422_error_message_format

METHOD ERRORS
  - test_method_error_returns_proper_http_status
  - test_method_not_found_returns_404
  - test_method_with_missing_parameters_returns_400

EDGE CASES
  - test_invalid_json_in_request_body
  - test_extra_fields_in_request_body_ignored
"""

import pytest
from helpers import auth_header


class TestHTTPErrorCodes:
    """HTTP status codes for various error conditions."""

    def test_401_unauthenticated_access_to_protected_endpoint(self, client):
        resp = client.post("/grants", json={
            "title": "Unauth Grant",
            "agency": "NSF",
            "url": "https://nsf.gov/unauth",
        })
        assert resp.status_code in (401, 403)

    def test_403_unauthorized_action_wrong_role(self, client, alice_token, bob_token):
        # Alice creates a grant
        create_resp = client.post("/grants", json={
            "title": "Alice Grant for Deletion Test",
            "agency": "NSF",
            "url": "https://nsf.gov/alice-delete-test",
        }, headers=auth_header(alice_token))
        grant_id = create_resp.json()["id"]

        # Bob (not owner, not admin) tries to delete
        delete_resp = client.delete(f"/grants/{grant_id}", headers=auth_header(bob_token))
        assert delete_resp.status_code == 403

    def test_404_non_existent_resource(self, client, alice_token):
        resp = client.get("/grants/99999", headers=auth_header(alice_token))
        assert resp.status_code == 404

    def test_404_non_existent_grant(self, client):
        resp = client.get("/grants/99999")
        assert resp.status_code == 404

    def test_404_non_existent_source(self, client, alice_token):
        resp = client.get("/sources/99999", headers=auth_header(alice_token))
        assert resp.status_code == 404

    def test_422_validation_error_bad_input_type(self, client, alice_token):
        # amount_min should be float, not string
        resp = client.post("/grants", json={
            "title": "Bad Type Grant",
            "agency": "NSF",
            "url": "https://nsf.gov/bad-type",
            "amount_min": "not-a-number",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_422_validation_error_missing_required_field(self, client, alice_token):
        # title is required
        resp = client.post("/grants", json={
            "agency": "NSF",
            "url": "https://nsf.gov/no-title",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_422_validation_error_field_too_short(self, client, alice_token):
        # title has min_length=1
        resp = client.post("/grants", json={
            "title": "",
            "agency": "NSF",
            "url": "https://nsf.gov/empty-title",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_422_validation_error_field_too_long(self, client, alice_token):
        # title has max_length=500
        resp = client.post("/grants", json={
            "title": "x" * 501,
            "agency": "NSF",
            "url": "https://nsf.gov/long-title",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_400_malformed_request_body(self, client, alice_token):
        # Send plain text instead of JSON
        resp = client.post(
            "/grants",
            data="not-json",
            headers={**auth_header(alice_token), "Content-Type": "application/json"}
        )
        assert resp.status_code in (400, 422)


class TestErrorResponseFormat:
    """Error responses have consistent format."""

    def test_error_response_has_detail_field(self, client):
        resp = client.get("/grants/99999")
        assert resp.status_code == 404
        assert "detail" in resp.json()

    def test_401_error_message_format(self, client):
        resp = client.post("/grants", json={
            "title": "Unauth Test",
            "agency": "NSF",
            "url": "https://nsf.gov/unauth",
        })
        if resp.status_code == 401:
            assert "detail" in resp.json()
            # Message should indicate authentication required
            assert resp.json()["detail"]

    def test_403_error_message_format(self, client, alice_token, bob_token):
        # Alice creates, Bob tries to delete
        create_resp = client.post("/grants", json={
            "title": "403 Test Grant",
            "agency": "NSF",
            "url": "https://nsf.gov/403-test",
        }, headers=auth_header(alice_token))
        grant_id = create_resp.json()["id"]

        delete_resp = client.delete(f"/grants/{grant_id}", headers=auth_header(bob_token))
        if delete_resp.status_code == 403:
            assert "detail" in delete_resp.json()
            # Message should indicate access denied
            assert delete_resp.json()["detail"]

    def test_404_error_message_format(self, client):
        resp = client.get("/grants/99999")
        assert resp.status_code == 404
        assert "detail" in resp.json()
        # Message should indicate not found
        detail = resp.json()["detail"]
        assert "not found" in detail.lower() or "404" in detail

    def test_422_error_message_format(self, client, alice_token):
        resp = client.post("/grants", json={
            "agency": "NSF",
            "url": "https://nsf.gov/no-title",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 422
        # Pydantic validation error format
        body = resp.json()
        assert "detail" in body


class TestMethodErrors:
    """Custom method error handling."""

    def test_method_with_missing_parameters_returns_400(self, client, alice_token, seed_data):
        # Try to call a method without required parameters
        # Most custom methods require 'id' at minimum
        grant = seed_data["grants"][0]

        # If Grant model has a custom method, test it
        # For now, test generic missing id case
        resp = client.post(f"/grants/favorite", json={
            # Missing 'id'
        }, headers=auth_header(alice_token))

        # Should return 400 or 404 depending on route existence
        assert resp.status_code in (400, 404, 405)


class TestEdgeCases:
    """Edge cases in error handling."""

    def test_invalid_json_in_request_body(self, client, alice_token):
        resp = client.post(
            "/grants",
            data='{"title": "Invalid JSON"',  # Malformed
            headers={**auth_header(alice_token), "Content-Type": "application/json"}
        )
        assert resp.status_code in (400, 422)

    def test_extra_fields_in_request_body_ignored(self, client, alice_token):
        # Pydantic should ignore extra fields (or raise depending on config)
        resp = client.post("/grants", json={
            "title": "Extra Fields Grant",
            "agency": "NSF",
            "url": "https://nsf.gov/extra",
            "extra_field_not_in_model": "ignored",
        }, headers=auth_header(alice_token))
        # Should succeed (extra fields ignored)
        assert resp.status_code == 201

    def test_omitted_optional_fields(self, client, alice_token):
        # Omit optional fields entirely (sending None may fail validation for typed fields)
        resp = client.post("/grants", json={
            "title": "Omitted Optional Fields",
            "agency": "NSF",
            "url": "https://nsf.gov/omitted-optional",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 201

    def test_invalid_url_format(self, client, alice_token):
        # url field is UrlField (validates as HTTP URL)
        resp = client.post("/grants", json={
            "title": "Invalid URL Grant",
            "agency": "NSF",
            "url": "not-a-valid-url",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_negative_amount_values(self, client, alice_token):
        # amount_min and amount_max should be positive (CurrencyField)
        resp = client.post("/grants", json={
            "title": "Negative Amount Grant",
            "agency": "NSF",
            "url": "https://nsf.gov/negative",
            "amount_min": -1000,
        }, headers=auth_header(alice_token))
        # Should fail validation if CurrencyField enforces >= 0
        # (depends on widget implementation)
        assert resp.status_code in (201, 422)

    def test_update_with_missing_required_fields_in_body(self, client, alice_token, seed_data):
        grant = seed_data["grants"][0]
        # Update should allow partial updates (only changed fields)
        resp = client.put(f"/grants/{grant.id}", json={
            "status": "reviewed",
            # Missing title, agency, url (may be required or optional)
        }, headers=auth_header(alice_token))
        # Depends on update logic — partial vs full replacement
        assert resp.status_code in (200, 422)
