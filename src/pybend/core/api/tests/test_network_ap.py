"""
Test plan for api/network_ap.py
================================

UNIT TESTS — behavior validation
  - test_initialization_defaults_addr_to_ap
  - test_initialization_strips_trailing_slash_from_base_url
  - test_base_url_property_returns_stripped_url
  - test_generate_actor_document_collection_level
  - test_generate_actor_document_entity_level
  - test_create_activity_maps_after_create_to_create
  - test_create_activity_maps_after_update_to_update
  - test_create_activity_maps_after_delete_to_delete
  - test_create_activity_delete_creates_tombstone
  - test_create_activity_create_includes_entity_data
  - test_record_activity_stores_in_outbox
  - test_record_activity_newest_first
  - test_get_outbox_returns_ordered_collection_page
  - test_get_outbox_pagination
  - test_get_outbox_next_link_when_more_pages
  - test_get_outbox_prev_link_when_not_first_page
  - test_get_followers_returns_empty_list_for_unknown_tablename
  - test_get_followers_returns_follower_list
  - test_get_federated_models_returns_empty_when_no_parent
  - test_get_federated_models_filters_by_federated_flag
  - test_webfinger_acct_format_collection_level
  - test_webfinger_acct_format_entity_level
  - test_webfinger_url_format
  - test_webfinger_returns_none_for_unknown_resource
  - test_webfinger_returns_none_for_wrong_domain

LIFECYCLE HANDLER TESTS — TX message handling
  - test_lifecycle_handler_receives_after_create_event
  - test_lifecycle_handler_receives_after_update_event
  - test_lifecycle_handler_receives_after_delete_event
  - test_lifecycle_handler_ignores_unknown_event
  - test_lifecycle_handler_ignores_non_federated_model
  - test_lifecycle_handler_creates_and_records_activity
  - test_lifecycle_handler_returns_recorded_status

INBOX HANDLER TESTS — inbound activity processing
  - test_handle_inbox_follow_adds_follower
  - test_handle_inbox_follow_idempotent
  - test_handle_inbox_unfollow_removes_follower
  - test_handle_inbox_unfollow_unknown_follower_silent
  - test_handle_inbox_create_routes_to_model
  - test_handle_inbox_update_routes_to_model
  - test_handle_inbox_delete_routes_to_model
  - test_handle_inbox_error_missing_type
  - test_handle_inbox_error_missing_actor

INTEGRATION TESTS — FastAPI route factory
  - test_create_federation_routes_returns_router
  - test_webfinger_route_returns_jrd_json
  - test_webfinger_route_404_for_unknown_resource
  - test_outbox_route_returns_activity_json
  - test_inbox_route_accepts_activity
  - test_inbox_route_400_for_invalid_json
  - test_inbox_route_422_for_missing_type

EDGE CASES
  - test_get_outbox_empty_outbox
  - test_create_activity_unknown_event_type_defaults_to_update
  - test_handle_inbox_undo_non_follow_activity
  - test_webfinger_acct_without_domain
  - test_generate_actor_document_includes_security_context
  - test_record_activity_multiple_tablenames_isolated

PRIVATE ATTR STATE
  - test_base_url_private_attr_initialization
  - test_outbox_private_attr_default_factory
  - test_followers_private_attr_default_factory
"""

import pytest
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from pydantic import Field

from pybend.core.api.network_ap import NetworkAP, create_federation_routes, AS_CONTEXT
from pybend.core.actors.tx import TX
from pybend.core.actors.actor import Actor
from pybend.core.actors.matrix import Matrix
from pybend.core.models.actor_model import ActorModel

pytestmark = pytest.mark.unit


# ===================================================================
# Test helper models
# ===================================================================

class _FederatedProduct(ActorModel, auto_register=False):
    """Mock federated model."""
    __tablename__: ClassVar[str] = 'products'
    __federated__: ClassVar[bool] = True
    name: str = Field(default='test')
    price: float = Field(default=0.0)


class _NonFederatedComment(ActorModel, auto_register=False):
    """Mock non-federated model."""
    __tablename__: ClassVar[str] = 'comments'
    __federated__: ClassVar[bool] = False
    text: str = Field(default='')


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture(autouse=True)
def reset_actor_state():
    """Save and restore Actor/Matrix class-level state between tests."""
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()
    saved_matrix_children = Matrix.__children__.copy()

    Actor.__matrix__ = None
    Actor.__children__ = {}
    Matrix.__children__ = {}

    yield

    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_children
    Matrix.__children__ = saved_matrix_children


