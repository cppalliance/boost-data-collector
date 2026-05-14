"""Coverage for workspace.clear_exporter_staging_dir."""

from __future__ import annotations

import pytest

from discord_activity_tracker.workspace import (
    clear_exporter_staging_dir,
    get_exporter_staging_dir,
)


@pytest.mark.django_db
def test_clear_exporter_staging_dir_removes_children(tmp_path, settings):
    settings.WORKSPACE_DIR = tmp_path / "ws"
    settings.WORKSPACE_DIR.mkdir(parents=True)
    staging = get_exporter_staging_dir()
    (staging / "a.json").write_text("{}", encoding="utf-8")
    sub = staging / "sub"
    sub.mkdir()
    (sub / "x.txt").write_text("x", encoding="utf-8")
    clear_exporter_staging_dir()
    assert list(staging.iterdir()) == []
