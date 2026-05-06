# discord_activity_tracker.services

**Module path:** `discord_activity_tracker.services`
**Description:** Discord servers, channels, messages, and reactions. Single place for all writes to discord_activity_tracker models. Discord user profiles live in `cppa_user_tracker.DiscordProfile`.

**Type notation:** Model types refer to `discord_activity_tracker.models` unless noted. `DiscordProfile` refers to `cppa_user_tracker.models.DiscordProfile`.

---

## DiscordServer

| Function                      | Parameter types                                                    | Return type                  | Description                                                       |
| ----------------------------- | ------------------------------------------------------------------ | ---------------------------- | ----------------------------------------------------------------- |
| `get_or_create_discord_server` | `server_id: int`, `server_name: str`, `icon_url: str = ""`        | `tuple[DiscordServer, bool]` | Get or create server; update name/icon if changed.               |

---

## DiscordChannel

New fields (migration `0005`): `category_id: BigIntegerField | null`, `category_name: CharField`.

| Function                        | Parameter types                                                                                                                                          | Return type                    | Description                                                               |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ | ------------------------------------------------------------------------- |
| `get_or_create_discord_channel` | `server: DiscordServer`, `channel_id: int`, `channel_name: str`, `channel_type: str`, `topic: str = ""`, `position: int = 0`, `category_id: int \| None = None`, `category_name: str = ""` | `tuple[DiscordChannel, bool]`  | Get or create channel; update all fields (incl. category) if changed.    |
| `update_channel_last_activity`  | `channel: DiscordChannel`, `last_activity_at: datetime`                                                                                                  | `DiscordChannel`               | Update `last_activity_at`.                                                |
| `update_channel_last_synced`    | `channel: DiscordChannel`, `timestamp: datetime \| None = None`                                                                                          | `DiscordChannel`               | Update `last_synced_at` (defaults to now).                               |

---

## DiscordMessage

New fields (migration `0005`): `message_type: CharField` (default `"Default"`), `is_pinned: BooleanField` (default `False`).

| Function                           | Parameter types                                                                                                                                                                                                                           | Return type                    | Description                    |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ | ------------------------------ |
| `create_or_update_discord_message` | `message_id: int`, `channel: DiscordChannel`, `author: DiscordProfile`, `content: str`, `message_created_at: datetime`, `message_edited_at: datetime \| None = None`, `reply_to_message_id: int \| None = None`, `attachment_urls: list \| None = None`, `message_type: str = "Default"`, `is_pinned: bool = False` | `tuple[DiscordMessage, bool]`  | Create or update message.      |
| `mark_message_deleted`             | `message: DiscordMessage`, `deleted_at: datetime \| None = None`                                                                                                                                                                          | `DiscordMessage`               | Mark message as deleted.       |

---

## DiscordReaction

| Function                 | Parameter types                                        | Return type                     | Description              |
| ------------------------ | ------------------------------------------------------ | ------------------------------- | ------------------------ |
| `add_or_update_reaction` | `message: DiscordMessage`, `emoji: str`, `count: int`  | `tuple[DiscordReaction, bool]`  | Add or update reaction.  |

---

## Bulk operations

All bulk functions use `bulk_create(update_conflicts=True)` for efficient upserts and accept a list of pre-normalised message dicts (as produced by `sync.messages._prepare_message_data` or `sync.chat_exporter.convert_exporter_message_to_dict`).

| Function                      | Parameter types                                               | Return type | Description                                                                                     |
| ----------------------------- | ------------------------------------------------------------- | ----------- | ----------------------------------------------------------------------------------------------- |
| `bulk_upsert_discord_users`   | `user_data_list: list[dict]`                                  | `dict`      | Upsert `DiscordProfile` rows; returns `{user_id: profile}` map.                               |
| `bulk_upsert_discord_messages` | `message_data_list: list[dict]`, `channel: DiscordChannel`   | `dict`      | Upsert `DiscordMessage` rows incl. `message_type` and `is_pinned`; returns `{message_id: msg}`. |
| `bulk_upsert_discord_reactions` | `reaction_data_list: list[dict]`, `message_map: dict`       | `None`      | Upsert `DiscordReaction` rows.                                                                  |
| `bulk_process_message_batch`  | `channel: DiscordChannel`, `messages: list[dict]`            | `int`       | Orchestrates user upsert → message upsert → reaction upsert; returns number of messages upserted. |

