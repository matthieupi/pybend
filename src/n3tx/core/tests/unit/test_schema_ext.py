"""
Tests for actors/schema_ext.py — schema extension protocol.

Tests the pipeline registry, @schema_extension decorator, run_pipeline,
stage positioning, and error handling.
"""

import pytest
from typing import ClassVar

from pydantic import Field

from n3tx.core import config
from n3tx.core.models.proto_model import ProtoModel
from n3tx.core.models.proto_schema import (
    register_stage,
    schema_extension,
    run_pipeline,
    get_pipeline,
    clear_pipeline,
    remove_stage,
    _stages,
)
import n3tx.core.models.proto_schema as proto_schema

pytestmark = pytest.mark.unit

# Default pipeline stage names for reference
DEFAULT_STAGES = ['base', 'strip_hidden', 'methods', 'agent', 'defs', 'access', 'widget', 'ui', 'metadata']


# ===================================================================
# Helpers
# ===================================================================

class _Ext(ProtoModel):
    __tablename__: ClassVar[str] = 'ext_simple'
    name: str = Field(default='')
    value: int = Field(default=0)


@pytest.fixture(autouse=True)
def _restore_pipeline():
    """Save pipeline before each test, restore after.

    Extensions registered during a test are removed on teardown.
    Default stages stay intact across the test suite.
    """
    saved = list(_stages)
    yield
    _stages.clear()
    _stages.extend(saved)


# ===================================================================
# get_pipeline / default registration
# ===================================================================

class TestDefaultPipeline:

    def test_default_stages_registered(self):
        assert get_pipeline() == DEFAULT_STAGES

    def test_default_stage_count(self):
        assert len(get_pipeline()) == 9

    def test_base_is_first(self):
        assert get_pipeline()[0] == 'base'

    def test_metadata_is_last(self):
        assert get_pipeline()[-1] == 'metadata'


# ===================================================================
# register_stage
# ===================================================================

class TestRegisterStage:

    def test_append_to_end(self):
        register_stage('custom', lambda cls, s: s)
        assert get_pipeline()[-1] == 'custom'

    def test_after_positioning(self):
        register_stage('after_methods', lambda cls, s: s, after='methods')
        pipeline = get_pipeline()
        assert pipeline.index('after_methods') == pipeline.index('methods') + 1

    def test_before_positioning(self):
        register_stage('before_access', lambda cls, s: s, before='access')
        pipeline = get_pipeline()
        assert pipeline.index('before_access') == pipeline.index('access') - 1
        # defs should still be before our new stage
        assert pipeline.index('defs') < pipeline.index('before_access')

    def test_after_last_stage(self):
        register_stage('post_metadata', lambda cls, s: s, after='metadata')
        assert get_pipeline()[-1] == 'post_metadata'

    def test_before_first_stage(self):
        register_stage('pre_base', lambda cls: {}, before='base')
        assert get_pipeline()[0] == 'pre_base'

    def test_duplicate_name_raises(self):
        register_stage('unique_ext', lambda cls, s: s)
        with pytest.raises(ValueError, match="already registered"):
            register_stage('unique_ext', lambda cls, s: s)

    def test_after_nonexistent_raises(self):
        with pytest.raises(ValueError, match="not found"):
            register_stage('bad', lambda cls, s: s, after='nonexistent')

    def test_before_nonexistent_raises(self):
        with pytest.raises(ValueError, match="not found"):
            register_stage('bad', lambda cls, s: s, before='nonexistent')

    def test_both_after_and_before_raises(self):
        with pytest.raises(ValueError, match="not both"):
            register_stage('bad', lambda cls, s: s, after='base', before='metadata')

    def test_multiple_after_same_stage(self):
        """Two extensions after 'methods' — inserted in registration order."""
        register_stage('ext_a', lambda cls, s: s, after='methods')
        register_stage('ext_b', lambda cls, s: s, after='ext_a')
        pipeline = get_pipeline()
        assert pipeline.index('ext_a') == pipeline.index('methods') + 1
        assert pipeline.index('ext_b') == pipeline.index('ext_a') + 1


# ===================================================================
# schema_extension decorator
# ===================================================================