@pytest.fixture
def fresh_matrix():
    """Create an isolated Matrix instance registered as root."""
    return Matrix()


@pytest.fixture
def ap_adapter(fresh_matrix):
    """Create NetworkAP adapter registered with Matrix."""
    ap = NetworkAP(base_url='https://example.com')
    fresh_matrix.register(ap)
    return ap


@pytest.fixture
def federated_model(fresh_matrix):
    """Register a federated model with Matrix."""
    fresh_matrix.register(_FederatedProduct)
    return _FederatedProduct


@pytest.fixture
def non_federated_model(fresh_matrix):
    """Register a non-federated model with Matrix."""
    fresh_matrix.register(_NonFederatedComment)
    return _NonFederatedComment


def make_tx(name='TEST', source='client', target='target', data=None, meta=None):
    """Shorthand TX constructor for tests."""
    return TX(name=name, source=source, target=target,
              data=data or {}, meta=meta or {})


# ===================================================================
# TestInitialization
# ===================================================================

class TestInitialization:
    """NetworkAP constructor and PrivateAttr state."""

    def test_initialization_defaults_addr_to_ap(self):
        ap = NetworkAP(base_url='https://example.com')
        assert ap.addr == 'ap'

    def test_initialization_strips_trailing_slash_from_base_url(self):
        ap = NetworkAP(base_url='https://example.com/')
        assert ap._base_url == 'https://example.com'

    def test_initialization_multiple_trailing_slashes(self):
        ap = NetworkAP(base_url='https://example.com///')
        # rstrip('/') removes all trailing slashes
        assert ap._base_url == 'https://example.com'

    def test_base_url_property_returns_stripped_url(self):
        ap = NetworkAP(base_url='https://example.com/')
        assert ap.base_url == 'https://example.com'

    def test_base_url_private_attr_initialization(self):
        ap = NetworkAP(base_url='https://test.org')
        assert hasattr(ap, '_base_url')
        assert ap._base_url == 'https://test.org'

    def test_outbox_private_attr_default_factory(self):
        ap = NetworkAP(base_url='https://example.com')
        assert hasattr(ap, '_outbox')
        assert isinstance(ap._outbox, dict)
        assert len(ap._outbox) == 0

    def test_followers_private_attr_default_factory(self):
        ap = NetworkAP(base_url='https://example.com')
        assert hasattr(ap, '_followers')
        assert isinstance(ap._followers, dict)
        assert len(ap._followers) == 0

    def test_custom_addr_can_be_provided(self):
        ap = NetworkAP(base_url='https://example.com', addr='federation')
        assert ap.addr == 'federation'


# ===================================================================
# TestActorDocumentGeneration
# ===================================================================

class TestActorDocumentGeneration:
    """generate_actor_document() creates AP Actor/Object documents."""

    def test_generate_actor_document_collection_level(self):
        ap = NetworkAP(base_url='https://example.com')
        doc = ap.generate_actor_document('products', 'Product')

        assert doc['@context'] == [AS_CONTEXT, 'https://w3id.org/security/v1']
        assert doc['id'] == 'https://example.com/products'
        assert doc['type'] == 'Service'
        assert doc['name'] == 'Product'
        assert doc['preferredUsername'] == 'products'
        assert doc['inbox'] == 'https://example.com/products/inbox'
        assert doc['outbox'] == 'https://example.com/products/outbox'
        assert doc['followers'] == 'https://example.com/products/followers'
        assert doc['following'] == 'https://example.com/products/following'
        assert doc['url'] == 'https://example.com/products'
        assert doc['summary'] == 'PyBend Product actor'
        assert doc['endpoints']['sharedInbox'] == 'https://example.com/inbox'

    def test_generate_actor_document_entity_level(self):
        ap = NetworkAP(base_url='https://example.com')
        doc = ap.generate_actor_document('products', 'Product', entity_id=42)

        assert doc['id'] == 'https://example.com/products/42'
        assert doc['type'] == 'Person'
        assert doc['name'] == 'Product #42'
        assert doc['preferredUsername'] == 'products-42'
        assert doc['inbox'] == 'https://example.com/products/42/inbox'
        assert doc['outbox'] == 'https://example.com/products/42/outbox'

    def test_generate_actor_document_includes_security_context(self):
        ap = NetworkAP(base_url='https://example.com')
        doc = ap.generate_actor_document('products', 'Product')

        assert 'https://w3id.org/security/v1' in doc['@context']


