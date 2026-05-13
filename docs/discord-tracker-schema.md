# Discord activity tracker — staging JSON schema

This document describes the JSON shapes used when Discord data is staged on disk or normalized immediately before database writes in `discord_activity_tracker`. Runtime validation is implemented with **Pydantic** in [`discord_activity_tracker/staging_schema.py`](../discord_activity_tracker/staging_schema.py) (`validate_envelope`, `validate_normalized_message`).

## 1. Envelope (DiscordChatExporter file)

A single exported channel file is one JSON object with three top-level keys:

| Key | Type | Description |
| --- | --- | --- |
| `guild` | object | Guild metadata from DiscordChatExporter. |
| `channel` | object | Channel metadata. |
| `messages` | array | Message objects in export order. |

Common **guild** keys (camelCase as emitted by the exporter; `extra` fields are allowed and ignored by validation):

- `id` — guild snowflake (string or number in JSON).
- `name` — guild name.
- `iconUrl` — optional guild icon URL.

Common **channel** keys:

- `id`, `name`, `type`, `topic`, `category`, `categoryId` — as provided by the exporter.

**Normalization contract:** After `json.load`, ingestion validates the envelope with `validate_envelope`, then converts each raw message with `convert_exporter_message_to_dict` in [`discord_activity_tracker/sync/chat_exporter.py`](../discord_activity_tracker/sync/chat_exporter.py) before bulk DB upsert.

## 2. Normalized message record

