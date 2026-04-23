"""Path ordering and date-window filtering for Discussion-style DiscordChatExporter JSON trees."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Iterator, Optional


def is_resource_fork_json(path: Path) -> bool:
    return path.name.startswith("._") or any(p.startswith("._") for p in path.parts)


def discussion_json_sort_key(path: Path) -> tuple:
    """Sort per-day files by calendar day, then chunk files by end date then start date."""
    if is_resource_fork_json(path):
        return ("z", "", "", str(path))
    stem = path.stem
    if "_to_" in stem:
        a, b = stem.split("_to_", 1)
        if (
            len(a) == 10
            and len(b) == 10
            and a[4] == "-"
            and a[7] == "-"
            and b[4] == "-"
            and b[7] == "-"
        ):
            return ("1", b, a, str(path))
    if len(stem) == 10 and stem[4] == "-" and stem[7] == "-":
        return ("0", stem, "", str(path))
    return ("2", stem, "", str(path))


def iter_discussion_json_files(root: Path) -> Iterator[Path]:
    if not root.is_dir():
        return
    for p in sorted(root.rglob("*.json"), key=discussion_json_sort_key):
        if is_resource_fork_json(p):
            continue
        yield p


def _as_date(d: Optional[datetime]) -> Optional[date]:
    if d is None:
        return None
    return d.date() if isinstance(d, datetime) else None


def _day_in_window(
    since: Optional[datetime],
    until: Optional[datetime],
    day: date,
) -> bool:
    sd = _as_date(since)
    ud = _as_date(until)
    if sd and day < sd:
        return False
    if ud and day > ud:
        return False
    return True


def _range_overlaps(
    since: Optional[datetime],
    until: Optional[datetime],
    start_day: date,
    end_day: date,
) -> bool:
    sd = _as_date(since)
    ud = _as_date(until)
    if sd and end_day < sd:
        return False
    if ud and start_day > ud:
        return False
    return True


def json_path_in_date_window(
    path: Path,
    since: Optional[datetime],
    until: Optional[datetime],
) -> bool:
    """Include file when its filename encodes a day or chunk range overlapping ``since``/``until``."""
    if since is None and until is None:
        return True
    stem = path.stem
    if "_to_" in stem:
        parts = stem.split("_to_", 1)
        if len(parts) == 2 and len(parts[0]) == 10 and len(parts[1]) == 10:
            try:
                d0 = date.fromisoformat(parts[0])
                d1 = date.fromisoformat(parts[1])
            except ValueError:
                return True
            return _range_overlaps(since, until, d0, d1)
    if len(stem) == 10:
        try:
            d = date.fromisoformat(stem)
        except ValueError:
            return True
        return _day_in_window(since, until, d)
    return True
