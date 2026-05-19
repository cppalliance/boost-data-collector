# Boost Usage Tracker

## Overview

Collects **Boost library usage signals** (e.g. repository metadata tied to Boost) and runs periodic **database update** commands. Commands split between the main tracker run and smaller `run_update_*` jobs.

## Common tasks

- Full tracker: `python manage.py run_boost_usage_tracker --help`
- DB refresh helpers: `run_update_db`, `run_update_created_repos_by_language` (see the **Management commands** section below).

## Main command: `run_boost_usage_tracker`

Runs **monitor_content** (repo/content signals) and/or **monitor_stars** (monthly star counts) inside one collector invocation unless `--task` narrows it.

| Option | Description |
| --- | --- |
| `--task` | `monitor_content` \| `monitor_stars` — run only that task. **Default:** both, in order (`monitor_content` then `monitor_stars`). |
| `--since` | `YYYY-MM-DD` lower bound for `monitor_content` (default: **yesterday**). |
| `--until` | `YYYY-MM-DD` upper bound for `monitor_content` (default: **today**). |
| `--min-stars` | Minimum stars filter for `monitor_stars` (default **10**). |
| `--dry-run` | Log actions only; no DB changes. |

## Package

- **Django app label:** `boost_usage_tracker`
- **Path (from repo root):** `boost_usage_tracker/`
- **Registration:** Listed under `INSTALLED_APPS` in [`config/settings.py`](../config/settings.py) as `boost_usage_tracker`.

## Management commands

| Command | Description |
| --- | --- |
| `run_boost_usage_tracker` | Management command: run_boost_usage_tracker |
| `run_update_created_repos_by_language` | Management command: run_update_created_repos_by_language |
| `run_update_db` | Management command: run_update_db |

Run `python manage.py <command> --help` for options.

## Tests

Typical invocation (from repo root, after [README prerequisites](../README.md#running-tests)):

```bash
python -m pytest boost_usage_tracker/tests/ -v
```
