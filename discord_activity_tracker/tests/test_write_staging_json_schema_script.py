"""Coverage for write_staging_json_schema script entrypoint."""

from __future__ import annotations

from unittest.mock import patch

import discord_activity_tracker.scripts.write_staging_json_schema as mod


def test_write_staging_json_schema_main_prints_path(tmp_path, capsys):
    target = tmp_path / "schema.json"
    with patch.object(mod, "write_staging_json_schema", return_value=target):
        mod.main()
    out = capsys.readouterr().out.strip()
    assert str(target) in out