# ===================================================================
# TestActivityCreation
# ===================================================================

class TestActivityCreation:
    """create_activity() maps lifecycle events to AP Activities."""

    def test_create_activity_maps_after_create_to_create(self):
        ap = NetworkAP(base_url='https://example.com')
        entity = {'id': 1, 'name': 'Test'}
        activity = ap.create_activity('after_create', entity, 'products')

        assert activity['type'] == 'Create'
        assert activity['actor'] == 'https://example.com/products'
        assert '@context' in activity
        assert 'published' in activity

    def test_create_activity_maps_after_update_to_update(self):
        ap = NetworkAP(base_url='https://example.com')
        entity = {'id': 1, 'name': 'Updated'}
        activity = ap.create_activity('after_update', entity, 'products')

        assert activity['type'] == 'Update'

    def test_create_activity_maps_after_delete_to_delete(self):
        ap = NetworkAP(base_url='https://example.com')
        entity = {'id': 1}
        activity = ap.create_activity('after_delete', entity, 'products')

        assert activity['type'] == 'Delete'

    def test_create_activity_delete_creates_tombstone(self):
        ap = NetworkAP(base_url='https://example.com')
        entity = {'id': 1}
        activity = ap.create_activity('after_delete', entity, 'products')

        assert activity['object']['type'] == 'Tombstone'
        assert activity['object']['id'] == 'https://example.com/products/1'

    def test_create_activity_create_includes_entity_data(self):
        ap = NetworkAP(base_url='https://example.com')
        entity = {'id': 1, 'name': 'Widget', 'price': 9.99}
        activity = ap.create_activity('after_create', entity, 'products')

        obj = activity['object']
        assert obj['name'] == 'Widget'
        assert obj['price'] == 9.99
        # setdefault preserves existing 'id' from entity_data
        assert obj['id'] == 1
        assert obj['@context'] == AS_CONTEXT
        assert obj['type'] == 'Object'

    def test_create_activity_update_includes_entity_data(self):
        ap = NetworkAP(base_url='https://example.com')
        entity = {'id': 2, 'status': 'published'}
        activity = ap.create_activity('after_update', entity, 'products')

        obj = activity['object']
        assert obj['status'] == 'published'
        # setdefault preserves existing 'id' from entity_data
        assert obj['id'] == 2

    def test_create_activity_sets_url_when_id_not_in_entity(self):
        ap = NetworkAP(base_url='https://example.com')
        entity = {'name': 'Widget'}  # No 'id' key
        activity = ap.create_activity('after_create', entity, 'products')

        obj = activity['object']
        # setdefault adds the URL when 'id' is missing
        assert obj['id'] == 'https://example.com/products/'

    def test_create_activity_unknown_event_type_defaults_to_update(self):
        ap = NetworkAP(base_url='https://example.com')
        entity = {'id': 1}
        activity = ap.create_activity('unknown_event', entity, 'products')

        assert activity['type'] == 'Update'

    def test_create_activity_id_includes_timestamp(self):
        ap = NetworkAP(base_url='https://example.com')
        entity = {'id': 1}
        activity = ap.create_activity('after_create', entity, 'products')

        # ID format: {actor_url}/outbox/{type}-{entity_id}-{timestamp}
        assert '/outbox/create-1-' in activity['id']
        # Timestamp is YYYYMMDDHHMMSS
        assert len(activity['id'].split('-')[-1]) == 14

    def test_create_activity_published_is_iso_format(self):
        ap = NetworkAP(base_url='https://example.com')
        entity = {'id': 1}
        activity = ap.create_activity('after_create', entity, 'products')

        # Should be ISO 8601 format with timezone
        published = activity['published']
        assert 'T' in published
        assert '+' in published or 'Z' in published or published.endswith('+00:00')


# ===================================================================
# TestOutbox
# ===================================================================