class TestSchemaExtensionDecorator:

    def test_registers_by_function_name(self):
        @schema_extension(after='methods')
        def my_ext(cls, schema):
            return schema

        assert 'my_ext' in get_pipeline()

    def test_positioning_works(self):
        @schema_extension(after='defs')
        def after_defs_ext(cls, schema):
            return schema

        pipeline = get_pipeline()
        assert pipeline.index('after_defs_ext') == pipeline.index('defs') + 1

    def test_returns_original_function(self):
        @schema_extension(after='ui')
        def passthrough(cls, schema):
            return schema

        # The decorator returns the original function, not a wrapper
        assert callable(passthrough)
        assert passthrough.__name__ == 'passthrough'

    def test_extension_is_called_in_pipeline(self):
        """Extension actually runs and modifies the schema."""
        @schema_extension(after='methods')
        def inject_custom(cls, schema):
            schema['custom_key'] = 'custom_value'
            return schema

        _Ext.invalidate_schema_cache()
        result = run_pipeline(_Ext)
        assert result['custom_key'] == 'custom_value'

    def test_extension_receives_previous_output(self):
        """Extension receives the schema as transformed by prior stages."""
        @schema_extension(after='methods')
        def check_prior(cls, schema):
            # 'methods' stage has already run, so 'methods' key exists
            assert 'methods' in schema
            schema['prior_check'] = True
            return schema

        result = run_pipeline(_Ext)
        assert result['prior_check'] is True


# ===================================================================
# remove_stage
# ===================================================================

class TestRemoveStage:

    def test_removes_existing(self):
        register_stage('temporary', lambda cls, s: s)
        assert 'temporary' in get_pipeline()
        remove_stage('temporary')
        assert 'temporary' not in get_pipeline()

    def test_remove_nonexistent_raises(self):
        with pytest.raises(ValueError, match="not found"):
            remove_stage('nonexistent')

    def test_pipeline_still_works_after_removal(self):
        """Removing a non-essential extension doesn't break the pipeline."""
        register_stage('removable', lambda cls, s: s, after='methods')
        remove_stage('removable')
        _Ext.invalidate_schema_cache()
        result = run_pipeline(_Ext)
        assert 'properties' in result
        assert '$schema' in result


# ===================================================================
# clear_pipeline
# ===================================================================

class TestClearPipeline:

    def test_clears_all(self):
        clear_pipeline()
        assert get_pipeline() == []

    def test_run_pipeline_fails_after_clear(self):
        clear_pipeline()
        with pytest.raises(RuntimeError, match="No schema pipeline stages"):
            run_pipeline(_Ext)


# ===================================================================
# run_pipeline
# ===================================================================

class TestRunPipeline:

    def test_produces_valid_schema(self):
        _Ext.invalidate_schema_cache()
        result = run_pipeline(_Ext)
        assert '$schema' in result
        assert '$id' in result
        assert 'properties' in result
        assert 'methods' in result
        assert 'access' in result

    def test_matches_proto_model_schema(self):
        """run_pipeline output matches ProtoModel.schema() output."""
        _Ext.invalidate_schema_cache()
        pipeline_result = run_pipeline(_Ext)
        _Ext.invalidate_schema_cache()
        schema_result = _Ext.schema()
        assert pipeline_result == schema_result

    def test_extension_integrated_into_schema(self):
        """ProtoModel.schema() picks up extensions via run_pipeline."""
        @schema_extension(after='ui')
        def tag_ext(cls, schema):
            schema['_tagged'] = True
            return schema

        _Ext.invalidate_schema_cache()
        result = _Ext.schema()
        assert result['_tagged'] is True

    def test_extension_order_matters(self):
        """Earlier extensions run before later ones."""
        execution_order = []

        @schema_extension(after='methods')
        def first_ext(cls, schema):
            execution_order.append('first')
            return schema

        @schema_extension(after='first_ext')
        def second_ext(cls, schema):
            execution_order.append('second')
            return schema

        run_pipeline(_Ext)
        assert execution_order == ['first', 'second']

    def test_extension_can_read_and_modify(self):
        """Extension reads a value set by a prior stage and modifies it."""
        @schema_extension(after='metadata')
        def augment_id(cls, schema):
            # metadata set $id — we can modify it
            schema['$id'] = schema['$id'] + '/v2'
            return schema

        result = run_pipeline(_Ext)
        assert result['$id'].endswith('/v2')


