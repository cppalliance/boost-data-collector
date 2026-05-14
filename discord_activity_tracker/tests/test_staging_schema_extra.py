"""Extra coverage for staging_schema."""

from __future__ import annotations

import pytest

from discord_activity_tracker.staging_schema import (
    build_staging_json_schema_bundle,
    validate_normalized_message,
    write_staging_json_schema,
)


def test_build_staging_json_schema_bundle_has_models():
    bundle = build_staging_json_schema_bundle()
    assert bundle["title"] == "discord_staging_v1"
    assert "discord_chat_exporter_envelope" in bundle
    assert "normalized_discord_message" in bundle


def test_write_staging_json_schema_writes_file(tmp_path):
    p = tmp_path / "out.json"
    out = write_staging_json_schema(p)
    assert out == p
    assert p.read_text(encoding="utf-8").startswith("{")


@pytest.mark.django_db
def test_validate_normalized_blank_edited_at_becomes_none():
    from discord_activity_tracker.sync.chat_exporter import (
        convert_exporter_message_to_dict,
    )

    raw = {
        "id": "1",
        "timestamp": "2026-01-01T00:00:00Z",
        "timestampEdited": "   ",
        "content": "hello world example text long enough",
        "author": {"id": "1", "name": "a"},
        "attachments": [],
        "reactions": [],
    }
    d = convert_exporter_message_to_dict(raw, server_id=1, channel_id=2)
    m = validate_normalized_message(d, source="t")
    assert m.edited_at is None
