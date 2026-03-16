"""
Test plan for utils/decorators.py — debug envelope feature of @expose_route
============================================================================

UNIT TESTS — behavior validation
  - test_debug_false_returns_raw_string_result
  - test_debug_false_returns_raw_dict_result
  - test_debug_false_returns_raw_none_result
  - test_debug_false_returns_raw_int_result
  - test_debug_true_returns_envelope_with_data_and_debug_keys
  - test_debug_true_data_field_contains_original_value
  - test_debug_true_debug_field_contains_method_name
  - test_debug_true_debug_field_contains_model_name_from_instance
  - test_debug_true_debug_field_contains_instance_id_from_self
  - test_debug_true_debug_field_duration_ms_is_float
  - test_debug_true_debug_field_duration_ms_is_nonnegative

EDGE CASES — instance vs classmethod dispatch
  - test_debug_true_classmethod_instance_id_is_none
  - test_debug_true_classmethod_model_name_is_class_name
  - test_debug_true_no_args_instance_id_is_none
  - test_debug_true_no_args_model_name_is_none

JSON STRING PARSING
  - test_debug_true_json_string_is_parsed_to_dict
  - test_debug_true_json_array_string_is_parsed_to_list
  - test_debug_true_non_json_string_is_preserved_as_string
  - test_debug_true_empty_string_is_preserved

DICT AND NONE RESULTS
  - test_debug_true_dict_result_preserved_in_envelope
  - test_debug_true_none_result_wrapped_in_envelope

EXCEPTION HANDLING
  - test_debug_false_exception_propagates_unchanged
  - test_debug_true_exception_propagates_unchanged
  - test_debug_true_custom_exception_propagates

METADATA PRESERVATION
  - test_endpoint_metadata_route_preserved
  - test_endpoint_metadata_methods_preserved
  - test_endpoint_metadata_access_preserved
  - test_endpoint_metadata_stream_preserved
  - test_functools_wraps_name_preserved
  - test_functools_wraps_doc_preserved
  - test_inspect_signature_matches_original

STATE TRANSITIONS — DEBUG flag toggled mid-run
  - test_toggling_debug_changes_return_shape
"""

import inspect
import json
import pytest

from n3tx_core import config
from n3tx_core.utils.decorators import expose_route

pytestmark = pytest.mark.unit


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def debug_on():
    """Enable DEBUG mode for the duration of a single test."""
    config.DEBUG = True
    yield
    config.DEBUG = False


class FakeInstance:
    """Minimal instance with an 'id' attribute for testing instance dispatch."""

    def __init__(self, id_=42):
        self.id = id_
        self.__class__.__name__ = 'FakeModel'


class FakeClass:
    """Minimal class used as the first arg in classmethod-style calls."""
    pass


# ===================================================================
# DEBUG=False — raw result returned unchanged
# ===================================================================

class TestDebugFalseRawResult:
    """When config.DEBUG is False, @expose_route returns the function's result unchanged."""

    def test_debug_false_returns_raw_string_result(self):
        @expose_route('/action')
        def handler(self):
            return 'hello'

        result = handler(FakeInstance())
        assert result == 'hello'

    def test_debug_false_returns_raw_dict_result(self):
        @expose_route('/action')
        def handler(self):
            return {'key': 'value'}

        result = handler(FakeInstance())
        assert result == {'key': 'value'}

    def test_debug_false_returns_raw_none_result(self):
        @expose_route('/action')
        def handler(self):
            return None

        result = handler(FakeInstance())
        assert result is None

    def test_debug_false_returns_raw_int_result(self):
        @expose_route('/action')
        def handler(self):
            return 99

        result = handler(FakeInstance())
        assert result == 99

    def test_debug_false_no_envelope_keys(self):
        @expose_route('/action')
        def handler(self):
            return {'action': 'done'}

        result = handler(FakeInstance())
        assert '_debug' not in result


# ===================================================================
# DEBUG=True — envelope shape
# ===================================================================

