"""Tests for utils/populate.py — PopulateSpec and parse_populate."""

import pytest
from pybend.core.utils.populate import PopulateSpec, parse_populate, DEFAULT_CHILD_LIMIT

pytestmark = pytest.mark.unit



class TestPopulateSpec:

    def test_default_values(self):
        spec = PopulateSpec()
        assert spec.depth == 0
        assert spec.fields == {}
        assert spec.limit == DEFAULT_CHILD_LIMIT

    def test_is_empty_default(self):
        spec = PopulateSpec()
        assert spec.is_empty is True

    def test_not_empty_with_depth(self):
        spec = PopulateSpec(depth=1)
        assert spec.is_empty is False

    def test_not_empty_with_fields(self):
        spec = PopulateSpec(fields={'comments': PopulateSpec()})
        assert spec.is_empty is False

    def test_should_populate_depth(self):
        spec = PopulateSpec(depth=1)
        assert spec.should_populate('comments') is True
        assert spec.should_populate('anything') is True

    def test_should_populate_explicit_field(self):
        spec = PopulateSpec(fields={'comments': PopulateSpec()})
        assert spec.should_populate('comments') is True
        assert spec.should_populate('other') is False

    def test_should_not_populate_empty(self):
        spec = PopulateSpec()
        assert spec.should_populate('comments') is False

    def test_child_spec_explicit(self):
        child = PopulateSpec(depth=2)
        spec = PopulateSpec(fields={'comments': child})
        result = spec.child_spec('comments')
        assert result.depth == 2

    def test_child_spec_depth_decrement(self):
        spec = PopulateSpec(depth=2)
        result = spec.child_spec('comments')
        assert result.depth == 1

    def test_child_spec_depth_zero_stays_zero(self):
        spec = PopulateSpec(depth=1)
        child = spec.child_spec('comments')
        grandchild = child.child_spec('likes')
        assert grandchild.depth == 0

    def test_child_spec_no_match(self):
        spec = PopulateSpec()
        result = spec.child_spec('nonexistent')
        assert result.is_empty is True

    def test_child_spec_merges_depth_and_explicit(self):
        spec = PopulateSpec(
            depth=3,
            fields={'comments': PopulateSpec(fields={'likes': PopulateSpec()})}
        )
        child = spec.child_spec('comments')
        assert child.depth >= 2
        assert 'likes' in child.fields

    def test_custom_limit(self):
        spec = PopulateSpec(limit=5)
        assert spec.limit == 5

    def test_child_spec_inherits_limit(self):
        spec = PopulateSpec(depth=2, limit=10)
        child = spec.child_spec('comments')
        assert child.limit == 10


class TestParsePopulate:

    def test_none_both(self):
        spec = parse_populate(None, None)
        assert spec.is_empty is True

    def test_depth_only(self):
        spec = parse_populate(None, 2)
        assert spec.depth == 2
        assert spec.fields == {}

    def test_single_field(self):
        spec = parse_populate('comments', None)
        assert 'comments' in spec.fields

    def test_multiple_fields(self):
        spec = parse_populate('comments,tags', None)
        assert 'comments' in spec.fields
        assert 'tags' in spec.fields

    def test_nested_field(self):
        spec = parse_populate('comments.likes', None)
        assert 'comments' in spec.fields
        assert 'likes' in spec.fields['comments'].fields

    def test_depth_and_fields(self):
        spec = parse_populate('comments', 2)
        assert spec.depth == 2
        assert 'comments' in spec.fields

    def test_empty_string(self):
        spec = parse_populate('', None)
        assert spec.fields == {}

    def test_whitespace_handling(self):
        spec = parse_populate(' comments , tags ', None)
        assert 'comments' in spec.fields
        assert 'tags' in spec.fields

    def test_deep_nesting(self):
        spec = parse_populate('a.b.c', None)
        assert 'a' in spec.fields
        assert 'b' in spec.fields['a'].fields
        assert 'c' in spec.fields['a'].fields['b'].fields

    def test_depth_zero(self):
        spec = parse_populate(None, 0)
        assert spec.depth == 0
        assert spec.is_empty is True

    def test_mixed(self):
        spec = parse_populate('comments.likes,tags', 1)
        assert spec.depth == 1
        assert 'comments' in spec.fields
        assert 'tags' in spec.fields
        assert 'likes' in spec.fields['comments'].fields
