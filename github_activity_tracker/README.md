# GitHub Activity Tracker

## Overview

Collects **GitHub activity** (commits, issues, PRs, files) for configured repositories into PostgreSQL and uses the shared **`workspace/`** tree for raw JSON before ingestion. Behavior is sensitive to **rate limits**, **multiple GitHub tokens**, and **workspace layout**—see [docs/Workspace.md](../docs/Workspace.md) and [docs/operations/github.md](../docs/operations/github.md).

## Common tasks

- After changing workspace paths or repo list: review migrations and maintenance commands under `management/commands/` (layout migrations, backfills).
- Token setup: `GITHUB_TOKEN`, `GITHUB_TOKENS_SCRAPING`, `GITHUB_TOKEN_WRITE` in `.env` (see root README **GitHub tokens**).

## Main commands in this app

This package does **not** ship a `run_github_*` collector command—routine GitHub sync for Boost flows through **`run_boost_github_activity_tracker`** in [`boost_library_tracker`](../boost_library_tracker/README.md). The commands below are **maintenance** utilities shipped with `github_activity_tracker`.

### `migrate_workspace_layout`

Rewrites files under `WORKSPACE_DIR/github_activity_tracker/` from the legacy tree (`<owner>/commits/<repo>/…`) into `<owner>/<repo>/commits|issues|prs/`.

| Option | Description |
| --- | --- |
| `--dry-run` | Print planned moves only; do not modify files. |

### `backfill_300_file_commits`

Finds commits with exactly **300** file-change rows (GitHub API truncation), refetches full file lists via git, and updates the DB.

| Option | Description |
| --- | --- |
| `--dry-run` | List commits that would update; no DB writes. |
| `--limit` | Process at most **N** commits (`0` = no limit). |

## Package

- **Django app label:** `github_activity_tracker`
- **Path (from repo root):** `github_activity_tracker/`
- **Registration:** Listed under `INSTALLED_APPS` in [`config/settings.py`](../config/settings.py) as `github_activity_tracker`.

## Management commands

| Command | Description |
| --- | --- |
| `backfill_300_file_commits` | Backfill commits that have exactly 300 file changes (API truncation). |
| `migrate_workspace_layout` | Migrate workspace/github_activity_tracker from the legacy layout to the app layout. |

Run `python manage.py <command> --help` for options.

## Tests

Typical invocation (from repo root, after [README prerequisites](../README.md#running-tests)):

```bash
python -m pytest github_activity_tracker/tests/ -v
```
