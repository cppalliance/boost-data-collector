"""Tests for backfill JSON import."""

import json
import shutil
from pathlib import Path

import pytest
from django.core.management import call_command

from discord_activity_tracker.models import DiscordMessage


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "backfill_minimal.json"


@pytest.mark.django_db
class TestBackfillDiscordJson:
    def test_persist_fixture_creates_message(self, settings):
        settings.DISCORD_SERVER_ID = "331718482485837825"
        import asyncio

        from discord_activity_tracker.sync.importer import (
            persist_exporter_channel_payloads,
        )

        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload = {
            "guild": data["guild"],
            "channel": data["channel"],
            "messages": data["messages"],
        }
        asyncio.run(
            persist_exporter_channel_payloads(
                [payload],
                expected_guild_id=331718482485837825,
            )
        )
        assert DiscordMessage.objects.filter(message_id=1900000000000000001).exists()

    def test_backfill_command_imports_file(self, settings, tmp_path):
        settings.DISCORD_SERVER_ID = "331718482485837825"
        layout = tmp_path / "2014" / "2014-06"
        layout.mkdir(parents=True)
        target = layout / "2014-06-01.json"
        shutil.copy(FIXTURE, target)

        call_command(
            "backfill_discord_json",
            path=str(tmp_path),
            guild_id=331718482485837825,
        )
        assert DiscordMessage.objects.filter(message_id=1900000000000000001).exists()