The dict returned by `convert_exporter_message_to_dict` (and consumed by `_prepare_message_data` in [`discord_activity_tracker/sync/messages.py`](../discord_activity_tracker/sync/messages.py), which **drops unknown keys** before ORM bulk write) uses **snake_case** for nested author fields aligned with the Discord bot API shape.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | integer | Message snowflake. |
| `content` | string | Message body; may be empty. |
| `created_at` | string | ISO 8601 timestamp (from exporter `timestamp`). Required non-empty for validation. |
| `edited_at` | string or null | ISO 8601 if edited; otherwise JSON `null` or omitted when absent. |
| `message_type` | string | Exporter/API `type` string (e.g. `Default`, `Reply`). **Opaque passthrough** — see [Limitations](#6-limitations--out-of-scope). |
| `is_pinned` | boolean | |
| `author` | object | `id`, `username`, `global_name`, `avatar_url`, `bot`. |
| `attachments` | array | Objects with optional `url`. |
| `reactions` | array | Only entries with a non-empty resolved emoji; `{ "emoji": string, "count": integer >= 0 }`. |
| `reference` | object or null | When present: `{ "message_id": integer or null }`. |

### Canonical cross-tracker fields (additive)

These are set by `convert_exporter_message_to_dict` when enough context exists. They are **not** persisted as separate ORM columns; they exist on the normalized dict for validation, logs, and downstream consumers.

| Field | Type | When set |
| --- | --- | --- |
| `occurred_at` | string | ISO 8601 instant in UTC with `Z` suffix, from `created_at` when non-empty (implementation: `core.utils.datetime_parsing.format_instant_iso_z`). |
| `actor_id` | string | Discord user snowflake as decimal string when author `id` is non-zero. |
| `source_url` | string | When `server_id` and `channel_id` are passed into the converter and message id is non-zero: `https://discord.com/channels/{server}/{channel}/{message}` via `format_discord_url`. |

### Null vs omitted

- Prefer JSON **`null`** for nullable scalars when serializing (e.g. `edited_at`, `reference`) to match common REST-style workspace files elsewhere in the monorepo.
- Omit optional keys when the exporter does not provide them (e.g. `edited_at` absent vs `null`).

## 3. Reactions

Each reaction in the normalized message:

- `emoji` — non-empty string (custom emoji name or Unicode).
- `count` — integer `>= 0`.

Exporter rows with no resolvable emoji are **dropped** during conversion (they are not stored).

## 4. `message_type`

Treated as an **opaque string** from DiscordChatExporter or the Discord API. The app stores it on `DiscordMessage.message_type` without interpreting join/leave semantics from this field alone. See [Limitations](#6-limitations--out-of-scope).

## 5. Channel activity summary (derived)

Not materialized as a separate JSON file in this iteration. For a given export envelope, a logical summary can be computed as:

- `server_id` / `channel_id` from `guild.id` / `channel.id`.
- `message_count` — `len(messages)`.
- `first_message_at` / `last_message_at` — from the first and last message `timestamp` / `created_at` after conversion, in UTC, if messages are non-empty.

## 6. Limitations / out of scope

The collector’s primary path fetches **per-channel** message history (DiscordChatExporter export or bot API sync). Therefore:

- **`message_type` is not a membership lifecycle log.** System or non-default types may appear when the exporter includes them, but rows are **not** a complete or authoritative log of users joining or leaving the **server** or a **channel**.
- **Single-channel export/fetch** cannot infer server-wide join/leave; Discord does not guarantee join system messages appear in every text channel, and leaves often have no built-in chat message. Authoritative membership tracking would require gateway events, audit log (where permitted), multi-channel export including the guild system channel, or dedicated bot logging — outside the current design.

Do not document join/leave **detection** as a capability of this schema.

## 7. JSON Schema artifact vs runtime validation

The committed file [`discord_activity_tracker/schemas/discord_staging_v1.json`](../discord_activity_tracker/schemas/discord_staging_v1.json) is an **optional** JSON document for reviewers who prefer raw [JSON Schema](https://json-schema.org/). It bundles `model_json_schema()` output for:

- `DiscordChatExporterEnvelope`
- `NormalizedDiscordMessage`

**Single source of truth at runtime:** the Pydantic models in [`discord_activity_tracker/staging_schema.py`](../discord_activity_tracker/staging_schema.py). The `.json` file can **drift** if models change and the file is not regenerated.

**Regenerate** (from repository root, with `discord_activity_tracker` importable, e.g. `PYTHONPATH=.`):

```bash
python -m discord_activity_tracker.scripts.write_staging_json_schema
```

or:

```bash
python -c "from discord_activity_tracker.staging_schema import write_staging_json_schema; write_staging_json_schema()"
```

## Alignment with other trackers (conventions)

| Concern | `github_activity_tracker` | `cppa_slack_tracker` | `discord_activity_tracker` (this doc) |
| --- | --- | --- | --- |
| Workspace layout | Per-owner/repo trees; JSON per commit/issue/PR under [`github_activity_tracker/workspace.py`](../github_activity_tracker/workspace.py). | Per team/channel; daily `YYYY-MM-DD.json`; iterators **sorted** by path. | Per-server under `workspace/discord_activity_tracker/`; raw archive under `WORKSPACE_DIR/raw/discord_activity_tracker/`; `iter_existing_message_jsons` yields **sorted** paths. |
| Field naming | Mostly GitHub REST / snake_case in cached JSON. | Slack API native keys in daily lists (`ts`, `text`, `user`, …). | Exporter camelCase in file → **normalized** snake_case + ISO timestamps on message dict. |
| Links | e.g. `html_url` on GitHub entities. | Slack permalinks vary by payload. | Canonical `source_url` on normalized message when guild/channel ids are known. |

### Shared conceptual fields (mapping)

| Concept | Discord (normalized dict) | Slack (workspace message) | GitHub (example) |
| --- | --- | --- | --- |
| When | `created_at`, `occurred_at` | `ts` (Unix fractional string) | `created_at`, `commit.author.date`, … |
| Actor | `author.id` + `actor_id` string | `user` | `author.login`, `user.login`, … |
| Body | `content` | `text` | `body`, commit `message`, … |
| Link | `source_url` | (construct from team/channel/ts) | `html_url` |

Discord ingestion keeps legacy keys (`created_at`, `id`, …) for `_prepare_message_data` compatibility and adds **parallel** canonical fields above rather than renaming bulk keys.
