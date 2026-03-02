# tests/test_schema_endpoints.py
"""
Test Plan Section 1: Schema Endpoints
Verifies JSON Schema structure for each model (Product, Comment, Like, User).
Schema endpoints are public (no auth required).
"""

import pytest
from pybend.example_actor.tests.helpers import auth_header

pytestmark = pytest.mark.integration



class TestProductSchema:
    """GET /Product -- full JSON Schema verification."""

    def test_product_schema_returns_200(self, client):
        resp = client.get("/Product")
        assert resp.status_code == 200

    def test_product_schema_has_json_schema_metadata(self, client):
        schema = client.get("/Product").json()
        assert "$schema" in schema
        assert schema["$schema"].endswith("/Schema")
        assert "$id" in schema
        assert schema["$id"].endswith("/Product")

    def test_product_schema_has_name_and_tablename(self, client):
        schema = client.get("/Product").json()
        assert schema.get("__name__") == "Product"
        assert schema.get("__tablename__") == "products"

    def test_product_schema_has_required_properties(self, client):
        schema = client.get("/Product").json()
        props = schema.get("properties", {})
        for field_name in ["name", "price", "description", "comments", "favorites", "image", "id"]:
            assert field_name in props, f"Missing property: {field_name}"

    def test_product_schema_id_has_display_false(self, client):
        schema = client.get("/Product").json()
        id_prop = schema["properties"]["id"]
        assert id_prop.get("ui", {}).get("display") is False

    def test_product_schema_image_has_display_false(self, client):
        schema = client.get("/Product").json()
        image_prop = schema["properties"]["image"]
        assert image_prop.get("ui", {}).get("display") is False

    def test_product_schema_has_access_rules(self, client):
        schema = client.get("/Product").json()
        access = schema.get("access", {})
        # Product has no explicit __access__, so should get default
        assert isinstance(access, dict)

    def test_product_schema_has_methods(self, client):
        schema = client.get("/Product").json()
        methods = schema.get("methods", {})
        assert "comment" in methods, "Missing 'comment' method"
        assert "favorite" in methods, "Missing 'favorite' method"

    def test_product_schema_comment_method_structure(self, client):
        schema = client.get("/Product").json()
        comment_method = schema["methods"]["comment"]
        assert "route" in comment_method
        assert "methods" in comment_method
        assert "parameters" in comment_method
        assert "returns" in comment_method
        assert comment_method["route"] == "/comment"
        assert "POST" in comment_method["methods"]

    def test_product_schema_favorite_method_has_access(self, client):
        schema = client.get("/Product").json()
        fav_method = schema["methods"]["favorite"]
        assert "access" in fav_method
        assert fav_method["access"]["rule"] == "authenticated"

    def test_product_schema_has_defs(self, client):
        schema = client.get("/Product").json()
        defs = schema.get("$defs", {})
        assert "Comment" in defs, "Missing Comment in $defs"
        assert "Like" in defs, "Missing Like in $defs"

    def test_product_schema_defs_have_ids(self, client):
        schema = client.get("/Product").json()
        defs = schema["$defs"]
        for def_name, def_schema in defs.items():
            if "properties" in def_schema:
                assert "$id" in def_schema, f"$defs.{def_name} missing $id"

    def test_product_schema_defs_have_methods(self, client):
        schema = client.get("/Product").json()
        comment_def = schema["$defs"].get("Comment", {})
        assert "methods" in comment_def
        assert "like" in comment_def.get("methods", {})
        assert "reply" in comment_def.get("methods", {})

    def test_product_schema_defs_have_access(self, client):
        schema = client.get("/Product").json()
        comment_def = schema["$defs"].get("Comment", {})
        assert "access" in comment_def
        comment_access = comment_def["access"]
        assert comment_access.get("read", {}).get("rule") == "anyone"
        assert comment_access.get("create", {}).get("rule") == "authenticated"

    def test_product_schema_has_ui_config(self, client):
        schema = client.get("/Product").json()
        ui = schema.get("ui", {})
        assert "field_order" in ui
        assert "groups" in ui
        assert "renderer" in ui

    def test_product_schema_ui_field_order(self, client):
        schema = client.get("/Product").json()
        field_order = schema["ui"]["field_order"]
        assert "name" in field_order
        assert "price" in field_order
        assert "comments" in field_order

    def test_product_schema_no_auth_required(self, client):
        """Schema endpoints should not require authentication."""
        resp = client.get("/Product")
        assert resp.status_code == 200

    def test_product_schema_id_is_valid_url(self, client):
        """IT-9: $id should be a well-formed URL ending with /Product."""
        from urllib.parse import urlparse
        schema = client.get("/Product").json()
        parsed = urlparse(schema["$id"])
        assert parsed.scheme in ("http", "https")
        assert parsed.path == "/Product"

    def test_product_schema_schema_is_valid_url(self, client):
        """IT-9: $schema should be a well-formed URL ending with /Schema."""
        from urllib.parse import urlparse
        schema = client.get("/Product").json()
        parsed = urlparse(schema["$schema"])
        assert parsed.scheme in ("http", "https")
        assert parsed.path == "/Schema"

    def test_product_schema_defs_ids_are_consistent(self, client):
        """IT-9: Each $defs entry $id should be a valid URL with correct model name."""
        from urllib.parse import urlparse
        schema = client.get("/Product").json()
        for def_name, def_schema in schema.get("$defs", {}).items():
            if "$id" in def_schema:
                parsed = urlparse(def_schema["$id"])
                assert parsed.scheme in ("http", "https"), \
                    f"$defs.{def_name}.$id has no scheme: {def_schema['$id']}"


