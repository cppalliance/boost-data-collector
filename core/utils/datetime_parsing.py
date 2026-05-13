"""Parsing date/time strings from CLI, JSON, and APIs."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from django.utils import timezone as django_timezone

logger = logging.getLogger(__name__)

# ISO 8601 UTC instant with ``Z`` (optional fractional seconds). Used by JSON Schema and Pydantic.
CANONICAL_INSTANT_UTC_Z_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"


def ensure_aware_utc(dt: datetime | None) -> datetime | None:
    """
    Normalize a datetime for ``DateTimeField`` when ``USE_TZ`` is True.

    Naive values are treated as UTC. Aware values are converted to UTC.
    """
    if dt is None:
        return None
    if django_timezone.is_naive(dt):
        return django_timezone.make_aware(dt, timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_iso_datetime_lenient(raw: str | None) -> datetime | None:
    """
    Parse ISO-like date/datetime strings from APIs (GitHub, Discord, etc.).

    Returns ``None`` for empty/whitespace input or on parse failure (logs at DEBUG).
    ``Z`` is normalized to ``+00:00`` for :meth:`datetime.fromisoformat`. Preserves
    timezone awareness when present (unlike :func:`parse_iso_datetime`, which returns
    naive UTC).

    :func:`parse_iso_datetime` delegates here for the actual parse, then applies
    strict error handling and naive-UTC normalization.
    """
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError as e:
        logger.debug("Failed to parse datetime %r: %s", s, e)
        return None


def parse_iso_datetime(raw: str | None) -> datetime | None:
    """
    Parse a date or datetime string using ``datetime.fromisoformat``.

    Delegates to :func:`parse_iso_datetime_lenient` for parsing. Empty or
    whitespace-only input returns ``None``.

    Raises:
        ValueError: If the string is non-empty but cannot be parsed.

    Timezone-aware values are converted to UTC and returned as **naive** datetimes
    (``tzinfo`` cleared). Naive input is returned unchanged.
    """
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip()
    dt = parse_iso_datetime_lenient(raw)
    if dt is None:
        raise ValueError(f"Invalid ISO datetime ({s!r})")
    if dt.tzinfo:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def format_instant_iso_z(raw: str | None) -> str:
    """
    Normalize a date/datetime string to an ISO 8601 **instant** in UTC with a ``Z`` suffix.

    Uses :func:`parse_iso_datetime` for parsing. Empty or whitespace-only input returns
    ``""``. If the string is non-empty but cannot be parsed, returns the stripped
    original string (lenient handling for odd exporter payloads).

    Naive datetimes from parsing are interpreted as UTC wall clock before formatting.
    """
    text = (raw or "").strip()
    if not text:
        return ""
    try:
        dt = parse_iso_datetime(text)
    except ValueError:
        return text
    if dt is None:
        return text
    aware = dt.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
