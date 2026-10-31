"""Exercise patch-aware policy on generated direct HTTP update routes."""

from types import SimpleNamespace
from typing import ClassVar

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import AliasChoices, ConfigDict, Field

import n3tx_core.api.routes_fastapi as routes_fastapi
from n3tx_core.api.routes_fastapi import _build_context
from n3tx_core.app import create_app
from n3tx_core.authorize import (
    ANYONE, OWNER, ROLE, AccessContext, AccessDenied, AccessRule,
    DefaultResolver, create_token,
)
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.ref import Ref
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.registrar import registered_models


pytestmark = pytest.mark.unit
ACTIVE = 'https://example.test/Account/2'


class OwnActive(AccessRule):
    """Allow active-only owner updates and an explicit admin grant."""

    def __init__(self):
        """Record contexts to verify the actual route authorization input."""
        self.seen = []

    def evaluate(self, ctx):
        """Require a nonempty active-only patch unless the caller is admin."""
        # 0. Observe the route context before applying the model policy.
        self.seen.append(ctx)
        patch = getattr(ctx, 'patch', None)
        return ROLE('admin').evaluate(ctx) or (
            OWNER.evaluate(ctx)
            and patch is not None
            and set(patch) == {'active'}
        )

    def to_dict(self):
        """Describe the test policy without exposing recorded requests."""
        return {'rule': 'own_active'}


@pytest.fixture
def api(tmp_path, monkeypatch):
    """Build real direct routes over an isolated temporary SQLite database."""
    # 0. Isolate the framework registry and declare a model-owned policy.
    saved = dict(registered_models)
    registered_models.clear()
    monkeypatch.setattr(routes_fastapi, 'router', APIRouter())
    rule = OwnActive()

    class Account(ProtoModel):
        """Supply a typed reference target without remote resolution."""

        __tablename__: ClassVar[str] = 'patch_accounts'

    class PatchUser(ProtoModel):
        """Model a self-owned identity with protected and aliased fields."""

        __tablename__: ClassVar[str] = 'patch_users'
        __storable__: ClassVar[bool] = True
        __owner_field__: ClassVar[str] = 'id'
        __protected_fields__: ClassVar[set] = {'password_hash', 'image'}
        __access__: ClassVar[dict] = {'read': ANYONE, 'update': rule}
        model_config = ConfigDict(populate_by_name=True)
        active: Ref[Account] | None = Field(
            default=None,
            validation_alias=AliasChoices('activeAccount', 'selection'),
        )
        role: str = 'staff'
        email: str = 'owner@example.test'
        account: str = 'unchanged'
        password_hash: str = Field(default='original', alias='passwordHash')
        preferences: dict = Field(default_factory=dict)

        @expose_route('/patch_only', methods=['POST'], access=rule)
        def patch_only(self) -> str:
            """Expose a policy probe which must receive no update patch."""
            return 'unexpected grant'

    try:
        # 1. Register generated routes and seed only disposable test records.
        app = create_app(
            models=[PatchUser],
            storage=SQLiteStorage(str(tmp_path / 'patch.db')),
            static_dir=None,
            jwt_secret='isolated-patch-tests-secret-at-least-32-characters',
            debug=False,
        )
        owner = PatchUser.create(PatchUser())
        other = PatchUser.create(PatchUser(email='other@example.test'))
        with TestClient(app) as client:
            yield SimpleNamespace(
                client=client, model=PatchUser, rule=rule,
                owner=owner, other=other,
            )
    finally:
        # 2. Restore registrations without touching application storage.
        registered_models.clear()
        registered_models.update(saved)


def headers(user_id, role='staff'):
    """Issue a synthetic JWT for the normal authentication middleware."""
    return {'x-access-token': create_token(
        user_id=user_id, email='synthetic@example.test', role=role,
    )}


@pytest.mark.parametrize('route', ['PatchUser', 'patch_users'])
@pytest.mark.parametrize('field', ['active', 'activeAccount', 'selection'])
def test_owner_updates_canonical_patch(api, route, field):
    """Both PUT mirrors authorize aliases as the same canonical field."""
    # 0. Exercise the generated route and inspect persisted state independently.
    response = api.client.put(
        f'/{route}/{api.owner.id}', json={field: ACTIVE},
        headers=headers(api.owner.id),
    )
    assert response.status_code == 200, response.text
    assert dict(api.rule.seen[-1].patch) == {'active': ACTIVE}
    stored = api.model.get(api.owner.id)
    assert str(stored.active) == ACTIVE
    assert stored.role == 'staff'
    assert stored.account == 'unchanged'


