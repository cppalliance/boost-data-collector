# Boost Collector Runner

## Overview

YAML-driven **orchestration** for collector commands: loads [`config/boost_collector_schedule.yaml`](../config/boost_collector_schedule.yaml) and runs the right `manage.py` commands on a schedule (typically via **Celery Beat** + worker). This is the glue between “what runs daily/hourly” and individual tracker apps.

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

## Title

**Boost Collector Runner**

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
