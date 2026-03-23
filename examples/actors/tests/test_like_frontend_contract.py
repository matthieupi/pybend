# tests/test_like_frontend_contract.py
"""
Like/favorite response contract verification.

After the fix, the like/favorite response includes:
  - action: 'liked'/'unliked'/'favorited'/'unfavorited'
  - _field: target array field name ('likes'/'favorites')
  - id: the Like entity's id
  - user, created_at: Like entity fields (on create)

The frontend _response_ handler uses _field + id to update the
parent entity's array in-place without a network round-trip.
"""

import pytest
from helpers import auth_header, extract_items

pytestmark = pytest.mark.integration


class TestLikeResponseContract:
    """The like/favorite response must include entity data + field hint."""

    def test_like_response_includes_entity_data(self, client, charlie_token, seed_data):
        """Like response must include id and _field for frontend update."""
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]

        resp = client.post(
            f"/products/{product.id}/comments/{comment.id}/like",
            json={}, headers=auth_header(charlie_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "action" in data
        assert "id" in data, f"Like response must include 'id'. Got: {data}"
        assert "_field" in data, f"Like response must include '_field'. Got: {data}"
        assert data["_field"] == "likes"

    def test_favorite_response_includes_entity_data(self, client, alice_token, seed_data):
        """Favorite response must include id and _field for frontend update."""
        product = seed_data["products"][3]

        resp = client.post(
            f"/products/{product.id}/favorite",
            json={}, headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "action" in data
        assert "id" in data, f"Favorite response must include 'id'. Got: {data}"
        assert "_field" in data, f"Favorite response must include '_field'. Got: {data}"
        assert data["_field"] == "favorites"

    def test_both_like_and_comment_return_entity_data(self, client, alice_token, seed_data):
        """Both comment() and like() responses must include id for
        consistent frontend _response_ handling."""
        product = seed_data["products"][0]

        # Comment method returns entity data
        comment_resp = client.post(
            f"/products/{product.id}/comment",
            json={"comment": {"name": "Test comment", "description": "Testing"}},
            headers=auth_header(alice_token),
        )
        assert comment_resp.status_code == 200
        comment_data = comment_resp.json()
        assert "id" in comment_data

        # Like method should also return entity data
        comments_resp = client.get(f"/products/{product.id}/comments")
        comments = extract_items(comments_resp.json())
        assert len(comments) > 0
        comment_id = comments[0]["id"]

        like_resp = client.post(
            f"/products/{product.id}/comments/{comment_id}/like",
            json={}, headers=auth_header(alice_token),
        )
        assert like_resp.status_code == 200
        like_data = like_resp.json()
        assert "id" in like_data, (
            f"Like response must include 'id' like comment() does. Got: {like_data}"
        )
