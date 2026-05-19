# Boost Collector Runner

## Overview

YAML-driven **orchestration** for collector commands: loads [`config/boost_collector_schedule.yaml`](../config/boost_collector_schedule.yaml) and runs the right `manage.py` commands on a schedule (typically via **Celery Beat** + worker). This is the glue between “what runs daily/hourly” and individual tracker apps.

## Data workflow

For end-to-end ingest and vector search, see [docs/Architecture_data_flow.md](../docs/Architecture_data_flow.md). This app only **orchestrates** other commands; it does not call external APIs or own database tables.

### Where we fetch data

**Not applicable at this layer.** `run_scheduled_collectors` reads [`config/boost_collector_schedule.yaml`](../config/boost_collector_schedule.yaml) and invokes the listed `manage.py` commands. Each target app performs its own fetches (GitHub, Slack, Discord, mailing lists, YouTube, and so on).

### How data is saved to the database

**Not applicable at this layer.** Persistence happens inside the collector commands this runner starts (PostgreSQL via each app’s models, plus workspace files under `WORKSPACE_DIR` where those collectors write raw or intermediate data).

### How content is published to GitHub

**Not applicable at this layer.** Git commits, uploads, or dashboard publishes are implemented inside the invoked collector apps (for example `run_boost_github_activity_tracker` or `run_boost_library_usage_dashboard`), not in `boost_collector_runner`.

### How vectors sync to Pinecone

**Not applicable at this layer.** When the schedule includes a task that runs Pinecone sync (directly or as a phase of another collector), that logic lives in `cppa_pinecone_sync` or in the specific tracker command.

## Common tasks

- Run a schedule group once (smoke test): `python manage.py run_scheduled_collectors --schedule daily --group github` (see root [README](../README.md)).
- Change what runs when: edit the YAML schedule and redeploy; keep command names in sync with each app’s `management/commands/`.

## Main command: `run_scheduled_collectors`

Runs collector tasks from [`config/boost_collector_schedule.yaml`](../config/boost_collector_schedule.yaml) for the selected schedule type. Exits with status **0** only when all invoked collectors succeed (see `--stop-on-failure`).

| Option | Description |
| --- | --- |
| `--schedule` | **Required.** `daily` \| `weekly` \| `monthly` \| `on_release` \| `interval` \| `default`. `default` runs daily + weekly (today) + monthly (today) + on_release when applicable; **`default` requires `--group`**. |
| `--day-of-week` | For `weekly`: weekday name (e.g. `monday`). **Required** when `--schedule weekly`. |
| `--day-of-month` | For `monthly`: day 1–31. **Required** when `--schedule monthly`. |
| `--interval-minutes` | For `interval`: repeat every *N* minutes (1–180). **Required** when `--schedule interval`. |
| `--group` | Run only tasks in this YAML group. Applies to all schedule kinds; **required** with `--schedule default`. |
| `--stop-on-failure` | Stop after the first failing collector instead of continuing. |

## Package

- **Django app label:** `boost_collector_runner`
- **Path (from repo root):** `boost_collector_runner/`
- **Registration:** Listed under `INSTALLED_APPS` in [`config/settings.py`](../config/settings.py) as `boost_collector_runner`.

## Management commands

| Command | Description |
| --- | --- |
| `run_scheduled_collectors` | Run collectors from config/boost_collector_schedule.yaml for a given schedule (daily, weekly, monthly, interval, on_release). |

Run `python manage.py <command> --help` for options.

## Tests

Typical invocation (from repo root, after [README prerequisites](../README.md#running-tests)):

```bash
python -m pytest boost_collector_runner/tests/ -v
```
