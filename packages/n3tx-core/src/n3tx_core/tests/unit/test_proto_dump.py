"""
Tests for models/proto_dump.py -- composable dump pipeline stages.

Tests the pipeline infrastructure: registry, ordering, extension decorator,
and utility functions.  Mirrors how test_schema_ext.py tests proto_schema.py.
"""

import pytest

import n3tx_core.models.proto_dump as proto_dump
from n3tx_core.models.proto_dump import (
    register_stage,
    dump_extension,
    run_pipeline,
    get_pipeline,
    clear_pipeline,
    remove_stage,
    _find_stage,
    _stages,
)

pytestmark = pytest.mark.unit

# Default pipeline stage names registered at import time
DEFAULT_STAGES = ['base', 'relationships', 'schema_url', 'instance_url', 'populate']


@pytest.fixture(autouse=True)
def _restore_pipeline():
    """Save and restore pipeline state around each test."""
    saved = list(_stages)
    yield
    _stages.clear()
    _stages.extend(saved)


# ===================================================================
# _find_stage
# ===================================================================

class TestFindStage:

    def test_finds_existing_stage(self):
        idx = _find_stage('base')
        assert idx == 0

    def test_finds_second_stage(self):
        idx = _find_stage('relationships')
        assert idx == 1

    def test_finds_third_stage(self):
        idx = _find_stage('schema_url')
        assert idx == 2

    def test_finds_fourth_stage(self):
        idx = _find_stage('instance_url')
        assert idx == 3

    def test_unknown_name_raises(self):
        with pytest.raises(ValueError, match="not found"):
            _find_stage('nonexistent')

    def test_error_message_lists_stages(self):
        with pytest.raises(ValueError, match="base"):
            _find_stage('nope')


# ===================================================================
# register_stage
# ===================================================================

class TestRegisterStage:

    def test_append_to_end(self):
        register_stage('custom', lambda inst, d: d)
        assert get_pipeline()[-1] == 'custom'

    def test_append_preserves_existing_order(self):
        register_stage('custom', lambda inst, d: d)
        pipeline = get_pipeline()
        assert pipeline[:len(DEFAULT_STAGES)] == DEFAULT_STAGES

    def test_after_positioning(self):
        register_stage('after_base', lambda inst, d: d, after='base')
        pipeline = get_pipeline()
        assert pipeline.index('after_base') == pipeline.index('base') + 1

    def test_before_positioning(self):
        register_stage('before_instance_url', lambda inst, d: d, before='instance_url')
        pipeline = get_pipeline()
        assert pipeline.index('before_instance_url') == pipeline.index('instance_url') - 1
        assert pipeline.index('base') < pipeline.index('before_instance_url')

    def test_after_last_stage(self):
        register_stage('post_populate', lambda inst, d: d, after='populate')
        assert get_pipeline()[-1] == 'post_populate'

    def test_before_first_stage(self):
        register_stage('pre_base', lambda inst: {}, before='base')
        assert get_pipeline()[0] == 'pre_base'

    def test_duplicate_name_raises(self):
        register_stage('unique_ext', lambda inst, d: d)
        with pytest.raises(ValueError, match="already registered"):
            register_stage('unique_ext', lambda inst, d: d)

    def test_both_after_and_before_raises(self):
        with pytest.raises(ValueError, match="not both"):
            register_stage('bad', lambda inst, d: d, after='base', before='instance_url')

    def test_after_unknown_anchor_raises(self):
        with pytest.raises(ValueError, match="not found"):
            register_stage('bad', lambda inst, d: d, after='nonexistent')

    def test_before_unknown_anchor_raises(self):
        with pytest.raises(ValueError, match="not found"):
            register_stage('bad', lambda inst, d: d, before='nonexistent')

    def test_multiple_after_same_stage(self):
        register_stage('ext_a', lambda inst, d: d, after='base')
        register_stage('ext_b', lambda inst, d: d, after='ext_a')
        pipeline = get_pipeline()
        assert pipeline.index('ext_a') == pipeline.index('base') + 1
        assert pipeline.index('ext_b') == pipeline.index('ext_a') + 1


# ===================================================================
# dump_extension decorator
# ===================================================================

class TestDumpExtension:

    def test_registers_by_function_name(self):
        @dump_extension(after='base')
        def my_dump_ext(instance, d):
            return d

        assert 'my_dump_ext' in get_pipeline()

    def test_after_positioning(self):
        @dump_extension(after='base')
        def post_base(instance, d):
            return d

        pipeline = get_pipeline()
        assert pipeline.index('post_base') == pipeline.index('base') + 1

    def test_before_positioning(self):
        @dump_extension(before='instance_url')
        def pre_instance_url(instance, d):
            return d

        pipeline = get_pipeline()
        assert pipeline.index('pre_instance_url') == pipeline.index('instance_url') - 1

    def test_returns_original_function(self):
        @dump_extension(after='instance_url')
        def passthrough(instance, d):
            return d

        assert callable(passthrough)
        assert passthrough.__name__ == 'passthrough'

    def test_function_is_unchanged(self):
        sentinel = object()

        @dump_extension(after='instance_url')
        def check_identity(instance, d):
            return sentinel

        assert check_identity(None, {}) is sentinel

    def test_no_positioning_appends(self):
        @dump_extension()
        def appended_ext(instance, d):
            return d

        assert get_pipeline()[-1] == 'appended_ext'