class TestDebugTrueEnvelopeShape:
    """When config.DEBUG is True, @expose_route wraps the result in a debug envelope."""

    def test_debug_true_returns_envelope_with_result_and_debug_keys(self, debug_on):
        @expose_route('/action')
        def handler(self):
            return 'ok'

        result = handler(FakeInstance())
        assert 'data' in result
        assert '_debug' in result

    def test_debug_true_result_field_contains_original_value(self, debug_on):
        @expose_route('/action')
        def handler(self):
            return {'status': 'done'}

        result = handler(FakeInstance())
        assert result['data'] == {'status': 'done'}

    def test_debug_true_envelope_has_no_extra_top_level_keys(self, debug_on):
        @expose_route('/action')
        def handler(self):
            return 'x'

        result = handler(FakeInstance())
        assert set(result.keys()) == {'data', '_debug'}

    def test_debug_true_debug_section_has_required_keys(self, debug_on):
        @expose_route('/action')
        def handler(self):
            return 'x'

        result = handler(FakeInstance())
        debug = result['_debug']
        assert 'method' in debug
        assert 'model' in debug
        assert 'instance_id' in debug
        assert 'duration_ms' in debug


# ===================================================================
# DEBUG=True — _debug field contents
# ===================================================================

class TestDebugFieldContents:
    """Verify each field inside the _debug dict is correct."""

    def test_debug_method_name_matches_function_name(self, debug_on):
        @expose_route('/do_thing')
        def do_thing(self):
            return 'result'

        result = do_thing(FakeInstance())
        assert result['_debug']['method'] == 'do_thing'

    def test_debug_model_name_from_instance_class(self, debug_on):
        class MyModel:
            id = 7

        @expose_route('/go')
        def go(self):
            return 'y'

        result = go(MyModel())
        assert result['_debug']['model'] == 'MyModel'

    def test_debug_instance_id_extracted_from_self_id(self, debug_on):
        instance = FakeInstance(id_=123)

        @expose_route('/ping')
        def ping(self):
            return 'pong'

        result = ping(instance)
        assert result['_debug']['instance_id'] == 123

    def test_debug_duration_ms_is_float(self, debug_on):
        @expose_route('/work')
        def work(self):
            return 'done'

        result = work(FakeInstance())
        assert isinstance(result['_debug']['duration_ms'], float)

    def test_debug_duration_ms_is_nonnegative(self, debug_on):
        @expose_route('/work')
        def work(self):
            return 'done'

        result = work(FakeInstance())
        assert result['_debug']['duration_ms'] >= 0.0

    def test_debug_duration_ms_under_reasonable_bound(self, debug_on):
        """A trivial function should complete in well under 1000 ms."""
        @expose_route('/fast')
        def fast(self):
            return 'immediate'

        result = fast(FakeInstance())
        assert result['_debug']['duration_ms'] < 1000.0


# ===================================================================
# Instance vs classmethod dispatch
# ===================================================================

class TestInstanceVsClassDispatch:
    """instance_id and model differ depending on whether self is an instance or a class."""

    def test_classmethod_instance_id_is_none(self, debug_on):
        """When first arg is a class (not an instance with .id), instance_id is None."""
        @expose_route('/register')
        def register(cls):
            return {'registered': True}

        result = register(FakeClass)
        assert result['_debug']['instance_id'] is None

    def test_classmethod_model_name_is_class_name(self, debug_on):
        """When first arg is a class, model name is the class's __name__."""
        @expose_route('/register')
        def register(cls):
            return {'registered': True}

        result = register(FakeClass)
        assert result['_debug']['model'] == 'FakeClass'

    def test_instance_without_id_has_none_instance_id(self, debug_on):
        """If the instance has no 'id' attribute, instance_id is None."""
        class NoId:
            pass

        @expose_route('/act')
        def act(self):
            return 'ok'

        result = act(NoId())
        assert result['_debug']['instance_id'] is None

    def test_no_args_model_is_none_and_instance_id_is_none(self, debug_on):
        """When called with no positional args, both model and instance_id are None."""
        @expose_route('/standalone')
        def standalone():
            return 'bare'

        result = standalone()
        assert result['_debug']['model'] is None
        assert result['_debug']['instance_id'] is None


# ===================================================================
# JSON string parsing
# ===================================================================