class TestOutbox:
    """record_activity() and get_outbox() manage the outbox collection."""

    def test_record_activity_stores_in_outbox(self):
        ap = NetworkAP(base_url='https://example.com')
        activity = {'type': 'Create', 'id': '1'}
        ap.record_activity(activity, 'products')

        assert 'products' in ap._outbox
        assert activity in ap._outbox['products']

    def test_record_activity_newest_first(self):
        ap = NetworkAP(base_url='https://example.com')
        act1 = {'type': 'Create', 'id': '1'}
        act2 = {'type': 'Update', 'id': '2'}
        ap.record_activity(act1, 'products')
        ap.record_activity(act2, 'products')

        assert ap._outbox['products'][0] == act2
        assert ap._outbox['products'][1] == act1

    def test_record_activity_multiple_tablenames_isolated(self):
        ap = NetworkAP(base_url='https://example.com')
        act1 = {'type': 'Create', 'id': '1'}
        act2 = {'type': 'Create', 'id': '2'}
        ap.record_activity(act1, 'products')
        ap.record_activity(act2, 'comments')

        assert len(ap._outbox['products']) == 1
        assert len(ap._outbox['comments']) == 1
        assert ap._outbox['products'][0] == act1
        assert ap._outbox['comments'][0] == act2

    def test_get_outbox_returns_ordered_collection_page(self):
        ap = NetworkAP(base_url='https://example.com')
        activity = {'type': 'Create', 'id': '1'}
        ap.record_activity(activity, 'products')

        outbox = ap.get_outbox('products', page=1)

        assert outbox['@context'] == AS_CONTEXT
        assert outbox['type'] == 'OrderedCollectionPage'
        assert outbox['id'] == 'https://example.com/products/outbox?page=1'
        assert outbox['partOf'] == 'https://example.com/products/outbox'
        assert outbox['totalItems'] == 1
        assert activity in outbox['orderedItems']

    def test_get_outbox_empty_outbox(self):
        ap = NetworkAP(base_url='https://example.com')
        outbox = ap.get_outbox('products', page=1)

        assert outbox['totalItems'] == 0
        assert outbox['orderedItems'] == []

    def test_get_outbox_pagination(self):
        ap = NetworkAP(base_url='https://example.com')
        # Add 25 activities
        for i in range(25):
            ap.record_activity({'type': 'Create', 'id': str(i)}, 'products')

        page1 = ap.get_outbox('products', page=1, page_size=20)
        assert len(page1['orderedItems']) == 20
        assert page1['orderedItems'][0]['id'] == '24'  # newest first

        page2 = ap.get_outbox('products', page=2, page_size=20)
        assert len(page2['orderedItems']) == 5
        assert page2['orderedItems'][0]['id'] == '4'

    def test_get_outbox_next_link_when_more_pages(self):
        ap = NetworkAP(base_url='https://example.com')
        for i in range(25):
            ap.record_activity({'type': 'Create', 'id': str(i)}, 'products')

        page1 = ap.get_outbox('products', page=1, page_size=20)
        assert 'next' in page1
        assert page1['next'] == 'https://example.com/products/outbox?page=2'

    def test_get_outbox_no_next_link_on_last_page(self):
        ap = NetworkAP(base_url='https://example.com')
        for i in range(15):
            ap.record_activity({'type': 'Create', 'id': str(i)}, 'products')

        page1 = ap.get_outbox('products', page=1, page_size=20)
        assert 'next' not in page1

    def test_get_outbox_prev_link_when_not_first_page(self):
        ap = NetworkAP(base_url='https://example.com')
        for i in range(25):
            ap.record_activity({'type': 'Create', 'id': str(i)}, 'products')

        page2 = ap.get_outbox('products', page=2, page_size=20)
        assert 'prev' in page2
        assert page2['prev'] == 'https://example.com/products/outbox?page=1'

    def test_get_outbox_no_prev_link_on_first_page(self):
        ap = NetworkAP(base_url='https://example.com')
        for i in range(25):
            ap.record_activity({'type': 'Create', 'id': str(i)}, 'products')

        page1 = ap.get_outbox('products', page=1, page_size=20)
        assert 'prev' not in page1


# ===================================================================
# TestFollowers
# ===================================================================

class TestFollowers:
    """get_followers(), _handle_follow(), _handle_unfollow()."""

    def test_get_followers_returns_empty_list_for_unknown_tablename(self):
        ap = NetworkAP(base_url='https://example.com')
        followers = ap.get_followers('products')
        assert followers == []

    def test_get_followers_returns_follower_list(self):
        ap = NetworkAP(base_url='https://example.com')
        ap._followers['products'] = ['https://remote.example/user1']
        followers = ap.get_followers('products')
        assert followers == ['https://remote.example/user1']

    def test_handle_follow_adds_follower(self):
        ap = NetworkAP(base_url='https://example.com')
        result = ap._handle_follow('https://remote.example/user1', 'products')

        assert result['accepted'] is True
        assert result['type'] == 'follow'
        assert result['follower'] == 'https://remote.example/user1'
        assert 'https://remote.example/user1' in ap._followers['products']

    def test_handle_follow_idempotent(self):
        ap = NetworkAP(base_url='https://example.com')
        ap._handle_follow('https://remote.example/user1', 'products')
        ap._handle_follow('https://remote.example/user1', 'products')

        assert len(ap._followers['products']) == 1

    def test_handle_unfollow_removes_follower(self):
        ap = NetworkAP(base_url='https://example.com')
        ap._followers['products'] = ['https://remote.example/user1']
        result = ap._handle_unfollow('https://remote.example/user1', 'products')

        assert result['accepted'] is True
        assert result['type'] == 'undo_follow'
        assert 'https://remote.example/user1' not in ap._followers['products']

    def test_handle_unfollow_unknown_follower_silent(self):
        ap = NetworkAP(base_url='https://example.com')
        # Should not raise
        result = ap._handle_unfollow('https://remote.example/user1', 'products')
        assert result['accepted'] is True


