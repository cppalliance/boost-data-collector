# CPPA Slack Tracker

## Overview

Collects **Slack workspace data** for CPPA workflows: channels, messages, and related metadata, driven by the scheduled collector command. Shares patterns with other “run\_\*\_tracker” apps in this repo.

## Common tasks

- Run the tracker: `python manage.py run_cppa_slack_tracker --help`.
- Workspace layout: [docs/Workspace.md](../docs/Workspace.md); service API index: [docs/service_api/README.md](../docs/service_api/README.md).

## Main command: `run_cppa_slack_tracker`

Syncs Slack teams, users, channels, memberships, and messages. **Team ID** comes from `--team-id` or `SLACK_TEAM_ID` in settings. With no `--sync-*` flags, defaults to users + channels + messages (not channel memberships—pass `--sync-channel-users` for that).

| Option | Description |
| --- | --- |
| `--team-id` | Slack team ID; if omitted, uses `SLACK_TEAM_ID` from `.env` (**required** one of the two). |
| `--channel-id` | Optional channel scope; otherwise all channels in the team. |
| `--start-date` | Message sync start (`YYYY-MM-DD` or ISO). Default: continue from latest message in DB. |
| `--end-date` | Message sync end; default: today. |
| `--messages-json` | Path to JSON file or directory of legacy message payloads (loaded before API message sync). |
| `--sync-users` | Run user sync only (can combine with other `--sync-*`). |
| `--sync-channels` | Run channel list sync. |
| `--sync-channel-users` | Run channel membership sync. |
| `--sync-messages` | Run message sync only. |
| `--dry-run` | Log planned work; no DB/API changes. |
| `--ignore-pinecone` | Skip Pinecone upsert after message sync. |

## Management commands

| Command | Purpose |
| --- | --- |
| `run_cppa_slack_tracker` | Primary scheduled collector for this app. |

Run `python manage.py COMMAND --help` for options.

## Tests

```bash
python -m pytest cppa_slack_tracker/tests/ -v
```

(from repo root; see root [README](../README.md#running-tests).)