class TestJsonStringParsing:
    """String results that are valid JSON are parsed into Python objects inside the envelope."""

    def test_json_object_string_is_parsed_to_dict(self, debug_on):
        @expose_route('/action')
        def action(self):
            return '{"action": "favorited"}'

        result = action(FakeInstance())
        assert result['data'] == {'action': 'favorited'}
        assert isinstance(result['data'], dict)

    def test_json_array_string_is_parsed_to_list(self, debug_on):
        @expose_route('/items')
        def items(self):
            return '[1, 2, 3]'

        result = items(FakeInstance())
        assert result['data'] == [1, 2, 3]

    def test_non_json_string_is_preserved_as_string(self, debug_on):
        @expose_route('/msg')
        def msg(self):
            return 'plain text, not JSON'

        result = msg(FakeInstance())
        assert result['data'] == 'plain text, not JSON'
        assert isinstance(result['data'], str)

    def test_empty_string_is_preserved_as_string(self, debug_on):
        @expose_route('/empty')
        def empty(self):
            return ''

        result = empty(FakeInstance())
        assert result['data'] == ''

    def test_json_number_string_is_parsed_to_int(self, debug_on):
        """A JSON string that is just a number should be parsed to an int."""
        @expose_route('/num')
        def num(self):
            return '42'

        result = num(FakeInstance())
        assert result['data'] == 42

    def test_non_json_does_not_raise(self, debug_on):
        """Invalid JSON strings should not raise — they fall through to string."""
        @expose_route('/bad')
        def bad(self):
            return '{not valid json}'

        result = bad(FakeInstance())
        assert result['data'] == '{not valid json}'

    def test_json_string_not_parsed_when_debug_false(self):
        """When DEBUG=False, JSON strings pass through unmodified."""
        @expose_route('/action')
        def action(self):
            return '{"action": "favorited"}'

        result = action(FakeInstance())
        assert result == '{"action": "favorited"}'
        assert isinstance(result, str)


# ===================================================================
# Dict and None results
# ===================================================================

class TestDictAndNoneResults:
    """Dict results go into result as-is; None is wrapped too."""

    def test_dict_result_preserved_in_envelope(self, debug_on):
        @expose_route('/info')
        def info(self):
            return {'token': 'abc', 'user': {'id': 1}}

        result = info(FakeInstance())
        assert result['data'] == {'token': 'abc', 'user': {'id': 1}}

    def test_none_result_wrapped_in_envelope(self, debug_on):
        @expose_route('/noop')
        def noop(self):
            return None

        result = noop(FakeInstance())
        assert 'data' in result
        assert result['data'] is None

    def test_list_result_preserved_in_envelope(self, debug_on):
        @expose_route('/list')
        def lst(self):
            return [1, 2, 3]

        result = lst(FakeInstance())
        assert result['data'] == [1, 2, 3]


# ===================================================================
# Exception handling
# ===================================================================

class TestExceptionPropagation:
    """Exceptions raised by the wrapped function must propagate unmodified regardless of DEBUG."""

    def test_debug_false_value_error_propagates(self):
        @expose_route('/fail')
        def fail(self):
            raise ValueError("something went wrong")

        with pytest.raises(ValueError, match="something went wrong"):
            fail(FakeInstance())

    def test_debug_true_value_error_propagates(self, debug_on):
        @expose_route('/fail')
        def fail(self):
            raise ValueError("debug mode error")

        with pytest.raises(ValueError, match="debug mode error"):
            fail(FakeInstance())

    def test_debug_false_runtime_error_propagates(self):
        @expose_route('/crash')
        def crash(self):
            raise RuntimeError("crash!")

        with pytest.raises(RuntimeError, match="crash!"):
            crash(FakeInstance())

    def test_debug_true_runtime_error_propagates(self, debug_on):
        @expose_route('/crash')
        def crash(self):
            raise RuntimeError("debug crash!")

        with pytest.raises(RuntimeError, match="debug crash!"):
            crash(FakeInstance())

    def test_debug_true_custom_exception_propagates(self, debug_on):
        class AppError(Exception):
            pass

        @expose_route('/boom')
        def boom(self):
            raise AppError("custom error")

        with pytest.raises(AppError, match="custom error"):
            boom(FakeInstance())

    def test_exception_not_wrapped_in_envelope(self, debug_on):
        """Exceptions must not be caught and wrapped; they propagate directly."""
        @expose_route('/err')
        def err(self):
            raise KeyError("missing")

        raised = None
        try:
            err(FakeInstance())
        except KeyError as exc:
            raised = exc

        assert raised is not None
        # The exception is a raw KeyError, not an envelope dict
        assert not isinstance(raised, dict)


