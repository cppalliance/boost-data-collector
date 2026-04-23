"""
Pinecone preprocess for Discord messages.

See docs/Pinecone_preprocess_guideline.md
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from django.conf import settings
from discord_activity_tracker.models import DiscordMessage

logger = logging.getLogger(__name__)

# Defaults when settings omit explicit app type / namespace
APP_TYPE = "discord-together-cpp"
NAMESPACE = "discord-cplusplus"


def _normalize_failed_ids(failed_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in failed_ids or []:
        value = (raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _clean_discord_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<@!?(\d+)>", r"@user-\1", text)
    text = re.sub(r"<#(\d+)>", r"#channel-\1", text)
    text = re.sub(r"<a?:([^:>]+):\d+>", r":\1:", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _message_text(msg: DiscordMessage) -> str:
    parts = []
    if msg.author:
        who = msg.author.display_name or msg.author.username or "unknown"
        parts.append(f"@{who}")
    parts.append(_clean_discord_text(msg.content or ""))
    if msg.attachment_urls:
        parts.append(
            "Attachments: " + ", ".join(str(u) for u in msg.attachment_urls[:5])
        )
    return "\n".join(p for p in parts if p)


def preprocess_discord_for_pinecone(
    failed_ids: list[str],
    final_sync_at: datetime | None,
) -> tuple[list[dict[str, Any]], bool]:
    """
    Build Pinecone documents from DiscordMessage rows.

    Incremental sync uses ``updated_at`` vs ``final_sync_at``. Retries use PK in
    ``failed_ids``.
    """
    normalized_failed = _normalize_failed_ids(failed_ids)
    min_len = int(getattr(settings, "PINECONE_MIN_TEXT_LENGTH", 50) or 50)

    qs = DiscordMessage.objects.filter(is_deleted=False).select_related(
        "author", "channel", "channel__server"
    )

    messages_new: list[DiscordMessage] = []
    messages_failed: list[DiscordMessage] = []

    if final_sync_at is None and not normalized_failed:
        messages_new = list(qs.order_by("message_created_at"))
        logger.info(
            "Discord Pinecone preprocess: first sync, %d messages",
            len(messages_new),
        )
    else:
        if final_sync_at is not None:
            messages_new = list(
                qs.filter(updated_at__gt=final_sync_at).order_by("message_created_at")
            )
            logger.info(
                "Discord Pinecone preprocess: incremental, %d messages",
                len(messages_new),
            )
        if normalized_failed:
            pks = []
            for x in normalized_failed:
                try:
                    pks.append(int(x))
                except ValueError:
                    continue
            if pks:
                messages_failed = list(qs.filter(pk__in=pks))
                logger.info(
                    "Discord Pinecone preprocess: retry failed, %d messages",
                    len(messages_failed),
                )

    seen_pk: set[int] = set()
    docs: list[dict[str, Any]] = []
    for msg in messages_new + messages_failed:
        if msg.pk in seen_pk:
            continue
        seen_pk.add(msg.pk)
        content = _message_text(msg)
        if len(content.strip()) < min_len:
            continue
        ch = msg.channel
        server = ch.server if ch else None
        doc_id = f"discord-msg-{msg.message_id}"
        metadata: dict[str, Any] = {
            "doc_id": doc_id,
            "source_ids": str(msg.pk),
            "type": "discord",
            "channel_name": ch.channel_name if ch else "",
            "channel_id": str(ch.channel_id) if ch else "",
            "server_name": server.server_name if server else "",
            "message_id": str(msg.message_id),
        }
        docs.append({"content": content, "metadata": metadata})

    logger.info("Discord Pinecone preprocess: built %d documents", len(docs))
    return docs, False