@pytest.mark.parametrize('patch', [
    {'role': 'admin'}, {'email': 'changed@example.test'},
    {'account': 'changed'}, {'active': ACTIVE, 'role': 'admin'},
    {'active': ACTIVE, 'unknown': True},
    {'active': ACTIVE, 'user': {'user_id': 1, 'role': 'admin'}},
    {'active': ACTIVE, 'context': {'patch': {'active': ACTIVE}}},
    {}, {'passwordHash': 'changed'}, {'image': 'changed'},
    {'id': 99, '$id': 'ignored', '$schema': 'ignored'},
])
def test_owner_cannot_expand_patch(api, patch):
    """Deny forbidden, unknown, forged-context and empty effective patches."""
    # 0. Submit disallowed input and verify persisted state is untouched.
    before = api.model.get(api.owner.id).model_dump()
    response = api.client.put(
        f'/PatchUser/{api.owner.id}', json=patch,
        headers=headers(api.owner.id),
    )
    assert response.status_code == 403, response.text
    assert api.model.get(api.owner.id).model_dump() == before


@pytest.mark.parametrize('caller', ['other', 'anonymous'])
def test_wrong_owner_and_anonymous_denied(api, caller):
    """Patch content never supplies caller identity or ownership."""
    # 0. Submit the allowed field without the required owner identity.
    auth = headers(api.other.id) if caller == 'other' else {}
    response = api.client.put(
        f'/PatchUser/{api.owner.id}', json={'active': ACTIVE}, headers=auth,
    )
    assert response.status_code == 403
    assert api.model.get(api.owner.id).active is None


def test_protected_fields_and_metadata_removed_before_policy(api):
    """Policy sees effective fields, not attempts to write protected data."""
    # 0. Submit aliases and stripped fields through the generated handler.
    response = api.client.put(
        f'/PatchUser/{api.owner.id}', headers=headers(api.owner.id),
        json={
            'activeAccount': ACTIVE, 'passwordHash': 'changed',
            'image': 'changed', 'id': 99, '$id': 'ignored',
            '$schema': 'ignored',
        },
    )
    assert response.status_code == 200, response.text
    assert dict(api.rule.seen[-1].patch) == {'active': ACTIVE}
    # 1. Verify stripped values never reached storage.
    stored = api.model.get(api.owner.id)
    assert stored.password_hash == 'original'
    assert stored.image == ''
    assert stored.id == api.owner.id


def test_admin_and_empty_noop_remain_supported(api):
    """Explicit admin grants retain ordinary updates and empty-patch no-ops."""
    # 0. Verify the independent admin policy still allows ordinary fields.
    auth = headers(api.other.id, 'admin')
    response = api.client.put(
        f'/PatchUser/{api.owner.id}', headers=auth,
        json={'role': 'client', 'email': 'new@example.test'},
    )
    assert response.status_code == 200, response.text
    before = api.model.get(api.owner.id).model_dump()
    assert before['role'] == 'client'
    assert before['email'] == 'new@example.test'
    # 1. Verify allowed empty effective input remains a no-op.
    response = api.client.put(
        f'/PatchUser/{api.owner.id}', headers=auth,
        json={'passwordHash': 'changed'},
    )
    assert response.status_code == 200
    assert dict(api.rule.seen[-1].patch) == {}
    assert api.model.get(api.owner.id).model_dump() == before


@pytest.mark.parametrize('patch', [
    {'active': ACTIVE, 'activeAccount': ACTIVE},
    {'password_hash': 'first', 'passwordHash': 'second'},
])
def test_alias_conflicts_rejected_before_policy(api, patch):
    """Canonicalization rejects duplicates even when the field is protected."""
    # 0. Verify ambiguity rejection precedes both policy and persistence.
    response = api.client.put(
        f'/PatchUser/{api.owner.id}', headers=headers(api.owner.id),
        json=patch,
    )
    assert response.status_code == 400
    assert 'supplied more than once' in response.json()['detail']
    assert api.rule.seen == []
    assert api.model.get(api.owner.id).active is None


def test_invalid_json_and_model_validation_do_not_persist(api):
    """Preserve 422 input/merged-model errors and the pre-validation policy."""
    # 0. Reject malformed JSON and non-object bodies before policy.
    auth = headers(api.owner.id)
    for body in ['{', '[]']:
        response = api.client.put(
            f'/PatchUser/{api.owner.id}', content=body,
            headers={**auth, 'content-type': 'application/json'},
        )
        assert response.status_code == 422
    assert api.rule.seen == []
    # 1. Authorize the field set, then reject its invalid value in the model.
    response = api.client.put(
        f'/PatchUser/{api.owner.id}', headers=auth,
        json={'active': 42},
    )
    assert response.status_code == 422
    assert api.rule.seen[-1].patch == {'active': 42}
    assert api.model.get(api.owner.id).active is None


