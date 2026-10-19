"""Tests for ViewableMixin injection and schema output (n3tx-ui)."""

import pytest

import n3tx_ui  # side-effect: registers ViewableMixin via register_mixin()
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from n3tx_core.app import create_app
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import registered_models
from n3tx_ui.mixin import (
    ViewableMixin,
    html_attr,
    resolve_collection_view_tag,
    resolve_member_view_tag,
    validate_component_tag,
    validate_view_token,
)
from n3tx_core.utils.decorators import expose_route
from pydantic import Field
from typing import ClassVar


# ===================================================================
# Injection
# ===================================================================

class TestInjection:

    def test_explicit_flag_injects_mixin(self):
        class Flagged(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_flagged'
            __viewable__ = True
        assert issubclass(Flagged, ViewableMixin)

    def test_ui_dict_guardrail_injects_mixin(self):
        class WithUI(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_withui'
            __ui__ = {'field_order': ['name']}
        assert issubclass(WithUI, ViewableMixin)
        assert WithUI.__viewable__ is True

    def test_plain_model_no_mixin(self):
        class Plain(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_plain'
        assert not issubclass(Plain, ViewableMixin)

    def test_false_flag_no_injection(self):
        class NotViewable(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_not_viewable'
            __viewable__ = False
        assert not issubclass(NotViewable, ViewableMixin)


# ===================================================================
# View routes
# ===================================================================

class TestViewRoutes:

    def test_register_view_routes_adds_collection_default_html_route(self):
        class ViewRouteProduct(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_view_route_products'
            __ui__ = {'renderer': {'page': 'ntx-products-page', 'list': 'ntx-products'}}
            name: str = Field(default='')

        router = APIRouter()
        ViewRouteProduct.register_view_routes(router, tag='Products')

        route = next(r for r in router.routes if getattr(r, 'path', None) == '/ViewRouteProduct/@')
        assert 'GET' in route.methods
        assert route.include_in_schema is False

        named_route = next(r for r in router.routes if getattr(r, 'path', None) == '/ViewRouteProduct/@{view}')
        assert 'GET' in named_route.methods
        assert named_route.include_in_schema is False

        member_route = next(r for r in router.routes if getattr(r, 'path', None) == '/ViewRouteProduct/{id:int}/@')
        assert 'GET' in member_route.methods
        assert member_route.include_in_schema is False

        app = FastAPI()
        app.include_router(router)
        response = TestClient(app).get('/ViewRouteProduct/@')

        assert response.status_code == 200
        assert 'text/html' in response.headers['content-type']
        assert '<ntx-products-page model="ViewRouteProduct"' in response.text

    def test_member_default_html_route_uses_detail_renderer(self):
        class ViewRouteDetail(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_view_route_details'
            __ui__ = {'renderer': {'detail': 'ntx-product-detail', 'item': 'ntx-product-card'}}
            name: str = Field(default='')

        assert resolve_member_view_tag(ViewRouteDetail) == 'ntx-product-detail'

        router = APIRouter()
        ViewRouteDetail.register_view_routes(router, tag='Details')
        app = FastAPI()
        app.include_router(router)

        response = TestClient(app).get('/ViewRouteDetail/1/@')
        assert response.status_code == 200
        assert 'text/html' in response.headers['content-type']
        assert '<ntx-product-detail ref="ViewRouteDetail/1" display="lg"' in response.text
        assert '<script type="module" src="/components/ntx-product-detail.js"></script>' in response.text

    def test_member_default_html_route_falls_back_to_item_renderer(self):
        class ViewRouteItem(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_view_route_items'
            __ui__ = {'renderer': {'item': 'ntx-product-card'}}
            name: str = Field(default='')

        assert resolve_member_view_tag(ViewRouteItem) == 'ntx-product-card'

        router = APIRouter()
        ViewRouteItem.register_view_routes(router, tag='Items')
        app = FastAPI()
        app.include_router(router)

        response = TestClient(app).get('/ViewRouteItem/2/@')
        assert response.status_code == 200
        assert '<ntx-product-card ref="ViewRouteItem/2" display="lg"' in response.text

    def test_member_default_html_route_falls_back_to_ntx_item(self):
        class ViewRouteMemberFallback(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_view_route_member_fallbacks'
            __viewable__ = True
            name: str = Field(default='')

        assert resolve_member_view_tag(ViewRouteMemberFallback) == 'ntx-item'

        router = APIRouter()
        ViewRouteMemberFallback.register_view_routes(router, tag='MemberFallbacks')
        app = FastAPI()
        app.include_router(router)

        response = TestClient(app).get('/ViewRouteMemberFallback/3/@')
        assert response.status_code == 200
        assert '<ntx-item ref="ViewRouteMemberFallback/3" display="lg"' in response.text
        assert response.text.count('/components/ntx-item.js') == 1

    def test_member_named_html_route_uses_schema_renderer(self):
        class ViewRouteNamedMember(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_view_route_named_members'
            __ui__ = {'renderer': {'item': 'ntx-product-card', 'chat': 'ntx-product-chat'}}
            name: str = Field(default='')

        assert resolve_member_view_tag(ViewRouteNamedMember, 'item') == 'ntx-product-card'
        assert resolve_member_view_tag(ViewRouteNamedMember, 'chat') == 'ntx-product-chat'

        router = APIRouter()
        ViewRouteNamedMember.register_view_routes(router, tag='NamedMembers')
        route = next(r for r in router.routes if getattr(r, 'path', None) == '/ViewRouteNamedMember/{id:int}/@{view}')
        assert 'GET' in route.methods
        assert route.include_in_schema is False

        app = FastAPI()
        app.include_router(router)

        response = TestClient(app).get('/ViewRouteNamedMember/4/@chat')
        assert response.status_code == 200
        assert 'text/html' in response.headers['content-type']
        assert '<ntx-product-chat ref="ViewRouteNamedMember/4" display="lg"' in response.text

    def test_member_named_html_route_uses_known_fallbacks_and_rejects_unknown(self):
        class ViewRouteNamedMemberFallback(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_view_route_named_member_fallbacks'
            __viewable__ = True
            name: str = Field(default='')

        assert resolve_member_view_tag(ViewRouteNamedMemberFallback, 'item') == 'ntx-item'
        assert resolve_member_view_tag(ViewRouteNamedMemberFallback, 'detail') == 'ntx-item'
        assert resolve_member_view_tag(ViewRouteNamedMemberFallback, 'chat') == 'ntx-chat'
        with pytest.raises(ValueError, match='Unknown view name'):
            resolve_member_view_tag(ViewRouteNamedMemberFallback, 'custom-card')

        router = APIRouter()
        ViewRouteNamedMemberFallback.register_view_routes(router, tag='NamedMemberFallbacks')
        app = FastAPI()
        app.include_router(router)

        chat_response = TestClient(app).get('/ViewRouteNamedMemberFallback/5/@chat')
        assert chat_response.status_code == 200
        assert '<ntx-chat ref="ViewRouteNamedMemberFallback/5" display="lg"' in chat_response.text

        custom_response = TestClient(app).get('/ViewRouteNamedMemberFallback/5/@custom-card')
        assert custom_response.status_code == 400
        assert custom_response.json()['detail'] == 'Unknown view name'

    def test_member_named_run_view_does_not_mount_method_attrs(self):
        class ViewRouteRunCollision(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_view_route_run_collisions'
            __ui__ = {'renderer': {'run': 'ntx-run-view'}}
            name: str = Field(default='')

            @expose_route('/run', methods=['POST'])
            def run(self) -> str:
                return 'ran'

        router = APIRouter()
        ViewRouteRunCollision.register_view_routes(router, tag='RunCollisions')
        app = FastAPI()
        app.include_router(router)

        response = TestClient(app).get('/ViewRouteRunCollision/6/@run')
        assert response.status_code == 200
        assert '<ntx-run-view ref="ViewRouteRunCollision/6" display="lg"' in response.text
        assert 'method=' not in response.text

    def test_named_collection_html_route_uses_schema_renderer(self):
        class ViewRouteTable(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_view_route_tables'
            __ui__ = {'renderer': {'table': 'ntx-product-table'}}
            name: str = Field(default='')

        router = APIRouter()
        ViewRouteTable.register_view_routes(router, tag='Tables')
        app = FastAPI()
        app.include_router(router)

        response = TestClient(app).get('/ViewRouteTable/@table')
        assert response.status_code == 200
        assert 'text/html' in response.headers['content-type']
        assert '<ntx-product-table model="ViewRouteTable"' in response.text
        assert '<script type="module" src="/components/ntx-product-table.js"></script>' in response.text

    def test_named_collection_html_route_uses_known_fallbacks_and_rejects_unknown(self):
        class ViewRouteNamedFallback(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_view_route_named_fallbacks'
            __viewable__ = True
            name: str = Field(default='')

        assert resolve_collection_view_tag(ViewRouteNamedFallback, 'table') == 'ntx-table'
        assert resolve_collection_view_tag(ViewRouteNamedFallback, 'list') == 'ntx-list'
        with pytest.raises(ValueError, match='Unknown view name'):
            resolve_collection_view_tag(ViewRouteNamedFallback, 'custom-card')
        with pytest.raises(ValueError, match='Unknown view name'):
            resolve_collection_view_tag(ViewRouteNamedFallback, 'ntx-custom-card')

        router = APIRouter()
        ViewRouteNamedFallback.register_view_routes(router, tag='NamedFallbacks')
        app = FastAPI()
        app.include_router(router)

        table_response = TestClient(app).get('/ViewRouteNamedFallback/@table')
        assert table_response.status_code == 200
        assert '<ntx-table model="ViewRouteNamedFallback"' in table_response.text

        custom_response = TestClient(app).get('/ViewRouteNamedFallback/@custom-card')
        assert custom_response.status_code == 400
        assert custom_response.json()['detail'] == 'Unknown view name'

    def test_custom_views_are_allowed_when_schema_declares_renderer(self):
        class ViewRouteDeclaredCustom(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_view_route_declared_customs'
            __ui__ = {'renderer': {'custom-card': 'ntx-custom-card', '0': 'ntx-zero-view'}}
            name: str = Field(default='')

        assert resolve_collection_view_tag(ViewRouteDeclaredCustom, 'custom-card') == 'ntx-custom-card'
        assert resolve_member_view_tag(ViewRouteDeclaredCustom, '0') == 'ntx-zero-view'

        router = APIRouter()
        ViewRouteDeclaredCustom.register_view_routes(router, tag='DeclaredCustoms')
        app = FastAPI()
        app.include_router(router)

        collection_response = TestClient(app).get('/ViewRouteDeclaredCustom/@custom-card')
        assert collection_response.status_code == 200
        assert '<ntx-custom-card model="ViewRouteDeclaredCustom"' in collection_response.text

        member_response = TestClient(app).get('/ViewRouteDeclaredCustom/7/@0')
        assert member_response.status_code == 200
        assert '<ntx-zero-view ref="ViewRouteDeclaredCustom/7" display="lg"' in member_response.text

    def test_view_token_and_tag_helpers_validate_safety(self):
        for token in ['table', 'custom-card', 'ntx-custom-card', '0', 'view_2']:
            assert validate_view_token(token) == token

        for token in ['../x', '../../x', 'x/y', 'x.y', 'x y', '<script>', '', '@evil']:
            with pytest.raises(ValueError, match='Invalid view name'):
                validate_view_token(token)

        for tag in ['ntx-list', 'ntx-custom-card', 'ntx-zero-view']:
            assert validate_component_tag(tag) == tag

        for tag in ['script', 'div', 'ntx', 'ntx/<bad>', 'ntx-<script>']:
            with pytest.raises(ValueError, match='Invalid renderer tag'):
                validate_component_tag(tag)

        assert html_attr('a"<b>') == 'a&quot;&lt;b&gt;'

    def test_unsafe_backend_view_tokens_return_400(self):
        class ViewRouteUnsafeToken(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_view_route_unsafe_tokens'
            __viewable__ = True
            name: str = Field(default='')

        router = APIRouter()
        ViewRouteUnsafeToken.register_view_routes(router, tag='UnsafeTokens')
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        assert client.get('/ViewRouteUnsafeToken/@%2e%2e').status_code == 400
        assert client.get('/ViewRouteUnsafeToken/1/@%2e%2e').status_code == 400
        assert client.get('/ViewRouteUnsafeToken/@%3Cscript%3E').status_code == 400

    def test_extra_backend_view_segments_remain_404(self):
        class ViewRouteExtraSegment(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_view_route_extra_segments'
            __ui__ = {'renderer': {'table': 'ntx-table', 'item': 'ntx-item'}}
            name: str = Field(default='')

        router = APIRouter()
        ViewRouteExtraSegment.register_view_routes(router, tag='ExtraSegments')
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        assert client.get('/ViewRouteExtraSegment/@table/extra').status_code == 404
        assert client.get('/ViewRouteExtraSegment/1/@item/extra').status_code == 404

    def test_invalid_schema_renderer_tag_returns_400(self):
        class ViewRouteInvalidRenderer(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_view_route_invalid_renderers'
            __ui__ = {'renderer': {'table': 'script'}}
            name: str = Field(default='')

        router = APIRouter()
        ViewRouteInvalidRenderer.register_view_routes(router, tag='InvalidRenderers')
        app = FastAPI()
        app.include_router(router)

        response = TestClient(app).get('/ViewRouteInvalidRenderer/@table')
        assert response.status_code == 400
        assert response.json()['detail'] == 'Invalid renderer tag'

    def test_collection_default_html_route_falls_back_to_ntx_list(self):
        class ViewRouteFallback(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_view_route_fallbacks'
            __viewable__ = True
            name: str = Field(default='')

        router = APIRouter()
        ViewRouteFallback.register_view_routes(router, tag='Fallbacks')

        app = FastAPI()
        app.include_router(router)
        response = TestClient(app).get('/ViewRouteFallback/@')

        assert response.status_code == 200
        assert '<ntx-list model="ViewRouteFallback"' in response.text
        assert response.text.count('/components/ntx-list.js') == 1

    def test_create_app_registers_viewable_collection_default_route(self, tmp_path):
        saved = dict(registered_models)
        registered_models.clear()
        try:
            class AppViewRouteProduct(ProtoModel):
                __tablename__: ClassVar[str] = 'app_view_route_products'
                __storable__: ClassVar[bool] = True
                __ui__ = {'renderer': {'page': 'ntx-app-products-page'}}
                name: str = Field(default='')

            app = create_app(
                models=[AppViewRouteProduct],
                storage=SQLiteStorage(str(tmp_path / 'view_routes.db')),
                static_dir=None,
            )
            client = TestClient(app)

            html_response = client.get('/AppViewRouteProduct/@')
            assert html_response.status_code == 200
            assert 'text/html' in html_response.headers['content-type']
            assert '<ntx-app-products-page model="AppViewRouteProduct"' in html_response.text

            named_response = client.get('/AppViewRouteProduct/@table')
            assert named_response.status_code == 200
            assert '<ntx-table model="AppViewRouteProduct"' in named_response.text

            member_response = client.get('/AppViewRouteProduct/1/@')
            assert member_response.status_code == 200
            assert '<ntx-item ref="AppViewRouteProduct/1" display="lg"' in member_response.text

            named_member_response = client.get('/AppViewRouteProduct/1/@chat')
            assert named_member_response.status_code == 200
            assert '<ntx-chat ref="AppViewRouteProduct/1" display="lg"' in named_member_response.text

            schema_response = client.get('/AppViewRouteProduct')
            assert schema_response.status_code == 200
            assert schema_response.json()['__name__'] == 'AppViewRouteProduct'

            list_response = client.get('/app_view_route_products')
            assert list_response.status_code == 200
        finally:
            registered_models.clear()
            registered_models.update(saved)


# ===================================================================
# Schema output
# ===================================================================

class TestSchemaOutput:

    def test_ui_config_in_schema(self):
        class Viewable(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_vschema'
            __ui__ = {'field_order': ['name']}
            name: str = Field(default='')

        Viewable.invalidate_schema_cache()
        s = Viewable.schema()
        assert 'ui' in s
        assert s['ui']['field_order'] == ['name']

    def test_ui_groups_in_schema(self):
        class Grouped(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_grouped'
            __ui__ = {
                'field_order': ['name', 'value'],
                'groups': {'main': ['name', 'value']},
            }
            name: str = Field(default='')
            value: int = Field(default=0)

        Grouped.invalidate_schema_cache()
        s = Grouped.schema()
        assert s['ui']['groups'] == {'main': ['name', 'value']}

    def test_model_icon_in_schema(self):
        class WithIcon(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_with_icon'
            __ui__ = {'icon': '📚'}
            name: str = Field(default='')

        WithIcon.invalidate_schema_cache()
        s = WithIcon.schema()
        assert s['ui']['icon'] == '📚'

    def test_model_lookup_icon_in_schema(self):
        class WithLookupIcon(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_with_lookup_icon'
            __ui__ = {'icon': 'books'}
            name: str = Field(default='')

        WithLookupIcon.invalidate_schema_cache()
        s = WithLookupIcon.schema()
        assert s['ui']['icon'] == 'books'

    def test_method_ui_hints(self):
        class WithMethodUI(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_method_ui'
            __ui__ = {'methods': {'ping': {'icon': 'send'}}}
            name: str = Field(default='')

            @expose_route('/ping', methods=['POST'])
            def ping(self) -> str:
                return 'pong'

        WithMethodUI.invalidate_schema_cache()
        s = WithMethodUI.schema()
        assert s['methods']['ping']['ui'] == {'icon': 'send'}

    def test_method_emoji_icon_hints(self):
        class WithMethodEmoji(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_method_emoji'
            __ui__ = {'methods': {'ping': {'icon': '🔎'}}}
            name: str = Field(default='')

            @expose_route('/ping', methods=['POST'])
            def ping(self) -> str:
                return 'pong'

        WithMethodEmoji.invalidate_schema_cache()
        s = WithMethodEmoji.schema()
        assert s['methods']['ping']['ui']['icon'] == '🔎'

    def test_method_lookup_icon_hints(self):
        class WithMethodLookup(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_method_lookup'
            __ui__ = {'methods': {'ping': {'icon': 'analyze'}}}
            name: str = Field(default='')

            @expose_route('/ping', methods=['POST'])
            def ping(self) -> str:
                return 'pong'

        WithMethodLookup.invalidate_schema_cache()
        s = WithMethodLookup.schema()
        assert s['methods']['ping']['ui']['icon'] == 'analyze'

    def test_viewable_flag_no_ui_config(self):
        class ViewableNoConfig(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_vno_config'
            __viewable__ = True
            # no __ui__

        ViewableNoConfig.invalidate_schema_cache()
        s = ViewableNoConfig.schema()
        assert 'ui' not in s  # viewable but no config → no ui key

    def test_plain_model_no_ui_key(self):
        class PlainModel(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_plain2'
            name: str = Field(default='')

        PlainModel.invalidate_schema_cache()
        s = PlainModel.schema()
        assert 'ui' not in s
