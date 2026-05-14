"""Tests for sync/exporter_window.py."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from cppa_user_tracker.models import DiscordProfile
from discord_activity_tracker.models import (
    DiscordChannel,
    DiscordMessage,
    DiscordServer,
)
from discord_activity_tracker.sync.exporter_window import (
    latest_message_created_at_for_guild,
)


def _uid() -> int:
    return uuid.uuid4().int % (2**50)


@pytest.mark.django_db
def test_latest_message_empty_db():
    assert latest_message_created_at_for_guild(999001, channel_ids=None) is None


@pytest.mark.django_db
def test_latest_message_ignores_deleted():
    srv = DiscordServer.objects.create(server_id=_uid(), server_name="G", icon_url="")
    ch = DiscordChannel.objects.create(
        server=srv, channel_id=_uid(), channel_name="c", channel_type="text"
    )
    author = DiscordProfile.objects.create(
        discord_user_id=_uid(),
        username="u",
        display_name="U",
        avatar_url="",
        is_bot=False,
    )
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    DiscordMessage.objects.create(
        message_id=_uid(),
        channel=ch,
        author=author,
        content="deleted",
        message_created_at=t,
        is_deleted=True,
    )
    assert latest_message_created_at_for_guild(srv.server_id, channel_ids=None) is None


@pytest.mark.django_db
def test_latest_message_respects_channel_allowlist():
    srv = DiscordServer.objects.create(server_id=_uid(), server_name="G", icon_url="")
    ch1 = DiscordChannel.objects.create(
        server=srv, channel_id=_uid(), channel_name="a", channel_type="text"
    )
    ch2 = DiscordChannel.objects.create(
        server=srv, channel_id=_uid(), channel_name="b", channel_type="text"
    )
    author = DiscordProfile.objects.create(
        discord_user_id=_uid(),
        username="u",
        display_name="U",
        avatar_url="",
        is_bot=False,
    )
    t1 = datetime(2026, 2, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 3, 1, tzinfo=timezone.utc)
    DiscordMessage.objects.create(
        message_id=_uid(),
        channel=ch1,
        author=author,
        content="older",
        message_created_at=t1,
    )
    DiscordMessage.objects.create(
        message_id=_uid(),
        channel=ch2,
        author=author,
        content="newer",
        message_created_at=t2,
    )
    latest = latest_message_created_at_for_guild(
        srv.server_id, channel_ids=[ch1.channel_id]
    )
    assert latest == t1
