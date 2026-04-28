from n3tx_actors.matrix import matrix
from n3tx_core.utils.registrar import registered_models


def test_registered_users_model_has_storage():
    user_cls = registered_models['users']

    assert user_cls.storage is not None


def test_matrix_users_child_matches_registered_model():
    user_cls = registered_models['users']
    routed = matrix.children.get('users')

    assert routed is user_cls


def test_matrix_users_child_has_storage():
    routed = matrix.children.get('users')

    assert routed is not None
    assert routed.storage is not None