# ===================================================================
# TestLifecycleHandler
# ===================================================================

class TestLifecycleHandler:
    """LIFECYCLE() handler receives lifecycle events from ActorModel."""

    def test_lifecycle_handler_receives_after_create_event(self, ap_adapter, federated_model):
        tx = make_tx(
            name='LIFECYCLE',
            source='products',
            target='ap',
            data={
                'event': 'after_create',
                'entity': {'id': 1, 'name': 'Widget'},
            }
        )

        result = ap_adapter.LIFECYCLE(tx.data, tx)

        assert result['recorded'] is True
        assert result['type'] == 'Create'
        assert 'products' in ap_adapter._outbox

    def test_lifecycle_handler_receives_after_update_event(self, ap_adapter, federated_model):
        tx = make_tx(
            name='LIFECYCLE',
            source='products',
            target='ap',
            data={
                'event': 'after_update',
                'entity': {'id': 1, 'name': 'Updated'},
            }
        )

        result = ap_adapter.LIFECYCLE(tx.data, tx)

        assert result['recorded'] is True
        assert result['type'] == 'Update'

    def test_lifecycle_handler_receives_after_delete_event(self, ap_adapter, federated_model):
        tx = make_tx(
            name='LIFECYCLE',
            source='products',
            target='ap',
            data={
                'event': 'after_delete',
                'entity': {'id': 1},
            }
        )

        result = ap_adapter.LIFECYCLE(tx.data, tx)

        assert result['recorded'] is True
        assert result['type'] == 'Delete'

    def test_lifecycle_handler_ignores_unknown_event(self, ap_adapter, federated_model):
        tx = make_tx(
            name='LIFECYCLE',
            source='products',
            target='ap',
            data={
                'event': 'unknown_event',
                'entity': {'id': 1},
            }
        )

        result = ap_adapter.LIFECYCLE(tx.data, tx)

        assert result['ignored'] is True
        assert 'Unknown event' in result['reason']

    def test_lifecycle_handler_ignores_non_federated_model(self, ap_adapter, non_federated_model):
        tx = make_tx(
            name='LIFECYCLE',
            source='comments',
            target='ap',
            data={
                'event': 'after_create',
                'entity': {'id': 1, 'text': 'Test'},
            }
        )

        result = ap_adapter.LIFECYCLE(tx.data, tx)

        assert result['ignored'] is True
        assert 'not federated' in result['reason']

    def test_lifecycle_handler_creates_and_records_activity(self, ap_adapter, federated_model):
        tx = make_tx(
            name='LIFECYCLE',
            source='products',
            target='ap',
            data={
                'event': 'after_create',
                'entity': {'id': 42, 'name': 'Gadget'},
            }
        )

        ap_adapter.LIFECYCLE(tx.data, tx)

        assert 'products' in ap_adapter._outbox
        assert len(ap_adapter._outbox['products']) == 1
        activity = ap_adapter._outbox['products'][0]
        assert activity['type'] == 'Create'
        assert activity['object']['name'] == 'Gadget'

    def test_lifecycle_handler_returns_recorded_status(self, ap_adapter, federated_model):
        tx = make_tx(
            name='LIFECYCLE',
            source='products',
            target='ap',
            data={
                'event': 'after_create',
                'entity': {'id': 1},
            }
        )

        result = ap_adapter.LIFECYCLE(tx.data, tx)

        assert 'recorded' in result
        assert 'type' in result


# ===================================================================
# TestInboxHandler
# ===================================================================

