"""Tests for utils/erroring.py — get_traceback_info."""

import pytest
from n3tx.core.utils.erroring import get_traceback_info

pytestmark = pytest.mark.unit



class TestGetTracebackInfo:

    def test_returns_list(self):
        try:
            raise ValueError("test error")
        except Exception as e:
            result = get_traceback_info(e)
            assert isinstance(result, list)

    def test_contains_error(self):
        try:
            raise ValueError("test error")
        except Exception as e:
            result = get_traceback_info(e)
            last = result[-1]
            assert 'error' in last
            assert 'test error' in last['error']

    def test_frame_keys(self):
        try:
            raise ValueError("test error")
        except Exception as e:
            result = get_traceback_info(e)
            for frame in result:
                assert 'file' in frame
                assert 'line' in frame
                assert 'function' in frame
                assert 'code' in frame

    def test_max_three_frames(self):
        def inner():
            raise RuntimeError("deep error")
        def middle():
            inner()
        def outer():
            middle()
        try:
            outer()
        except Exception as e:
            result = get_traceback_info(e)
            assert len(result) <= 3
