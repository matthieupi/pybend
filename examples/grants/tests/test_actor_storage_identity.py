"""Regression tests for grants actor-routing model/storage identity.

These tests pin the P0.1 invariant from the test-failure triage plan: actor
routing must dispatch to the same live model classes configured by the model
registrar, and those classes must have the active test storage attached.
"""


def test_registered_user_model_has_storage():
    from n3tx_core.utils.registrar import registered_models

    user_cls = registered_models["users"]

    assert user_cls.storage is not None


def test_matrix_user_actor_is_registered_model():
    from n3tx_core.utils.registrar import registered_models
    from n3tx_actors.matrix import matrix

    user_cls = registered_models["users"]
    routed = matrix.children.get("users")

    assert routed is user_cls


def test_matrix_user_actor_uses_registered_storage():
    from n3tx_core.utils.registrar import registered_models
    from n3tx_actors.matrix import matrix

    user_cls = registered_models["users"]
    routed = matrix.children.get("users")

    assert routed is not None
    assert routed.storage is user_cls.storage
    assert routed.storage is not None
