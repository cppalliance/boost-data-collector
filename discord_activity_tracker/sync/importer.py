"""Import DiscordChatExporter JSON payloads into the database (shared by exporter + backfill)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from asgiref.sync import sync_to_async

from discord_activity_tracker.services import (
    get_or_create_discord_server,
    get_or_create_discord_channel,
    update_channel_last_synced,
    update_channel_last_activity,
)
from discord_activity_tracker.sync.chat_exporter import convert_exporter_message_to_dict
from discord_activity_tracker.sync.messages import _process_messages_in_batches
from discord_activity_tracker.sync.utils import parse_datetime

logger = logging.getLogger(__name__)


async def persist_exporter_channel_payloads(
    parsed_data: List[Dict[str, Any]],
    *,
    expected_guild_id: Optional[int] = None,
) -> None:
    """
    Persist parsed DiscordChatExporter channel dicts.

    Each item should have keys ``guild``, ``channel``, ``messages`` (same shape as
    ``parse_exported_json`` output). Optional ``expected_guild_id`` skips rows whose
    ``guild['id']`` does not match (logs a warning).
    """
    for channel_data in parsed_data:
        try:
            guild_info = channel_data["guild"]
            channel_info = channel_data["channel"]
            messages = channel_data["messages"]

            gid = guild_info.get("id")
            if expected_guild_id is not None and gid != expected_guild_id:
                logger.warning(
                    "Skipping JSON for guild %s (expected %s) channel %s",
                    gid,
                    expected_guild_id,
                    channel_info.get("name"),
                )
                continue

            server, _ = await sync_to_async(get_or_create_discord_server)(
                server_id=guild_info["id"],
                server_name=guild_info["name"],
                icon_url="",
            )

            channel, _ = await sync_to_async(get_or_create_discord_channel)(
                server=server,
                channel_id=channel_info["id"],
                channel_name=channel_info["name"],
                channel_type=channel_info.get("type", "text"),
                topic=channel_info.get("topic") or "",
                position=0,
            )

            converted = [convert_exporter_message_to_dict(msg) for msg in messages]

            processed = await _process_messages_in_batches(channel, converted)

            if messages:
                last_msg = convert_exporter_message_to_dict(messages[-1])
                last_time = parse_datetime(last_msg.get("created_at"))
                if last_time:
                    await sync_to_async(update_channel_last_activity)(
                        channel, last_time
                    )

            await sync_to_async(update_channel_last_synced)(channel)

            logger.info(
                "Synced #%s: %s/%s messages",
                channel.channel_name,
                processed,
                len(messages),
            )

        except Exception as e:
            ch_name = channel_data.get("channel", {}).get("name")
            logger.error("Failed to persist channel %s: %s", ch_name, e)
            continue
