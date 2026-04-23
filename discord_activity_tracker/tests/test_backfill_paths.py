"""Tests for backfill path ordering and date windows."""

from datetime import datetime
from pathlib import Path


from discord_activity_tracker.sync.backfill_paths import (
    discussion_json_sort_key,
    iter_discussion_json_files,
    json_path_in_date_window,
)


def test_sort_day_before_chunk(tmp_path: Path):
    d = tmp_path / "2017" / "2017-06"
    d.mkdir(parents=True)
    day = d / "2017-06-02.json"
    chunk = tmp_path / "2017-06-01_to_2017-06-10.json"
    day.write_text("{}")
    chunk.write_text("{}")
    ordered = list(iter_discussion_json_files(tmp_path))
    assert ordered[0].stem == "2017-06-02"
    assert "2017-06-01_to_2017-06-10" in ordered[1].stem


def test_skips_resource_fork(tmp_path: Path):
    (tmp_path / "._x.json").write_text("{}")
    (tmp_path / "ok.json").write_text("{}")
    assert list(iter_discussion_json_files(tmp_path)) == [tmp_path / "ok.json"]


def test_json_path_in_date_window_day():
    p = Path("/x/2024-01-15.json")
    since = datetime(2024, 1, 1)
    until = datetime(2024, 1, 20)
    assert json_path_in_date_window(p, since, until) is True
    assert json_path_in_date_window(p, datetime(2024, 2, 1), None) is False


def test_json_path_in_date_window_chunk():
    p = Path("/x/2024-01-01_to_2024-01-10.json")
    assert (
        json_path_in_date_window(p, datetime(2024, 1, 5), datetime(2024, 1, 20)) is True
    )
    assert json_path_in_date_window(p, datetime(2024, 1, 15), None) is False


def test_discussion_json_sort_key_stable():
    a = Path("/a/2017-06-01.json")
    b = Path("/b/2017-06-02.json")
    assert discussion_json_sort_key(a) < discussion_json_sort_key(b)