def test_missing_resource_retains_404(api):
    """Resource lookup still precedes patch processing and policy."""
    # 0. Address a nonexistent record without invoking update policy.
    response = api.client.put(
        '/PatchUser/9999', json={'active': ACTIVE},
        headers=headers(api.owner.id),
    )
    assert response.status_code == 404
    assert api.rule.seen == []


def test_other_entrypoints_and_default_context_have_no_patch(api):
    """Fail closed when patch-aware rules run without direct PUT input."""
    # 0. Check contexts constructed without transport-provided patch input.
    user = {'user_id': api.owner.id, 'role': 'staff'}
    request = SimpleNamespace(state=SimpleNamespace(user=user))
    contexts = [
        AccessContext(user, 'update', api.model, api.owner),
        _build_context(request, api.model, 'update', api.owner),
    ]
    for ctx in contexts:
        assert ctx.patch is None
        with pytest.raises(AccessDenied):
            DefaultResolver().authorize(ctx)
    # 1. Verify an action body is not promoted to update authorization input.
    response = api.client.post(
        f'/PatchUser/{api.owner.id}/patch_only',
        headers=headers(api.owner.id), json={'active': ACTIVE},
    )
    assert response.status_code == 403
    assert api.rule.seen[-1].patch is None


def test_patch_snapshot_is_readonly_and_detached():
    """Neither caller mutation nor nested policy mutation changes the input."""
    # 0. Mutate each side of the snapshot and verify deep isolation.
    original = {'preferences': {'items': ['original']}}
    ctx = AccessContext({}, 'update', object, patch=original)
    original['preferences']['items'].append('caller')
    assert ctx.patch['preferences']['items'] == ['original']
    with pytest.raises(TypeError):
        ctx.patch['role'] = 'admin'
    ctx.patch['preferences']['items'].append('policy')
    assert original['preferences']['items'] == ['original', 'caller']


def test_policy_cannot_mutate_persisted_patch(api, monkeypatch):
    """Nested policy writes affect its snapshot, never the model payload."""
    # 0. Observe attempted policy mutations during actual route authorization.
    evaluate = api.rule.evaluate

    def inspect_patch(ctx):
        """Probe read-only keys and detached values during authorization."""
        # 0. Try to alter both top-level keys and a nested JSON value.
        with pytest.raises(TypeError):
            ctx.patch['role'] = 'admin'
        ctx.patch['preferences']['items'].append('policy-only')
        return evaluate(ctx)

    monkeypatch.setattr(api.rule, 'evaluate', inspect_patch)
    # 1. Verify persistence uses the original effective values, not the copy.
    response = api.client.put(
        f'/PatchUser/{api.owner.id}', headers=headers(api.other.id, 'admin'),
        json={'preferences': {'items': ['submitted']}},
    )
    assert response.status_code == 200, response.text
    stored = api.model.get(api.owner.id)
    assert stored.preferences == {'items': ['submitted']}
    assert stored.role == 'staff'


@pytest.fixture(params=['alias', 'validation_alias', 'alias_choices'])
def collision_api(tmp_path, monkeypatch, request):
    """Expose an overlapping alias schema through isolated native PUT routes."""
    # 0. Isolate routes and configure each supported string-alias spelling.
    saved = dict(registered_models)
    registered_models.clear()
    monkeypatch.setattr(routes_fastapi, 'router', APIRouter())
    rule = OwnActive()
    role_options = {
        'alias': {'alias': 'active'},
        'validation_alias': {'validation_alias': 'active'},
        'alias_choices': {
            'validation_alias': AliasChoices('legacyRole', 'active'),
        },
    }[request.param]

    class CollisionUser(ProtoModel):
        """Make active's canonical name an input alias for a different field."""

        __tablename__: ClassVar[str] = 'collision_users'
        __storable__: ClassVar[bool] = True
        __owner_field__: ClassVar[str] = 'id'
        __access__: ClassVar[dict] = {'update': rule}
        model_config = ConfigDict(populate_by_name=True)
        active: str = Field(default='staff', alias='selection')
        role: str = Field(default='staff', **role_options)

    try:
        # 1. Use disposable storage and native authentication/route generation.
        app = create_app(
            models=[CollisionUser],
            storage=SQLiteStorage(str(tmp_path / 'collision.db')),
            static_dir=None,
            jwt_secret='isolated-alias-tests-secret-at-least-32-characters',
            debug=False,
        )
        owner = CollisionUser.create(
            CollisionUser(selection='staff', role='staff')
        )
        with TestClient(app) as client:
            yield SimpleNamespace(
                client=client, model=CollisionUser, owner=owner, rule=rule,
            )
    finally:
        # 2. Restore registrations for neighboring tests.
        registered_models.clear()
        registered_models.update(saved)


