"""Coverage for task_markdown_export_and_push."""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from discord_activity_tracker.management.commands.run_discord_activity_tracker import (
    DiscordActivityCollector,
    task_markdown_export_and_push,
)
from discord_activity_tracker.models import DiscordServer


@pytest.mark.django_db
def test_task_markdown_skip_export():
    cmd = MagicMock()
    cmd.stdout = StringIO()
    cmd.style = MagicMock()
    cmd.style.WARNING = lambda x: x
    cmd.style.SUCCESS = lambda x: x
    collector = DiscordActivityCollector(cmd=cmd, options={})
    task_markdown_export_and_push(
        dry_run=False,
        skip_markdown_export=True,
        skip_remote_push=False,
        guild_id=1,
        collector=collector,
    )


@pytest.mark.django_db
def test_task_markdown_no_context_path(monkeypatch, tmp_path, settings):
    monkeypatch.setattr(settings, "DISCORD_CONTEXT_REPO_PATH", "")
    cmd = MagicMock()
    cmd.stdout = StringIO()
    cmd.style = MagicMock()
    cmd.style.WARNING = lambda x: x
    collector = DiscordActivityCollector(cmd=cmd, options={})
    task_markdown_export_and_push(
        dry_run=False,
        skip_markdown_export=False,
        skip_remote_push=False,
        guild_id=1,
        collector=collector,
    )


@pytest.mark.django_db
def test_task_markdown_dry_run(tmp_path, settings):
    p = tmp_path / "ctx"
    p.mkdir()
    settings.DISCORD_CONTEXT_REPO_PATH = str(p)
    cmd = MagicMock()
    cmd.stdout = StringIO()
    cmd.style = MagicMock()
    cmd.style.WARNING = lambda x: x
    collector = DiscordActivityCollector(cmd=cmd, options={})
    task_markdown_export_and_push(
        dry_run=True,
        skip_markdown_export=False,
        skip_remote_push=False,
        guild_id=1,
        collector=collector,
    )
    assert "ctx" in cmd.stdout.getvalue() or "dry-run" in cmd.stdout.getvalue().lower()


@pytest.mark.django_db
def test_task_markdown_server_not_in_db(tmp_path, settings):
    settings.DISCORD_CONTEXT_REPO_PATH = str(tmp_path / "ctx")
    (tmp_path / "ctx").mkdir()
    cmd = MagicMock()
    cmd.stdout = StringIO()
    cmd.style = MagicMock()
    cmd.style.WARNING = lambda x: x
    cmd.style.SUCCESS = lambda x: x
    collector = DiscordActivityCollector(cmd=cmd, options={})
    task_markdown_export_and_push(
        dry_run=False,
        skip_markdown_export=False,
        skip_remote_push=True,
        guild_id=999888777666,
        collector=collector,
    )
    assert "not in DB" in cmd.stdout.getvalue() or "Server" in cmd.stdout.getvalue()


@pytest.mark.django_db
def test_task_markdown_export_success(tmp_path, settings):
    settings.DISCORD_CONTEXT_REPO_PATH = str(tmp_path / "ctx")
    (tmp_path / "ctx").mkdir()
    srv = DiscordServer.objects.create(server_id=424242, server_name="S", icon_url="")
    cmd = MagicMock()
    cmd.stdout = StringIO()
    cmd.style = MagicMock()
    cmd.style.WARNING = lambda x: x
    cmd.style.SUCCESS = lambda x: x
    collector = DiscordActivityCollector(cmd=cmd, options={})
    with patch(
        "discord_activity_tracker.sync.export.export_and_push",
        return_value=True,
    ):
        task_markdown_export_and_push(
            dry_run=False,
            skip_markdown_export=False,
            skip_remote_push=True,
            guild_id=srv.server_id,
            collector=collector,
        )
    assert "Exported" in cmd.stdout.getvalue()


@pytest.mark.django_db
def test_task_markdown_export_warns_on_false(tmp_path, settings):
    settings.DISCORD_CONTEXT_REPO_PATH = str(tmp_path / "ctx")
    (tmp_path / "ctx").mkdir()
    srv = DiscordServer.objects.create(server_id=424243, server_name="S2", icon_url="")
    cmd = MagicMock()
    cmd.stdout = StringIO()
    cmd.style = MagicMock()
    cmd.style.WARNING = lambda x: x
    cmd.style.SUCCESS = lambda x: x
    collector = DiscordActivityCollector(cmd=cmd, options={})
    with patch(
        "discord_activity_tracker.sync.export.export_and_push",
        return_value=False,
    ):
        task_markdown_export_and_push(
            dry_run=False,
            skip_markdown_export=False,
            skip_remote_push=True,
            guild_id=srv.server_id,
            collector=collector,
        )
    assert "No markdown" in cmd.stdout.getvalue()


@pytest.mark.django_db
def test_task_markdown_auto_commit_path(tmp_path, settings):
    settings.DISCORD_CONTEXT_REPO_PATH = str(tmp_path / "ctx")
    (tmp_path / "ctx").mkdir()
    settings.DISCORD_CONTEXT_AUTO_COMMIT = True
    srv = DiscordServer.objects.create(server_id=424245, server_name="S4", icon_url="")
    cmd = MagicMock()
    cmd.stdout = StringIO()
    cmd.style = MagicMock()
    cmd.style.WARNING = lambda x: x
    cmd.style.SUCCESS = lambda x: x
    collector = DiscordActivityCollector(cmd=cmd, options={})
    with patch(
        "discord_activity_tracker.sync.export.export_and_push",
        return_value=True,
    ):
        task_markdown_export_and_push(
            dry_run=False,
            skip_markdown_export=False,
            skip_remote_push=False,
            guild_id=srv.server_id,
            collector=collector,
        )
