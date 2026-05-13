"""Coverage for pinecone_runner."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from discord_activity_tracker.pinecone_runner import task_discord_pinecone_sync


def test_task_discord_pinecone_sync_dry_run():
    task_discord_pinecone_sync(dry_run=True)


@pytest.mark.django_db
def test_task_discord_pinecone_sync_skips_when_app_type_empty(monkeypatch, settings):
    monkeypatch.setattr(settings, "PINECONE_DISCORD_APP_TYPE", "")
    monkeypatch.setattr(settings, "PINECONE_DISCORD_NAMESPACE", "ns")
    task_discord_pinecone_sync(dry_run=False)


@pytest.mark.django_db
def test_task_discord_pinecone_sync_skips_when_namespace_empty(monkeypatch, settings):
    monkeypatch.setattr(settings, "PINECONE_DISCORD_APP_TYPE", "app")
    monkeypatch.setattr(settings, "PINECONE_DISCORD_NAMESPACE", "  ")
    task_discord_pinecone_sync(dry_run=False)


@pytest.mark.django_db
def test_task_discord_pinecone_sync_calls_run_command(monkeypatch, settings):
    monkeypatch.setattr(settings, "PINECONE_DISCORD_APP_TYPE", "discord")
    monkeypatch.setattr(settings, "PINECONE_DISCORD_NAMESPACE", "ns")
    with patch("discord_activity_tracker.pinecone_runner.call_command") as cc:
        task_discord_pinecone_sync(dry_run=False)
    cc.assert_called_once()


@pytest.mark.django_db
def test_task_discord_pinecone_sync_swallows_call_command_error(monkeypatch, settings):
    monkeypatch.setattr(settings, "PINECONE_DISCORD_APP_TYPE", "discord")
    monkeypatch.setattr(settings, "PINECONE_DISCORD_NAMESPACE", "ns")
    with patch(
        "discord_activity_tracker.pinecone_runner.call_command",
        side_effect=RuntimeError("no command"),
    ):
        task_discord_pinecone_sync(dry_run=False)
