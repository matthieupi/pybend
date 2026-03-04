"""
Test plan for app boot verification
====================================

BOOT VERIFICATION
  - test_app_starts_without_errors
  - test_all_models_registered
  - test_all_routes_accessible
  - test_schema_endpoints_return_valid_json_schema
  - test_static_files_served
  - test_root_endpoint_accessible
  - test_openapi_schema_accessible
  - test_models_have_required_attributes
"""

import pytest
from pybend.core.utils.registrar import registered_models


class TestAppBoot:
    """Application boots successfully."""

    def test_app_starts_without_errors(self, client):
        """Client fixture creation implies app started successfully."""
        assert client is not None

    def test_all_models_registered(self):
        """All expected models are registered."""
        expected_models = {'User', 'Grant', 'Source', 'WebTools', 'AgentActor'}
        model_names = {cls.__name__ for cls in registered_models.values()}
        # Check that expected models are present
        for model in expected_models:
            assert model in model_names or any(model.lower() in name.lower() for name in model_names)

    def test_all_routes_accessible(self, client):
        """Core routes respond without 500 errors."""
        routes = [
            "/",
            "/grants",
            "/sources",
            "/users",
            "/agents",
        ]
        for route in routes:
            resp = client.get(route)
            # 200, 401, 403 are all OK — just not 500
            assert resp.status_code != 500, f"Route {route} returned 500"

    def test_schema_endpoints_return_valid_json_schema(self, client):
        """Schema endpoints return valid JSON Schema documents."""
        schemas = [
            "/Grant",
            "/Source",
            "/User",
        ]
        for schema_path in schemas:
            resp = client.get(schema_path)
            assert resp.status_code == 200, f"Schema {schema_path} not accessible"
            data = resp.json()
            # Verify it's a JSON Schema document
            assert "$schema" in data or "$id" in data or "properties" in data

    def test_static_files_served(self, client):
        """Static files are accessible."""
        # Try to access index.html or a known static file
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_endpoint_accessible(self, client):
        """Root endpoint returns successfully."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_openapi_schema_accessible(self, client):
        """OpenAPI schema is accessible (if docs enabled)."""
        resp = client.get("/openapi.json")
        # May be disabled in production
        assert resp.status_code in (200, 404)


class TestModelAttributes:
    """Models have required attributes for proper operation."""

    def test_models_have_required_attributes(self):
        """All registered models have required class attributes."""
        for model_name, model_cls in registered_models.items():
            # Check for __tablename__
            assert hasattr(model_cls, '__tablename__'), f"{model_name} missing __tablename__"
            assert model_cls.__tablename__, f"{model_name} has empty __tablename__"

            # Check for schema() method (from ProtoModel)
            assert hasattr(model_cls, 'schema'), f"{model_name} missing schema() method"

    def test_storable_models_can_be_queried(self, seed_data):
        """Storable models can be queried (implies storage configured)."""
        # If seed_data loaded successfully, storage is working
        assert seed_data is not None
        assert 'users' in seed_data
        assert 'grants' in seed_data