@pytest.mark.parametrize('caller_role', ['staff', 'admin'])
def test_alias_overlap_cannot_change_authorized_keys(
    collision_api, caller_role,
):
    """Reject a second canonicalization that redirects active into role."""
    # 0. Send an active alias that previously bypassed the active-only policy.
    api = collision_api
    response = api.client.put(
        f'/CollisionUser/{api.owner.id}', json={'selection': 'admin'},
        headers=headers(api.owner.id, caller_role),
    )
    # 1. Inspect raw stored columns so overlapping read aliases cannot hide it.
    stored = api.model.get(api.owner.id, as_dict=True)
    assert stored['role'] == 'staff', (response.status_code, stored)
    assert response.status_code == 400, response.text
    assert 'stable canonical' in response.json()['detail']
    assert api.rule.seen == []


def test_alias_overlap_cannot_target_protected_field(collision_api):
    """A later alias expansion cannot reintroduce a stripped protected key."""
    # 0. Protect the second-hop destination, not the first canonical key.
    api = collision_api
    api.model.__protected_fields__ = {'role'}
    response = api.client.put(
        f'/CollisionUser/{api.owner.id}', json={'selection': 'admin'},
        headers=headers(api.owner.id, 'admin'),
    )
    assert api.model.get(api.owner.id, as_dict=True)['role'] == 'staff'
    assert response.status_code == 400
    assert api.rule.seen == []


def test_stable_admin_patch_on_overlapping_schema(collision_api):
    """Stable canonical keys remain usable under an explicit admin policy."""
    # 0. Update the fixed-point role key rather than its chained aliases.
    api = collision_api
    response = api.client.put(
        f'/CollisionUser/{api.owner.id}', json={'role': 'admin'},
        headers=headers(api.owner.id, 'admin'),
    )
    assert response.status_code == 200, response.text
    assert api.rule.seen[-1].patch == {'role': 'admin'}
    assert api.model.get(api.owner.id, as_dict=True)['role'] == 'admin'


def test_protected_stripping_precedes_alias_stability(collision_api):
    """Fully stripped input remains an authorized empty no-op for admins."""
    # 0. Strip the first-hop field before checking the remaining patch.
    api = collision_api
    api.model.__protected_fields__ = {'active'}
    before = api.model.get(api.owner.id, as_dict=True)
    response = api.client.put(
        f'/CollisionUser/{api.owner.id}', json={'selection': 'admin'},
        headers=headers(api.owner.id, 'admin'),
    )
    assert response.status_code == 200, response.text
    assert api.rule.seen[-1].patch == {}
    assert api.model.get(api.owner.id, as_dict=True) == before


def test_second_pass_alias_conflict_rejected_before_policy(collision_api):
    """Reject keys that collide only after the model's second alias pass."""
    # 0. Both initial keys survive, but active and role then map to role.
    api = collision_api
    before = api.model.get(api.owner.id, as_dict=True)
    response = api.client.put(
        f'/CollisionUser/{api.owner.id}',
        json={'selection': 'admin', 'role': 'staff'},
        headers=headers(api.owner.id, 'admin'),
    )
    assert response.status_code == 400
    assert 'supplied more than once' in response.json()['detail']
    assert api.rule.seen == []
    assert api.model.get(api.owner.id, as_dict=True) == before


def test_alias_and_unknown_keys_remain_visible(collision_api):
    """A canonical-looking alias is not treated as an unknown allowed field."""
    # 0. A literal active key maps to role; a real unknown key stays in input.
    api = collision_api
    response = api.client.put(
        f'/CollisionUser/{api.owner.id}',
        json={'active': 'admin', 'unknown': 'value'},
        headers=headers(api.owner.id),
    )
    assert response.status_code == 403
    assert api.rule.seen[-1].patch == {'role': 'admin', 'unknown': 'value'}
    assert api.model.get(api.owner.id, as_dict=True)['role'] == 'staff'


# Changelog
# - 2026-10-26: Cover canonical direct PUT patches and fail-closed policies,
#   including overlapping aliases and stable downstream canonicalization.