class TestInboxHandler:
    """handle_inbox() processes inbound AP activities."""

    @pytest.mark.asyncio
    async def test_handle_inbox_follow_adds_follower(self):
        ap = NetworkAP(base_url='https://example.com')
        activity = {
            'type': 'Follow',
            'actor': 'https://remote.example/user1',
            'object': 'https://example.com/products',
        }

        result = await ap.handle_inbox(activity, 'products')

        assert result['accepted'] is True
        assert result['type'] == 'follow'
        assert 'https://remote.example/user1' in ap._followers['products']

    @pytest.mark.asyncio
    async def test_handle_inbox_follow_idempotent(self):
        ap = NetworkAP(base_url='https://example.com')
        activity = {
            'type': 'Follow',
            'actor': 'https://remote.example/user1',
            'object': 'https://example.com/products',
        }

        await ap.handle_inbox(activity, 'products')
        await ap.handle_inbox(activity, 'products')

        assert len(ap._followers['products']) == 1

    @pytest.mark.asyncio
    async def test_handle_inbox_unfollow_removes_follower(self):
        ap = NetworkAP(base_url='https://example.com')
        ap._followers['products'] = ['https://remote.example/user1']

        activity = {
            'type': 'Undo',
            'actor': 'https://remote.example/user1',
            'object': {
                'type': 'Follow',
                'actor': 'https://remote.example/user1',
                'object': 'https://example.com/products',
            }
        }

        result = await ap.handle_inbox(activity, 'products')

        assert result['accepted'] is True
        assert result['type'] == 'undo_follow'
        assert 'https://remote.example/user1' not in ap._followers['products']

    @pytest.mark.asyncio
    async def test_handle_inbox_unfollow_unknown_follower_silent(self):
        ap = NetworkAP(base_url='https://example.com')
        activity = {
            'type': 'Undo',
            'actor': 'https://remote.example/user1',
            'object': {
                'type': 'Follow',
                'actor': 'https://remote.example/user1',
                'object': 'https://example.com/products',
            }
        }

        result = await ap.handle_inbox(activity, 'products')
        assert result['accepted'] is True

    @pytest.mark.asyncio
    async def test_handle_inbox_create_routes_to_model(self, fresh_matrix):
        ap = NetworkAP(base_url='https://example.com')
        fresh_matrix.register(ap)

        # Mock send to capture TX
        send_mock = AsyncMock()
        object.__setattr__(ap, 'send', send_mock)

        activity = {
            'type': 'Create',
            'actor': 'https://remote.example/user1',
            'object': {'id': '1', 'content': 'test'},
        }

        result = await ap.handle_inbox(activity, 'products')

        assert result['accepted'] is True
        assert result['type'] == 'create'
        send_mock.assert_called_once()
        tx = send_mock.call_args[0][0]
        assert tx.name == 'create'
        assert tx.target == 'products'
        assert tx.source == 'https://remote.example/user1'
        assert tx.data == {'id': '1', 'content': 'test'}
        assert tx.meta['federated'] is True

    @pytest.mark.asyncio
    async def test_handle_inbox_update_routes_to_model(self, fresh_matrix):
        ap = NetworkAP(base_url='https://example.com')
        fresh_matrix.register(ap)

        send_mock = AsyncMock()
        object.__setattr__(ap, 'send', send_mock)

        activity = {
            'type': 'Update',
            'actor': 'https://remote.example/user1',
            'object': {'id': '1', 'content': 'updated'},
        }

        await ap.handle_inbox(activity, 'products')

        tx = send_mock.call_args[0][0]
        assert tx.name == 'update'

    @pytest.mark.asyncio
    async def test_handle_inbox_delete_routes_to_model(self, fresh_matrix):
        ap = NetworkAP(base_url='https://example.com')
        fresh_matrix.register(ap)

        send_mock = AsyncMock()
        object.__setattr__(ap, 'send', send_mock)

        activity = {
            'type': 'Delete',
            'actor': 'https://remote.example/user1',
            'object': 'https://example.com/products/1',
        }

        await ap.handle_inbox(activity, 'products')

        tx = send_mock.call_args[0][0]
        assert tx.name == 'delete'
        # Object is a string, should be wrapped in dict
        assert tx.data == {'id': 'https://example.com/products/1'}

    @pytest.mark.asyncio
    async def test_handle_inbox_error_missing_type(self):
        ap = NetworkAP(base_url='https://example.com')
        activity = {
            'actor': 'https://remote.example/user1',
        }

        result = await ap.handle_inbox(activity, 'products')

        assert 'error' in result
        assert 'type' in result['error']

    @pytest.mark.asyncio
    async def test_handle_inbox_error_missing_actor(self):
        ap = NetworkAP(base_url='https://example.com')
        activity = {
            'type': 'Create',
        }

        result = await ap.handle_inbox(activity, 'products')

        assert 'error' in result
        assert 'actor' in result['error']

    @pytest.mark.asyncio
    async def test_handle_inbox_undo_non_follow_activity(self):
        ap = NetworkAP(base_url='https://example.com')
        activity = {
            'type': 'Undo',
            'actor': 'https://remote.example/user1',
            'object': {
                'type': 'Like',  # Not a Follow
                'actor': 'https://remote.example/user1',
            }
        }

        result = await ap.handle_inbox(activity, 'products')

        assert result['accepted'] is True
        assert result['type'] == 'undo'