---

## Query helpers

| Function              | Parameter types                                                    | Return type | Description                                         |
| --------------------- | ------------------------------------------------------------------ | ----------- | --------------------------------------------------- |
| `get_active_channels` | `server: DiscordServer`, `days: int = 30`, `channel_ids: list[int] \| None = None` | `QuerySet`  | Channels with activity in last N days, optionally filtered by `channel_ids` allowlist. |

---

## Ingestion commands

Two management commands handle message ingestion. Both follow the `CollectorBase` pattern with four phases: **fetch → db_sync → save_raw → pinecone_sync**.

### `run_discord_activity_tracker` — incremental / scheduled

Uses `DiscordChatExporter` CLI with the user token. Fetches into a staging directory, persists to the database, then archives JSON under:

`{WORKSPACE_DIR}/raw/discord_activity_tracker/<server_id>/<channel_id>/`

Date bounds passed to the exporter use **UTC** (see `sync/chat_exporter.py`). When `--since` is omitted, the lower bound is the latest stored message time for this guild (and channel allowlist). If the database has no matching rows, no `--after` filter is applied (full history). When `--until` is omitted, there is no upper bound (export through the present).

```
python manage.py run_discord_activity_tracker [options]

Options:
  --dry-run                 No fetch, export, push, or Pinecone writes; log plan
  --skip-discord-sync       Skip DiscordChatExporter, DB upserts, and raw JSON
  --skip-markdown-export    Skip writing Markdown from DB to DISCORD_CONTEXT_REPO_PATH
  --skip-remote-push        Skip git commit/push after export (see DISCORD_CONTEXT_AUTO_COMMIT)
  --skip-pinecone           Skip run_cppa_pinecone_sync (alias: --ignore-pinecone)
  --since, --until          ISO or YYYY-MM-DD window (UTC; aliases: --from-date, --to-date, --start-time, --end-time). Omit `--since` to continue from latest DB message; omit `--until` for no upper bound.
  --channels IDS            Comma-separated channel ID override
  --task {sync,export,all}  Deprecated: maps to the skip flags (prefer --skip-*)
```

### `backfill_discord_activity_tracker` — full history

Exports an explicit date range for one-off or recovery imports.

```
python manage.py backfill_discord_activity_tracker [--start-date YYYY-MM-DD] [options]

Options:
  --start-date YYYY-MM-DD  Backfill start date (UTC); omit to use latest stored message time
  --end-date YYYY-MM-DD    Backfill end date (default: open-ended / today per exporter)
  --channels IDS           Comma-separated channel ID override
  --skip-pinecone          Skip Pinecone sync (alias: --ignore-pinecone)
  --dry-run                Preview only
```

### Channel allowlist

Both commands respect `DISCORD_CHANNEL_IDS` in `settings.py` (populated from the `DISCORD_CHANNEL_IDS` env var, comma-separated snowflake IDs). The `--channels` CLI argument overrides the setting for a single run.

---

## Pinecone integration

`discord_activity_tracker/preprocessor.py` exposes `preprocess_discord_for_pinecone(failed_ids, final_sync_at)` which:

1. Queries `DiscordMessage` rows (new since `final_sync_at`, plus any `failed_ids` retry).
2. Groups messages into reply chains (`reply_to_message_id` linking).
3. Filters documents with fewer than `PINECONE_MIN_TEXT_LENGTH` (default 20) characters.
4. Emits `{"content": str, "metadata": {...}}` dicts with metadata keys: `doc_id`, `type`, `channel_id`, `channel_name`, `server_id`, `author`, `timestamp`, `is_reply_chain`, `source_ids`.

Settings:

| Setting                       | Default             | Description                              |
| ----------------------------- | ------------------- | ---------------------------------------- |
| `PINECONE_DISCORD_APP_TYPE`   | (empty skips sync) | Passed to `run_cppa_pinecone_sync` as `--app-type`. If unset/empty, Pinecone sync is skipped. |
| `PINECONE_DISCORD_NAMESPACE`  | (empty skips sync) | Pinecone namespace. If unset/empty, Pinecone sync is skipped.  |

---

## Related

- [Service API index](README.md)
- [Contributing](../Contributing.md)
- [Schema](../Schema.md)
- [Workspace](../Workspace.md) – raw export JSON in `{WORKSPACE_DIR}/raw/discord_activity_tracker/<server_id>/<channel_id>/`