# ===================================================================
# Real-world extension patterns (from roadmap)
# ===================================================================

class TestExtensionPatterns:

    def test_federation_pattern(self):
        """Simulates how federation would register a schema extension."""
        @schema_extension(after='methods')
        def federation(cls, schema):
            if getattr(cls, '__federated__', False):
                schema['federation'] = {
                    'actor_url': f"{config.API_URL}/{cls.__name__}",
                    'inbox': f"{config.API_URL}/{cls.__tablename__}/inbox",
                    'outbox': f"{config.API_URL}/{cls.__tablename__}/outbox",
                }
            return schema

        # Non-federated model: no federation key
        result = run_pipeline(_Ext)
        assert 'federation' not in result

        # Federated model: federation key present
        class _Federated(ProtoModel):
            __tablename__: ClassVar[str] = 'ext_federated'
            __federated__: ClassVar[bool] = True
            name: str = Field(default='')

        result = run_pipeline(_Federated)
        assert 'federation' in result
        assert result['federation']['inbox'] == f"{config.API_URL}/ext_federated/inbox"

    def test_agent_tools_pattern(self):
        """Simulates how agent/MCP would register a schema extension."""
        @schema_extension(after='methods')
        def agent_tools(cls, schema):
            if getattr(cls, '__agent__', False):
                tools = []
                for name, method in schema.get('methods', {}).items():
                    tools.append({
                        'name': f"{schema.get('__tablename__', '')}_{name}",
                        'inputSchema': {'type': 'object', 'properties': method.get('parameters', {})},
                    })
                schema['tools'] = tools
            return schema

        result = run_pipeline(_Ext)
        assert 'tools' not in result

    def test_discriminator_pattern(self):
        """Simulates how polymorphic types would register a schema extension."""
        @schema_extension(after='defs')
        def discriminator(cls, schema):
            disc_field = getattr(cls, '__discriminator__', None)
            if disc_field:
                schema['discriminator'] = {'propertyName': disc_field}
            return schema

        class _Poly(ProtoModel):
            __tablename__: ClassVar[str] = 'ext_poly'
            __discriminator__: ClassVar[str] = '_type'
            name: str = Field(default='')

        result = run_pipeline(_Poly)
        assert result['discriminator'] == {'propertyName': '_type'}

    def test_multiple_extensions_compose(self):
        """Multiple extensions from different 'packages' all apply."""
        @schema_extension(after='methods')
        def ext_alpha(cls, schema):
            schema['alpha'] = True
            return schema

        @schema_extension(after='ext_alpha')
        def ext_beta(cls, schema):
            schema['beta'] = True
            return schema

        @schema_extension(before='metadata')
        def ext_gamma(cls, schema):
            schema['gamma'] = True
            return schema

        result = run_pipeline(_Ext)
        assert result['alpha'] is True
        assert result['beta'] is True
        assert result['gamma'] is True


# ===================================================================
# Edge cases
# ===================================================================

class TestEdgeCases:

    def test_extension_that_returns_new_dict(self):
        """Extension can return a completely new dict (not mutate in place)."""
        @schema_extension(after='metadata')
        def replace_all(cls, schema):
            return {**schema, 'replaced': True}

        result = run_pipeline(_Ext)
        assert result['replaced'] is True
        assert '$schema' in result  # Original keys preserved via spread

    def test_extension_with_no_modification(self):
        """Extension that returns schema unchanged is a no-op."""
        @schema_extension(after='ui')
        def noop_ext(cls, schema):
            return schema

        _Ext.invalidate_schema_cache()
        with_ext = run_pipeline(_Ext)
        remove_stage('noop_ext')
        _Ext.invalidate_schema_cache()
        without_ext = run_pipeline(_Ext)
        assert with_ext == without_ext

    def test_cache_invalidation_picks_up_extensions(self):
        """After registering an extension, invalidating cache and calling
        schema() should include the extension's output."""
        _Ext.invalidate_schema_cache()
        before = _Ext.schema()
        assert 'dynamic_ext' not in before

        @schema_extension(after='ui')
        def dynamic_ext(cls, schema):
            schema['dynamic_ext'] = True
            return schema

        _Ext.invalidate_schema_cache()
        after = _Ext.schema()
        assert after['dynamic_ext'] is True