# ===================================================================
# run_pipeline
# ===================================================================

class TestRunPipeline:

    def test_empty_pipeline_raises(self):
        clear_pipeline()
        with pytest.raises(RuntimeError, match="No dump pipeline stages"):
            run_pipeline(object())

    def test_first_stage_seeds_data(self):
        clear_pipeline()
        register_stage('seed', lambda inst: {'seeded': True})
        result = run_pipeline(object())
        assert result == {'seeded': True}

    def test_subsequent_stages_transform(self):
        clear_pipeline()
        register_stage('seed', lambda inst: {'count': 0})
        register_stage('inc1', lambda inst, d: {**d, 'count': d['count'] + 1})
        register_stage('inc2', lambda inst, d: {**d, 'count': d['count'] + 1})
        result = run_pipeline(object())
        assert result['count'] == 2

    def test_runs_all_stages_in_order(self):
        execution_order = []
        clear_pipeline()

        def stage_a(inst):
            execution_order.append('a')
            return {}

        def stage_b(inst, d):
            execution_order.append('b')
            return d

        def stage_c(inst, d):
            execution_order.append('c')
            return d

        register_stage('a', stage_a)
        register_stage('b', stage_b)
        register_stage('c', stage_c)
        run_pipeline(object())
        assert execution_order == ['a', 'b', 'c']

    def test_instance_is_passed_to_all_stages(self):
        clear_pipeline()
        sentinel = object()

        received = []

        def seed(inst):
            received.append(inst)
            return {}

        def transform(inst, d):
            received.append(inst)
            return d

        register_stage('seed', seed)
        register_stage('transform', transform)
        run_pipeline(sentinel)
        assert all(r is sentinel for r in received)
        assert len(received) == 2

    def test_kwargs_forwarded_to_first_stage(self):
        clear_pipeline()
        captured = {}

        def seed(inst, **kwargs):
            captured.update(kwargs)
            return {}

        register_stage('seed', seed)
        run_pipeline(object(), mode='full', exclude_unset=True)
        assert captured == {'mode': 'full', 'exclude_unset': True}

    def test_single_stage_pipeline(self):
        clear_pipeline()
        register_stage('only', lambda inst: {'solo': True})
        result = run_pipeline(object())
        assert result == {'solo': True}

    def test_stage_can_return_new_dict(self):
        clear_pipeline()
        register_stage('seed', lambda inst: {'original': True})
        register_stage('replace', lambda inst, d: {'replaced': True})
        result = run_pipeline(object())
        assert result == {'replaced': True}
        assert 'original' not in result


# ===================================================================
# get_pipeline
# ===================================================================

class TestGetPipeline:

    def test_returns_stage_names_in_order(self):
        assert get_pipeline() == DEFAULT_STAGES

    def test_returns_list(self):
        result = get_pipeline()
        assert isinstance(result, list)

    def test_reflects_additions(self):
        register_stage('extra', lambda inst, d: d)
        assert get_pipeline() == DEFAULT_STAGES + ['extra']

    def test_reflects_insertions(self):
        register_stage('mid', lambda inst, d: d, after='base')
        assert get_pipeline() == ['base', 'mid', 'relationships', 'schema_url', 'instance_url', 'populate']

    def test_empty_after_clear(self):
        clear_pipeline()
        assert get_pipeline() == []


# ===================================================================
# clear_pipeline
# ===================================================================

class TestClearPipeline:

    def test_clears_all_stages(self):
        clear_pipeline()
        assert get_pipeline() == []
        assert len(_stages) == 0

    def test_run_pipeline_fails_after_clear(self):
        clear_pipeline()
        with pytest.raises(RuntimeError, match="No dump pipeline stages"):
            run_pipeline(object())

    def test_can_register_after_clear(self):
        clear_pipeline()
        register_stage('fresh', lambda inst: {'fresh': True})
        assert get_pipeline() == ['fresh']
        result = run_pipeline(object())
        assert result == {'fresh': True}


# ===================================================================
# remove_stage
# ===================================================================

class TestRemoveStage:

    def test_removes_by_name(self):
        register_stage('temp', lambda inst, d: d)
        assert 'temp' in get_pipeline()
        remove_stage('temp')
        assert 'temp' not in get_pipeline()

    def test_unknown_name_raises(self):
        with pytest.raises(ValueError, match="not found"):
            remove_stage('nonexistent')

    def test_pipeline_intact_after_removal(self):
        register_stage('removable', lambda inst, d: d, after='base')
        remove_stage('removable')
        assert get_pipeline() == DEFAULT_STAGES

    def test_pipeline_still_functional_after_removal(self):
        clear_pipeline()
        register_stage('seed', lambda inst: {'value': 1})
        register_stage('double', lambda inst, d: {**d, 'value': d['value'] * 2})
        register_stage('noop', lambda inst, d: d)
        remove_stage('noop')
        result = run_pipeline(object())
        assert result == {'value': 2}

    def test_remove_default_stage(self):
        remove_stage('instance_url')
        assert get_pipeline() == ['base', 'relationships', 'schema_url', 'populate']
