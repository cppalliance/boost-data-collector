"""Tests for core.utils.datetime_parsing."""

import re
from datetime import datetime, timedelta, timezone

import pytest
from django.utils import timezone as django_timezone

from core.utils.datetime_parsing import (
    CANONICAL_INSTANT_UTC_Z_PATTERN,
    ensure_aware_utc,
    format_instant_iso_z,
    parse_iso_datetime,
    parse_iso_datetime_lenient,
)


def test_ensure_aware_utc_none():
    assert ensure_aware_utc(None) is None


def test_ensure_aware_utc_naive_becomes_utc():
    naive = datetime(2024, 6, 1, 12, 0, 0)
    assert django_timezone.is_naive(naive)
    out = ensure_aware_utc(naive)
    assert out is not None
    assert out.tzinfo == timezone.utc


def test_ensure_aware_utc_aware_converted_to_utc():
    dt = datetime(2024, 1, 1, 15, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    out = ensure_aware_utc(dt)
    assert out is not None
    assert out.tzinfo == timezone.utc
    assert out.hour == 13


def test_parse_iso_datetime_empty():
    assert parse_iso_datetime(None) is None
    assert parse_iso_datetime("") is None
    assert parse_iso_datetime("   ") is None


def test_parse_iso_datetime_z_suffix():
    dt = parse_iso_datetime("2024-03-15T10:30:00Z")
    assert dt is not None
    assert dt.tzinfo is None
    assert dt.year == 2024
    assert dt.month == 3
    assert dt.day == 15
    assert dt.hour == 10
    assert dt.minute == 30
    assert dt.second == 0


def test_parse_iso_datetime_date_only():
    dt = parse_iso_datetime("2024-12-25")
    assert dt is not None
    assert dt.tzinfo is None


def test_parse_iso_datetime_with_offset_strips_tz_to_naive_utc():
    dt = parse_iso_datetime("2024-01-01T00:00:00+05:00")
    assert dt is not None
    assert dt.tzinfo is None
    assert dt.year == 2023
    assert dt.month == 12
    assert dt.day == 31
    assert dt.hour == 19
    assert dt.minute == 0
    assert dt.second == 0


def test_parse_iso_datetime_invalid_raises():
    with pytest.raises(ValueError, match="Invalid ISO datetime"):
        parse_iso_datetime("not-a-date")


def test_format_instant_iso_z_empty():
    assert format_instant_iso_z(None) == ""
    assert format_instant_iso_z("") == ""
    assert format_instant_iso_z("   ") == ""


def test_format_instant_iso_z_z_suffix_utc():
    assert format_instant_iso_z("2024-03-15T10:30:00Z") == "2024-03-15T10:30:00Z"


def test_format_instant_iso_z_offset_to_z():
    assert format_instant_iso_z("2024-01-01T00:00:00+05:00") == "2023-12-31T19:00:00Z"


def test_format_instant_iso_z_invalid_returns_original():
    assert format_instant_iso_z("not-a-date") == "not-a-date"


def test_parse_iso_datetime_lenient_empty():
    assert parse_iso_datetime_lenient(None) is None
    assert parse_iso_datetime_lenient("") is None
    assert parse_iso_datetime_lenient("   ") is None


def test_parse_iso_datetime_lenient_z_utc_aware():
    dt = parse_iso_datetime_lenient("2024-01-15T10:30:00Z")
    assert dt == datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)


def test_parse_iso_datetime_lenient_invalid_returns_none():
    assert parse_iso_datetime_lenient("not-a-date") is None


@pytest.mark.parametrize(
    "date_str,expected_year",
    [
        ("2023-06-01T00:00:00Z", 2023),
        ("2025-12-31T23:59:59Z", 2025),
    ],
)
def test_parse_iso_datetime_lenient_parametrized(date_str, expected_year):
    result = parse_iso_datetime_lenient(date_str)
    assert result is not None
    assert result.year == expected_year


def test_canonical_instant_utc_z_pattern():
    pat = re.compile(CANONICAL_INSTANT_UTC_Z_PATTERN)
    assert pat.fullmatch("2026-01-01T00:00:00Z")
    assert pat.fullmatch("2026-01-01T00:00:00.5Z")
    assert pat.fullmatch("2026-01-01T00:00:00.123456Z")
    assert pat.fullmatch("2026-01-01T00:00:00+00:00") is None
    assert pat.fullmatch("") is None
