"""Coverage for sync/export.py (markdown export, git helpers)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone as django_timezone

from cppa_user_tracker.models import DiscordProfile
from discord_activity_tracker.models import (
    DiscordChannel,
    DiscordMessage,
    DiscordServer,
)
from discord_activity_tracker.sync.export import (
    _strip_invisible_unicode,
    commit_and_push_context_repo,
    export_all_active_channels,
    export_and_push,
    export_channel_to_markdown,
    generate_markdown_content,
)


def _uid() -> int:
    return uuid.uuid4().int % (2**50)


@pytest.fixture
def export_server(db):
    return DiscordServer.objects.create(
        server_id=_uid(), server_name="Export Guild", icon_url=""
    )


@pytest.fixture
def export_channel(db, export_server):
    return DiscordChannel.objects.create(
        server=export_server,
        channel_id=_uid(),
        channel_name="general",
        channel_type="text",
    )


@pytest.fixture
def export_author(db):
    return DiscordProfile.objects.create(
        discord_user_id=_uid(),
        username="alice",
        display_name="Alice",
        avatar_url="",
        is_bot=False,
    )


def test_strip_invisible_unicode_empty_returns_empty():
    assert _strip_invisible_unicode("") == ""


@pytest.mark.django_db
def test_generate_markdown_microsecond_timestamp(export_channel, export_author):
    ts = datetime(2026, 3, 1, 10, 0, 0, 500000, tzinfo=timezone.utc)
    msg = DiscordMessage.objects.create(
        message_id=_uid(),
        channel=export_channel,
        author=export_author,
        content="hi",
        message_created_at=ts,
    )
    out = generate_markdown_content(export_channel, "2026-03", [msg])
    assert "10:00:00.500" in out


@pytest.mark.django_db
def test_generate_markdown_reply_same_day(export_channel, export_author):
    root = DiscordMessage.objects.create(
        message_id=_uid(),
        channel=export_channel,
        author=export_author,
        content="root text here",
        message_created_at=datetime(2026, 3, 5, 9, 0, 0, tzinfo=timezone.utc),
    )
    reply = DiscordMessage.objects.create(
        message_id=_uid(),
        channel=export_channel,
        author=export_author,
        content="reply",
        message_created_at=datetime(2026, 3, 5, 9, 5, 0, tzinfo=timezone.utc),
        reply_to_message_id=root.message_id,
    )
    out = generate_markdown_content(export_channel, "2026-03", [root, reply])
    assert "Reply to:" in out
    assert "Original:" in out


@pytest.mark.django_db
def test_generate_markdown_reply_split_by_day_other_month(
    export_channel, export_author
):
    root = DiscordMessage.objects.create(
        message_id=_uid(),
        channel=export_channel,
        author=export_author,
        content="x" * 90,
        message_created_at=datetime(2026, 2, 28, 23, 0, 0, tzinfo=timezone.utc),
    )
    reply = DiscordMessage.objects.create(
        message_id=_uid(),
        channel=export_channel,
        author=export_author,
        content="r",
        message_created_at=datetime(2026, 3, 1, 1, 0, 0, tzinfo=timezone.utc),
        reply_to_message_id=root.message_id,
    )
    out = generate_markdown_content(
        export_channel, "2026-03", [reply], date_str="2026-03-01", split_by_day=True
    )
    assert "../2026-02/" in out or "2026-02" in out


@pytest.mark.django_db
def test_generate_markdown_reply_missing_parent_skipped(export_channel, export_author):
    msg = DiscordMessage.objects.create(
        message_id=_uid(),
        channel=export_channel,
        author=export_author,
        content="orphan",
        message_created_at=datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
        reply_to_message_id=999999999999,
    )
    out = generate_markdown_content(export_channel, "2026-03", [msg])
    assert "orphan" in out
    assert "Reply to:" not in out


@pytest.mark.django_db
def test_generate_markdown_code_fence_and_unclosed(export_channel, export_author):
    msg = DiscordMessage.objects.create(
        message_id=_uid(),
        channel=export_channel,
        author=export_author,
        content="```\nunclosed",
        message_created_at=datetime(2026, 3, 2, 8, 0, 0, tzinfo=timezone.utc),
    )
    out = generate_markdown_content(export_channel, "2026-03", [msg])
    assert "<!-- -->" in out
    assert out.count("```") >= 2


@pytest.mark.django_db
def test_generate_markdown_attachments(export_channel, export_author):
    msg = DiscordMessage.objects.create(
        message_id=_uid(),
        channel=export_channel,
        author=export_author,
        content="see file",
        message_created_at=datetime(2026, 3, 3, 8, 0, 0, tzinfo=timezone.utc),
        has_attachments=True,
        attachment_urls=["https://cdn.discord.com/a/b/file.png?ex=1"],
    )
    out = generate_markdown_content(export_channel, "2026-03", [msg])
    assert "Attachments:" in out
    assert "file.png" in out


@pytest.mark.django_db
def test_generate_markdown_reply_same_month_aggregate_link(
    export_channel, export_author
):
    """Reply in same calendar month as year_month uses in-page anchor (export.py ~168)."""
    root = DiscordMessage.objects.create(
        message_id=_uid(),
        channel=export_channel,
        author=export_author,
        content="root",
        message_created_at=datetime(2026, 3, 1, 8, 0, 0, tzinfo=timezone.utc),
    )
    reply = DiscordMessage.objects.create(
        message_id=_uid(),
        channel=export_channel,
        author=export_author,
        content="later",
        message_created_at=datetime(2026, 3, 15, 9, 0, 0, tzinfo=timezone.utc),
        reply_to_message_id=root.message_id,
    )
    out = generate_markdown_content(export_channel, "2026-03", [root, reply])
    assert "Reply to:" in out
    assert "](" in out and "#" in out


@pytest.mark.django_db
def test_generate_markdown_reply_microsecond_reply_time(export_channel, export_author):
    root = DiscordMessage.objects.create(
        message_id=_uid(),
        channel=export_channel,
        author=export_author,
        content="root",
        message_created_at=datetime(2026, 3, 10, 1, 0, 0, tzinfo=timezone.utc),
    )
    reply = DiscordMessage.objects.create(
        message_id=_uid(),
        channel=export_channel,
        author=export_author,
        content="r",
        message_created_at=datetime(2026, 3, 10, 1, 0, 0, 123000, tzinfo=timezone.utc),
        reply_to_message_id=root.message_id,
    )
    out = generate_markdown_content(export_channel, "2026-03", [root, reply])
    assert "Reply to:" in out


@pytest.mark.django_db
def test_export_channel_to_markdown_writes_per_day_files(
    export_channel, export_author, tmp_path
):
    repo = tmp_path / "ctx"
    repo.mkdir()
    t0 = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    DiscordMessage.objects.create(
        message_id=_uid(),
        channel=export_channel,
        author=export_author,
        content="day a",
        message_created_at=t0,
    )
    DiscordMessage.objects.create(
        message_id=_uid(),
        channel=export_channel,
        author=export_author,
        content="day b",
        message_created_at=t0 + timedelta(days=1),
    )
    paths = export_channel_to_markdown(export_channel, "2026-04", repo)
    assert paths is not None and len(paths) == 2
    assert all(p.suffix == ".md" for p in paths)


@pytest.mark.django_db
def test_export_channel_to_markdown_empty_month_returns_none(export_channel, tmp_path):
    assert export_channel_to_markdown(export_channel, "2026-05", tmp_path) is None


@pytest.mark.django_db
def test_export_all_active_channels_collects_paths(
    export_server, export_channel, export_author, tmp_path, monkeypatch
):
    now = django_timezone.now()
    DiscordMessage.objects.create(
        message_id=_uid(),
        channel=export_channel,
        author=export_author,
        content="recent",
        message_created_at=now - timedelta(days=1),
    )
    ym = now.strftime("%Y-%m")
    fake_paths = [tmp_path / f"{ym}-stub.md"]

    def fake_export(ch, year_month, out_dir):
        if ch.pk == export_channel.pk and year_month == ym:
            return fake_paths
        return None

    monkeypatch.setattr(
        "discord_activity_tracker.sync.export.export_channel_to_markdown",
        fake_export,
    )
    paths = export_all_active_channels(
        tmp_path, export_server, months_back=1, active_days=30
    )
    assert paths == fake_paths


@pytest.mark.django_db
def test_export_all_active_channels_continues_on_channel_error(
    export_server, export_channel, export_author, tmp_path, monkeypatch
):
    now = django_timezone.now()
    DiscordMessage.objects.create(
        message_id=_uid(),
        channel=export_channel,
        author=export_author,
        content="recent",
        message_created_at=now - timedelta(hours=1),
    )

    def boom(*_a, **_k):
        raise RuntimeError("export failed")

    monkeypatch.setattr(
        "discord_activity_tracker.sync.export.export_channel_to_markdown",
        boom,
    )
    paths = export_all_active_channels(tmp_path, export_server, months_back=1)
    assert paths == []


def test_commit_and_push_no_changes(tmp_path):
    calls: list[list[str]] = []

    def run_side_effect(cmd, **_kwargs):
        calls.append(list(cmd))
        if "status" in cmd:
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("discord_activity_tracker.sync.export.subprocess.run", run_side_effect):
        assert commit_and_push_context_repo(tmp_path) is True
    assert any("status" in c for c in calls)


def test_commit_and_push_full_flow(tmp_path):
    seq = iter(
        [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout=" M file\n", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
    )

    def run_side_effect(cmd, **_kwargs):
        return next(seq)

    with patch("discord_activity_tracker.sync.export.subprocess.run", run_side_effect):
        assert commit_and_push_context_repo(tmp_path, "msg") is True


def test_commit_and_push_git_error(tmp_path):
    import subprocess as sp

    def run_side_effect(cmd, **_kwargs):
        raise sp.CalledProcessError(1, cmd, stderr="err")

    with patch("discord_activity_tracker.sync.export.subprocess.run", run_side_effect):
        assert commit_and_push_context_repo(tmp_path) is False


def test_commit_and_push_generic_exception(tmp_path):
    with patch(
        "discord_activity_tracker.sync.export.subprocess.run",
        side_effect=OSError("boom"),
    ):
        assert commit_and_push_context_repo(tmp_path) is False


@pytest.mark.django_db
def test_export_and_push_no_files_returns_false(export_server, tmp_path):
    with patch(
        "discord_activity_tracker.sync.export.export_all_active_channels",
        return_value=[],
    ):
        assert export_and_push(tmp_path, export_server) is False


@pytest.mark.django_db
def test_export_and_push_files_no_auto_commit(export_server, tmp_path):
    with patch(
        "discord_activity_tracker.sync.export.export_all_active_channels",
        return_value=[tmp_path / "a.md"],
    ):
        assert export_and_push(tmp_path, export_server, auto_commit=False) is True


@pytest.mark.django_db
def test_export_and_push_auto_commit(export_server, tmp_path):
    with (
        patch(
            "discord_activity_tracker.sync.export.export_all_active_channels",
            return_value=[tmp_path / "a.md"],
        ),
        patch(
            "discord_activity_tracker.sync.export.commit_and_push_context_repo",
            return_value=True,
        ) as m,
    ):
        assert export_and_push(tmp_path, export_server, auto_commit=True) is True
    m.assert_called_once()
