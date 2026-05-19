# Core

## Overview

Shared infrastructure for collectors and cross-cutting utilities. Tracker apps import from here; this package is **not** where app-specific database writes live (use each app’s `services.py`).

| Area | Path | Documentation |
| --- | --- | --- |
| Collector bases | [`collectors/`](collectors/) | [collectors/README.md](collectors/README.md) |
| External I/O | [`operations/`](operations/) | [operations/README.md](operations/README.md) — see also [github_ops](operations/github_ops/README.md), [slack_ops](operations/slack_ops/README.md), [md_ops](operations/md_ops/README.md), [file_ops](operations/file_ops/README.md) |
| Helpers | [`utils/`](utils/) | [utils/README.md](utils/README.md) |
| Tests | [`tests/`](tests/) | _(no README — run pytest below)_ |
| Management commands | [`management/commands/`](management/commands/) | [Management commands](#management-commands) (this file) |

**Top-level modules** (no subfolder): [`errors.py`](errors.py) (`classify_failure`), [`protocols.py`](protocols.py) (portable DTO protocols), [`workspace_orphans.py`](workspace_orphans.py) (workspace cleanup helpers). [`models.py`](models.py) is intentionally empty.

Other folders: [`migrations/`](migrations/) (no models today), [`pyright_samples/`](pyright_samples/) (protocol typing samples for Pyright, not runtime tests).

Long-form operations design: [docs/operations/](../docs/operations/README.md).

## Common tasks

- Add or change a collector: [docs/How_to_add_a_collector.md](../docs/How_to_add_a_collector.md); subclass `AbstractCollector` / use `BaseCollectorCommand` from [`collectors/`](collectors/).
- List cross-app imports (refactors): `python scripts/list_cross_app_imports.py`.

## `run_*` commands

**`core`** does not define a `run_core_*` collector. Shared collector helpers live under [`collectors/`](collectors/) and are used from each app’s `run_*` command (see app READMEs).

## Management commands

Project-wide maintenance commands in [`management/commands/`](management/commands/). Run `python manage.py <command> --help` for full options.

| Command | Description |
| --- | --- |
| `cleanup_workspace_orphans` | List or remove stale files under `WORKSPACE_DIR` (temp suffixes; optional GitHub JSON cache cleanup). |
| `send_startup_notification` | Post deploy/startup status to Slack and Discord (DB, Celery beat schedule, workers). |

### `cleanup_workspace_orphans`

Scans `WORKSPACE_DIR` for orphan artifacts (`*.tmp`, `*.part`, `*.lock`, `*.swp`) and, optionally, invalid or empty JSON under `github_activity_tracker/.../{commits,issues,prs}/`. Uses helpers in [`workspace_orphans.py`](workspace_orphans.py).

| Option | Description |
| --- | --- |
| `--max-age-hours` | Suffix scan: only delete files older than this many hours (default **24**). |
| `--execute` | Actually delete matches (default is list-only). |
| `--github-json-cache` | Also clean invalid/empty GitHub activity JSON cache files. |

### `send_startup_notification`

Posts deploy/startup status to configured Slack/Discord webhooks. Typically invoked after health checks: `DEPLOY_BRANCH=<branch> make notify`. No custom flags beyond Django’s standard `--verbosity` / traceback options.

## Package

- **Django app label:** `core`
- **Path (from repo root):** `core/`
- **Registration:** Listed under `INSTALLED_APPS` in [`config/settings.py`](../config/settings.py) as `core`.

## Tests

```bash
python -m pytest core/tests/ -v
```

Test layout under [`tests/`](tests/):

| Path | Covers |
| --- | --- |
| [`tests/github_ops/`](tests/github_ops/) | `core.operations.github_ops` |
| [`tests/operations/`](tests/operations/) | Slack, markdown, GitHub export ops |
| `tests/test_*.py` | `errors`, `protocols`, `utils`, workspace orphans, admin, collectors |

(from repo root; see root [README](../README.md#running-tests).)
