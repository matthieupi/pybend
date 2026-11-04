"""Bind annotated temporal predicates using native stored representations."""

from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import AwareDatetime, BaseModel, NaiveDatetime

from n3tx_core.utils.where import compile_where

pytestmark = pytest.mark.unit


class TemporalRow(BaseModel):
    """Declare Pydantic temporal annotations used by real application models."""

    aware: AwareDatetime
    optional: AwareDatetime | None = None
    naive: NaiveDatetime
    day: date


@pytest.mark.parametrize("field", ["aware", "optional"])
@pytest.mark.parametrize("suffix", ["", "__gte", "__lt"])
def test_aware_annotations_bind_iso_strings_with_storage_separator(field, suffix):
    """Parse annotated aware fields and retain their original minute offset."""
    # 0. This is an AwareDatetime field, not a plain datetime-only test seam.
    value = "2026-11-02T10:15:00.123456+05:45"
    result = compile_where(TemporalRow, {field + suffix: value})
    # 1. Native SQLite storage uses a space; no UTC conversion is permitted.
    assert result[1] == ["2026-11-02 10:15:00.123456+05:45"]
    assert "?" in result[0]
    assert value not in result[0]


def test_aware_datetime_objects_and_nullable_membership():
    """Bind Python dates and nullable IN members through the same field type."""
    # 0. Preserve nonzero offsets when trusted Python supplies datetime values.
    value = datetime(2026, 11, 2, 10, 15, tzinfo=timezone(timedelta(hours=-4)))
    assert compile_where(TemporalRow, {"aware": value}) == (
        '"aware" = ?', ["2026-11-02 10:15:00-04:00"],
    )
    # 1. Each membership element receives temporal validation independently.
    assert compile_where(TemporalRow, {"optional__in": [
        "2026-11-02T10:15:00Z", None,
    ]}) == ('"optional" IN (?,?)', ["2026-11-02 10:15:00+00:00", None])
    assert compile_where(TemporalRow, {"optional": None}) == (
        '"optional" IS NULL', [],
    )


@pytest.mark.parametrize("field", ["aware", "optional"])
@pytest.mark.parametrize("value", ["2026-11-02T10:15:00", "not-a-date"])
def test_aware_annotations_reject_naive_and_invalid_values(field, value):
    """Rebuild native field metadata instead of bypassing timezone validation."""
    # 0. Scalar and membership branches must both enforce awareness.
    with pytest.raises(ValueError):
        compile_where(TemporalRow, {field: value})
    with pytest.raises(ValueError):
        compile_where(TemporalRow, {field + "__in": [value]})


def test_naive_and_date_annotations_preserve_native_shapes():
    """Use date-only and naive-datetime storage forms without adding a zone."""
    # 0. Bind each declaration through its own Pydantic annotation.
    assert compile_where(TemporalRow, {
        "naive": "2026-11-02T10:15:00", "day": date(2026, 11, 2),
    }) == (
        '"naive" = ? AND "day" = ?', ["2026-11-02 10:15:00", "2026-11-02"],
    )
    # 1. NaiveDatetime does not silently accept aware inputs.
    with pytest.raises(ValueError):
        compile_where(TemporalRow, {"naive": "2026-11-02T10:15:00Z"})


# Changelog
# - 2026-11-02: Cover annotated temporal binding and native timezone constraints.
