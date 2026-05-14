"""Extra coverage for preprocessor reply chains and edge paths."""

from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone as django_timezone

from cppa_user_tracker.models import DiscordProfile
from discord_activity_tracker.models import (
    DiscordChannel,
    DiscordMessage,
    DiscordServer,
)
from discord_activity_tracker.preprocessor import (
    _build_reply_chains,
    _chain_to_document,
    preprocess_discord_for_pinecone,
)


def _uid() -> int:
    return uuid.uuid4().int % (2**50)


@pytest.mark.django_db
def test_build_reply_chains_skips_reply_having_parent_in_batch():
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
    root = DiscordMessage.objects.create(
        message_id=_uid(),
        channel=ch,
        author=author,
        content="root msg here long enough for any downstream checks",
        message_created_at=django_timezone.now(),
    )
    reply = DiscordMessage.objects.create(
        message_id=_uid(),
        channel=ch,
        author=author,
        content="reply text here long enough for any downstream checks",
        message_created_at=django_timezone.now(),
        reply_to_message_id=root.message_id,
    )
    chains = _build_reply_chains([root, reply])
    assert len(chains) == 1
    assert {m.message_id for m in chains[0]} == {root.message_id, reply.message_id}


@pytest.mark.django_db
def test_build_reply_chains_orphan_at_end():
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
    orphan = DiscordMessage.objects.create(
        message_id=_uid(),
        channel=ch,
        author=author,
        content="orphan reply text here long enough for downstream checks",
        message_created_at=django_timezone.now(),
        reply_to_message_id=999999999999,
    )
    chains = _build_reply_chains([orphan])
    assert len(chains) == 1
    assert chains[0] == [orphan]


@pytest.mark.django_db
def test_chain_to_document_long_content_returns_document():
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
    root = DiscordMessage.objects.create(
        message_id=_uid(),
        channel=ch,
        author=author,
        content="x" * 80,
        message_created_at=django_timezone.now(),
    )
    assert _chain_to_document([root]) is not None


@pytest.mark.django_db
def test_preprocess_discord_duplicate_doc_ids_skipped_second():
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
    DiscordMessage.objects.create(
        message_id=_uid(),
        channel=ch,
        author=author,
        content="y" * 80,
        message_created_at=django_timezone.now(),
    )
    DiscordMessage.objects.create(
        message_id=_uid(),
        channel=ch,
        author=author,
        content="z" * 80,
        message_created_at=django_timezone.now(),
    )

    doc = {
        "content": "a" * 80,
        "metadata": {"doc_id": "same", "type": "discord"},
    }

    with patch(
        "discord_activity_tracker.preprocessor._chain_to_document",
        return_value=doc,
    ):
        docs, _ = preprocess_discord_for_pinecone([], None)

    assert len(docs) == 1


@pytest.mark.django_db
def test_preprocess_discord_nothing_to_sync_logs(caplog):
    caplog.set_level("INFO")
    future = django_timezone.now() + timedelta(days=3650)
    docs, _ = preprocess_discord_for_pinecone([], future)
    assert docs == []
    assert "nothing to sync" in caplog.text.lower()