# ===================================================================
# TestWebFinger
# ===================================================================

class TestWebFinger:
    """webfinger() resolves WebFinger resources to AP actor links."""

    def test_webfinger_acct_format_collection_level(self, fresh_matrix):
        ap = NetworkAP(base_url='https://example.com')
        fresh_matrix.register(ap)
        fresh_matrix.register(_FederatedProduct)

        result = ap.webfinger('acct:products@example.com')

        assert result is not None
        assert result['subject'] == 'acct:products@example.com'
        assert 'https://example.com/products' in result['aliases']
        assert result['links'][0]['rel'] == 'self'
        assert result['links'][0]['type'] == 'application/activity+json'
        assert result['links'][0]['href'] == 'https://example.com/products'

    def test_webfinger_acct_format_entity_level(self, fresh_matrix):
        ap = NetworkAP(base_url='https://example.com')
        fresh_matrix.register(ap)
        fresh_matrix.register(_FederatedProduct)

        result = ap.webfinger('acct:products-42@example.com')

        assert result is not None
        assert result['subject'] == 'acct:products-42@example.com'
        assert 'https://example.com/products/42' in result['aliases']
        assert result['links'][0]['href'] == 'https://example.com/products/42'

    def test_webfinger_url_format(self, fresh_matrix):
        ap = NetworkAP(base_url='https://example.com')
        fresh_matrix.register(ap)
        fresh_matrix.register(_FederatedProduct)

        result = ap.webfinger('https://example.com/products')

        assert result is not None
        assert result['aliases'] == ['https://example.com/products']
        assert result['subject'] == 'acct:products@example.com'

    def test_webfinger_returns_none_for_unknown_resource(self, fresh_matrix):
        ap = NetworkAP(base_url='https://example.com')
        fresh_matrix.register(ap)

        result = ap.webfinger('acct:unknown@example.com')

        assert result is None

    def test_webfinger_returns_none_for_wrong_domain(self, fresh_matrix):
        ap = NetworkAP(base_url='https://example.com')
        fresh_matrix.register(ap)
        fresh_matrix.register(_FederatedProduct)

        result = ap.webfinger('acct:products@otherdomain.com')

        assert result is None

    def test_webfinger_acct_without_domain(self, fresh_matrix):
        ap = NetworkAP(base_url='https://example.com')
        fresh_matrix.register(ap)
        fresh_matrix.register(_FederatedProduct)

        result = ap.webfinger('acct:products')

        assert result is not None
        # Should match against example.com domain

    def test_webfinger_returns_none_when_no_base_url(self):
        ap = NetworkAP(base_url='')
        result = ap.webfinger('acct:products@example.com')
        assert result is None

    def test_webfinger_url_not_matching_base_url(self):
        ap = NetworkAP(base_url='https://example.com')
        result = ap.webfinger('https://otherdomain.com/products')
        assert result is None


# ===================================================================
# TestFederatedModelDiscovery
# ===================================================================

