"""Tests for discord_activity_tracker.staging_schema validation."""

import pytest

from discord_activity_tracker.staging_schema import (
    validate_envelope,
    validate_normalized_message,
)
from discord_activity_tracker.sync.chat_exporter import convert_exporter_message_to_dict


def _minimal_exporter_message():
    return {
        "id": "1399663560723923005",
        "type": "Default",
        "isPinned": False,
        "timestamp": "2026-01-01T12:00:00Z",
        "content": "hello world example text long enough",
        "author": {"id": "1082347485026070548", "name": "user"},
        "attachments": [],
        "reactions": [],
    }


def test_validate_normalized_well_formed_message():
    raw = _minimal_exporter_message()
    converted = convert_exporter_message_to_dict(
        raw, server_id=900, channel_id=851121440425639956
    )
    model = validate_normalized_message(converted, source="test")
    assert model.id == 1399663560723923005
    assert model.source_url.startswith("https://discord.com/channels/")
    assert model.actor_id == "1082347485026070548"
    assert model.occurred_at.endswith("Z")


def test_validate_normalized_well_formed_reactions():
    raw = {
        "id": "1",
        "timestamp": "2026-01-01T00:00:00Z",
        "content": "x",
        "author": {"id": "1", "name": "a"},
        "attachments": [],
        "reactions": [
            {"emoji": {"id": None, "name": "thumbsup", "isAnimated": False}, "count": 2}
        ],
    }
    converted = convert_exporter_message_to_dict(raw, server_id=1, channel_id=2)
    model = validate_normalized_message(converted)
    assert len(model.reactions) == 1
    assert model.reactions[0].emoji == "thumbsup"
    assert model.reactions[0].count == 2


def test_validate_normalized_malformed_rejects_with_valueerror():
    bad = {
        "id": 1,
        "content": "",
        "created_at": "",
        "edited_at": None,
        "message_type": "Default",
        "is_pinned": False,
        "author": {
            "id": 0,
            "username": "x",
            "global_name": "",
            "avatar_url": "",
            "bot": False,
        },
        "attachments": [],
        "reactions": [],
        "reference": None,
    }
    with pytest.raises(
        ValueError, match="Invalid normalized Discord message"
    ) as excinfo:
        validate_normalized_message(bad, source="unit")
    assert "pydantic" not in type(excinfo.value).__name__.lower()
    err = excinfo.value
    assert err.__cause__ is not None


def test_validate_normalized_rejects_created_at_without_z_suffix():
    bad = {
        "id": 1,
        "content": "x",
        "created_at": "2026-01-01T00:00:00+00:00",
        "edited_at": None,
        "message_type": "Default",
        "is_pinned": False,
        "author": {
            "id": 0,
            "username": "x",
            "global_name": "",
            "avatar_url": "",
            "bot": False,
        },
        "attachments": [],
        "reactions": [],
        "reference": None,
    }
    with pytest.raises(ValueError, match="Invalid normalized Discord message"):
        validate_normalized_message(bad, source="unit")


def test_validate_envelope_rejects_non_list_messages():
    with pytest.raises(ValueError, match="Invalid Discord export envelope"):
        validate_envelope(
            {"guild": {}, "channel": {}, "messages": "nope"}, source="x.json"
        )


def test_validate_envelope_messages_none_becomes_empty_list():
    env = validate_envelope(
        {
            "guild": {"id": "1", "name": "G"},
            "channel": {"id": "2", "name": "C"},
            "messages": None,
        },
        source="empty.json",
    )
    assert env.messages == []
    guild = env.guild.model_dump(by_alias=True)
    channel = env.channel.model_dump(by_alias=True)
    assert guild.get("id") == "1"
    assert channel.get("name") == "C"