class TestCommentSchema:
    """GET /ProductComment -- verify Comment schema (registered as join model ProductComment)."""

    def test_comment_schema_returns_200(self, client):
        # Comment is registered as ProductComment join model, not standalone
        resp = client.get("/ProductComment")
        assert resp.status_code == 200

    def test_comment_schema_has_access_rules(self, client):
        schema = client.get("/ProductComment").json()
        access = schema.get("access", {})
        assert access.get("read", {}).get("rule") == "anyone"
        assert access.get("create", {}).get("rule") == "authenticated"
        # update: OWNER | ROLE('admin')
        update_rule = access.get("update", {})
        assert update_rule.get("op") == "or"
        assert len(update_rule.get("rules", [])) == 2
        # delete: OWNER | ROLE('admin')
        delete_rule = access.get("delete", {})
        assert delete_rule.get("op") == "or"

    def test_comment_schema_parent_id_is_selfref(self, client):
        schema = client.get("/ProductComment").json()
        parent_prop = schema.get("properties", {}).get("parent_id", {})
        assert parent_prop.get("type") == "selfref"

    def test_comment_schema_has_likes_field(self, client):
        schema = client.get("/ProductComment").json()
        props = schema.get("properties", {})
        assert "likes" in props

    def test_comment_schema_user_owner_protected(self, client):
        schema = client.get("/ProductComment").json()
        user_owner_prop = schema.get("properties", {}).get("user_owner", {})
        assert user_owner_prop.get("ui", {}).get("protected") is True

    def test_standalone_comment_returns_404(self, client):
        """GET /Comment returns 404 -- Comment is not registered standalone."""
        resp = client.get("/Comment")
        assert resp.status_code == 404


class TestLikeSchema:
    """GET /CommentLike and /ProductLike -- verify Like schemas (registered as join models)."""

    def test_like_schema_returns_200(self, client):
        # Like is registered as CommentLike and ProductLike, not standalone
        resp = client.get("/CommentLike")
        assert resp.status_code == 200

    def test_like_schema_user_field_protected(self, client):
        schema = client.get("/CommentLike").json()
        user_prop = schema.get("properties", {}).get("user", {})
        assert user_prop.get("ui", {}).get("protected") is True

    def test_product_like_schema_returns_200(self, client):
        resp = client.get("/ProductLike")
        assert resp.status_code == 200

    def test_standalone_like_returns_404(self, client):
        """GET /Like returns 404 -- Like is not registered standalone."""
        resp = client.get("/Like")
        assert resp.status_code == 404


class TestUserSchema:
    """GET /User -- verify User schema."""

    def test_user_schema_returns_200(self, client):
        resp = client.get("/User")
        assert resp.status_code == 200

    def test_user_schema_hides_password_hash(self, client):
        schema = client.get("/User").json()
        props = schema.get("properties", {})
        assert "password_hash" not in props

    def test_user_schema_has_login_method(self, client):
        schema = client.get("/User").json()
        methods = schema.get("methods", {})
        assert "login" in methods
        login_method = methods["login"]
        assert login_method.get("access", {}).get("rule") == "anyone"

    def test_user_schema_has_register_method(self, client):
        schema = client.get("/User").json()
        methods = schema.get("methods", {})
        assert "register_user" in methods
        register_method = methods["register_user"]
        assert register_method.get("access", {}).get("rule") == "anyone"

    def test_user_schema_role_default(self, client):
        schema = client.get("/User").json()
        role_prop = schema.get("properties", {}).get("role", {})
        assert role_prop.get("default") == "user"


class TestAllSchemaEndpoints:
    """SD-1: Parametrized schema endpoint tests for all registered models."""

    @pytest.mark.parametrize("model_name", [
        "Product", "ProductComment", "CommentLike", "ProductLike", "User",
    ])
    def test_schema_returns_200(self, client, model_name):
        resp = client.get(f"/{model_name}")
        assert resp.status_code == 200

    @pytest.mark.parametrize("model_name", [
        "Product", "ProductComment", "CommentLike", "ProductLike", "User",
    ])
    def test_schema_has_metadata(self, client, model_name):
        schema = client.get(f"/{model_name}").json()
        assert "$schema" in schema
        assert "$id" in schema
        assert schema["$id"].endswith(f"/{model_name}")

    @pytest.mark.parametrize("model_name", [
        "Comment", "Like", "Nonexistent",
    ])
    def test_unregistered_schema_returns_404(self, client, model_name):
        resp = client.get(f"/{model_name}")
        assert resp.status_code == 404


class TestScaffoldEndpoint:
    """GET /{ClassName}?scaffold=component -- scaffold generation."""

    def test_scaffold_item_returns_text_plain(self, client):
        resp = client.get("/Product?scaffold=item")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers.get("content-type", "")
        assert "class" in resp.text  # Contains JS class definition

    def test_scaffold_list_returns_text_plain(self, client):
        resp = client.get("/Product?scaffold=list")
        assert resp.status_code == 200

    def test_scaffold_css_returns_text_plain(self, client):
        resp = client.get("/Product?scaffold=css")
        assert resp.status_code == 200

    def test_scaffold_invalid_kind_returns_400(self, client):
        resp = client.get("/Product?scaffold=invalid_type")
        assert resp.status_code == 400