class TestFederatedModelDiscovery:
    """get_federated_models() discovers models with __federated__ = True."""

    def test_get_federated_models_returns_empty_when_no_parent(self):
        ap = NetworkAP(base_url='https://example.com')
        # Not registered with Matrix, no parent
        models = ap.get_federated_models()
        assert models == []

    def test_get_federated_models_filters_by_federated_flag(self, fresh_matrix):
        ap = NetworkAP(base_url='https://example.com')
        fresh_matrix.register(ap)
        fresh_matrix.register(_FederatedProduct)
        fresh_matrix.register(_NonFederatedComment)

        models = ap.get_federated_models()

        assert len(models) == 1
        addr, cls = models[0]
        assert addr == 'products'
        assert cls is _FederatedProduct

    def test_get_federated_models_returns_empty_when_no_federated_models(self, fresh_matrix):
        ap = NetworkAP(base_url='https://example.com')
        fresh_matrix.register(ap)
        fresh_matrix.register(_NonFederatedComment)

        models = ap.get_federated_models()

        assert models == []

    def test_get_federated_models_returns_multiple_models(self, fresh_matrix):
        class _FederatedWidget(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'widgets'
            __federated__: ClassVar[bool] = True
            name: str = Field(default='')

        ap = NetworkAP(base_url='https://example.com')
        fresh_matrix.register(ap)
        fresh_matrix.register(_FederatedProduct)
        fresh_matrix.register(_FederatedWidget)

        models = ap.get_federated_models()

        assert len(models) == 2
        addrs = [addr for addr, cls in models]
        assert 'products' in addrs
        assert 'widgets' in addrs


# ===================================================================
# TestFederationRoutes
# ===================================================================

class TestFederationRoutes:
    """create_federation_routes() FastAPI route factory."""

    def test_create_federation_routes_returns_router(self):
        ap = NetworkAP(base_url='https://example.com')
        router = create_federation_routes(ap)

        from fastapi import APIRouter
        assert isinstance(router, APIRouter)

    def test_create_federation_routes_has_correct_tags(self):
        ap = NetworkAP(base_url='https://example.com')
        router = create_federation_routes(ap)

        assert router.tags == ['Federation']

    @pytest.mark.asyncio
    async def test_webfinger_route_returns_jrd_json(self, fresh_matrix):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        ap = NetworkAP(base_url='https://example.com')
        fresh_matrix.register(ap)
        fresh_matrix.register(_FederatedProduct)

        app = FastAPI()
        app.include_router(create_federation_routes(ap))
        client = TestClient(app)

        response = client.get('/.well-known/webfinger?resource=acct:products@example.com')

        assert response.status_code == 200
        assert response.headers['content-type'] == 'application/jrd+json'
        data = response.json()
        assert data['subject'] == 'acct:products@example.com'

    @pytest.mark.asyncio
    async def test_webfinger_route_404_for_unknown_resource(self, fresh_matrix):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        ap = NetworkAP(base_url='https://example.com')
        fresh_matrix.register(ap)

        app = FastAPI()
        app.include_router(create_federation_routes(ap))
        client = TestClient(app)

        response = client.get('/.well-known/webfinger?resource=acct:unknown@example.com')

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_outbox_route_returns_activity_json(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        ap = NetworkAP(base_url='https://example.com')
        activity = {'type': 'Create', 'id': '1'}
        ap.record_activity(activity, 'products')

        app = FastAPI()
        app.include_router(create_federation_routes(ap))
        client = TestClient(app)

        response = client.get('/products/outbox')

        assert response.status_code == 200
        assert response.headers['content-type'] == 'application/activity+json'
        data = response.json()
        assert data['type'] == 'OrderedCollectionPage'
        assert activity in data['orderedItems']

    @pytest.mark.asyncio
    async def test_inbox_route_accepts_activity(self, fresh_matrix):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        ap = NetworkAP(base_url='https://example.com')
        fresh_matrix.register(ap)

        app = FastAPI()
        app.include_router(create_federation_routes(ap))
        client = TestClient(app)

        activity = {
            'type': 'Follow',
            'actor': 'https://remote.example/user1',
            'object': 'https://example.com/products',
        }

        response = client.post('/products/inbox', json=activity)

        assert response.status_code == 202
        assert response.headers['content-type'] == 'application/activity+json'
        data = response.json()
        assert data['accepted'] is True

    @pytest.mark.asyncio
    async def test_inbox_route_400_for_invalid_json(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        ap = NetworkAP(base_url='https://example.com')

        app = FastAPI()
        app.include_router(create_federation_routes(ap))
        client = TestClient(app)

        response = client.post(
            '/products/inbox',
            data='invalid json',
            headers={'Content-Type': 'application/json'}
        )

        assert response.status_code == 400
        data = response.json()
        assert 'error' in data

    @pytest.mark.asyncio
    async def test_inbox_route_422_for_missing_type(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        ap = NetworkAP(base_url='https://example.com')

        app = FastAPI()
        app.include_router(create_federation_routes(ap))
        client = TestClient(app)

        activity = {
            'actor': 'https://remote.example/user1',
            # Missing 'type'
        }

        response = client.post('/products/inbox', json=activity)

        assert response.status_code == 422
