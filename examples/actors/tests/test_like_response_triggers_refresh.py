# tests/test_like_response_triggers_refresh.py
"""
Bug reproduction: Like/favorite responses don't include updated entity data.

The frontend _response_ handler only updates when the response has `id`.
Like/favorite returns {action: 'liked'} without entity data, so the frontend
never refreshes and counts stay stale.

These tests verify the RESPONSE FORMAT from like/favorite endpoints —
they should include the updated parent entity data so the frontend can
update without a separate pull.
"""

import pytest
from helpers import auth_header

pytestmark = pytest.mark.integration


class TestLikeResponseIncludesEntityData:
    """After calling like, the response should include updated entity data
    so the frontend can update the count without a separate GET."""

    def test_comment_like_response_includes_updated_likes(self, client, charlie_token, seed_data, make_comment):
        """Like response should include the comment's updated likes array
        so the frontend _response_ handler can update the count badge."""
        product = seed_data["products"][3]
        comment = make_comment(product.id, name="Fresh response contract comment")

        resp = client.post(
            f"/Product/{product.id}/Comment/{comment['id']}/like",
            json={}, headers=auth_header(charlie_token),
        )
        assert resp.status_code == 200
        data = resp.json()

        # The response must include the action direction
        assert "action" in data

        # BUG: The response should also include the updated comment data
        # so the frontend can update without a separate GET (pull).
        # Currently returns only {action: 'liked'} — frontend _response_
        # handler skips update because data has no 'id' field.
        assert "id" in data, (
            f"Like response must include comment entity data (with 'id') "
            f"for the frontend to update. Got: {data}"
        )

    def test_product_favorite_response_includes_updated_favorites(self, client, alice_token, seed_data):
        """Favorite response should include the product's updated favorites
        so the frontend _response_ handler can update the count badge."""
        product = seed_data["products"][3]

        resp = client.post(
            f"/Product/{product.id}/favorite",
            json={}, headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        data = resp.json()

        assert "action" in data

        # BUG: Same as above — response must include entity data
        # for frontend _response_ to update without pull.
        assert "id" in data, (
            f"Favorite response must include product entity data (with 'id') "
            f"for the frontend to update. Got: {data}"
        )

    def test_like_response_has_likes_count(self, client, bob_token, seed_data, make_comment):
        """The like response should carry enough info to update the count badge
        immediately — at minimum the current likes count."""
        product = seed_data["products"][2]
        comment = make_comment(product.id, name="Fresh count contract comment")

        # Get the count before
        before = client.get(f"/Product/{product.id}/Comment/{comment['id']}")
        before_likes = before.json().get("likes", [])

        resp = client.post(
            f"/Product/{product.id}/Comment/{comment['id']}/like",
            json={}, headers=auth_header(bob_token),
        )
        assert resp.status_code == 200
        data = resp.json()

        # The response should tell the frontend the new count or include likes array
        has_count_info = (
            "likes" in data  # updated likes array
            or "count" in data  # explicit count
            or "id" in data  # full entity (frontend can extract count)
        )
        assert has_count_info, (
            f"Like response must include count info for frontend update. "
            f"Got only: {data}"
        )