# ===================================================================
# Metadata preservation
# ===================================================================

class TestMetadataPreservation:
    """@expose_route must preserve __endpoint__, __name__, __doc__, and signature."""

    def test_endpoint_metadata_route_preserved(self):
        @expose_route('/my_action', methods=['POST'])
        def my_action(self):
            pass

        assert my_action.__endpoint__['route'] == '/my_action'

    def test_endpoint_metadata_methods_preserved(self):
        @expose_route('/act', methods=['GET', 'POST'])
        def act(self):
            pass

        assert my_action.__endpoint__['methods'] == ['GET', 'POST'] if False else \
               act.__endpoint__['methods'] == ['GET', 'POST']

    def test_endpoint_metadata_access_preserved(self):
        from n3tx_core.authorize.rules import AUTHENTICATED
        @expose_route('/secure', access=AUTHENTICATED)
        def secure(self):
            pass

        assert secure.__endpoint__['access'] is AUTHENTICATED

    def test_endpoint_metadata_stream_flag_preserved(self):
        @expose_route('/stream', stream=True)
        def streamer(self):
            pass

        assert streamer.__endpoint__['stream'] is True

    def test_endpoint_metadata_stream_default_false(self):
        @expose_route('/normal')
        def normal(self):
            pass

        assert normal.__endpoint__['stream'] is False

    def test_functools_wraps_preserves_name(self):
        @expose_route('/named')
        def my_named_function(self):
            pass

        assert my_named_function.__name__ == 'my_named_function'

    def test_functools_wraps_preserves_docstring(self):
        @expose_route('/documented')
        def documented(self):
            """This is my docstring."""
            pass

        assert documented.__doc__ == 'This is my docstring.'

    def test_functools_wraps_preserves_none_docstring(self):
        @expose_route('/undocumented')
        def undocumented(self):
            pass

        assert undocumented.__doc__ is None

    def test_inspect_signature_matches_original_single_param(self):
        @expose_route('/one_param')
        def one_param(self):
            return 'ok'

        sig = inspect.signature(one_param)
        params = list(sig.parameters.keys())
        assert params == ['self']

    def test_inspect_signature_matches_original_multiple_params(self):
        @expose_route('/multi')
        def multi(self, name: str, value: int = 0):
            return name

        sig = inspect.signature(multi)
        params = list(sig.parameters.keys())
        assert params == ['self', 'name', 'value']

    def test_endpoint_dict_has_exactly_four_keys(self):
        @expose_route('/check')
        def check(self):
            pass

        assert set(check.__endpoint__.keys()) == {'route', 'methods', 'access', 'stream'}


# ===================================================================
# State transitions — DEBUG flag toggled mid-run
# ===================================================================

class TestDebugFlagToggle:
    """The wrapper reads config.DEBUG at call time, not at decoration time."""

    def test_toggling_debug_on_changes_return_shape(self):
        @expose_route('/toggle')
        def toggle(self):
            return 'raw'

        instance = FakeInstance()

        config.DEBUG = False
        result_off = toggle(instance)

        config.DEBUG = True
        result_on = toggle(instance)

        config.DEBUG = False  # clean up (autouse fixture also restores)

        assert result_off == 'raw'
        assert isinstance(result_on, dict)
        assert 'data' in result_on
        assert '_debug' in result_on

    def test_debug_flag_read_at_call_time_not_decoration_time(self):
        """Decorating with DEBUG=False then calling with DEBUG=True must use DEBUG=True."""
        config.DEBUG = False

        @expose_route('/runtime')
        def runtime(self):
            return 'val'

        config.DEBUG = True
        result = runtime(FakeInstance())

        config.DEBUG = False

        assert isinstance(result, dict)
        assert result['data'] == 'val'
