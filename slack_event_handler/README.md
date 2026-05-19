# Slack Event Handler

## Overview

Django app that runs a **Slack Socket Mode** listener during **`runserver`** so inbound Slack events can be handled in-process. Production-style deployments typically use a different entrypoint; see module docstrings in [`runner.py`](runner.py) and [`apps.py`](apps.py) for startup behavior.

## Common tasks

- Local dev with events: `python manage.py runserver` (listener starts in the reloader child only).
- Run the collector-style command directly: `python manage.py run_slack_event_handler --help`.
- Cross-cutting docs: [docs/service_api/README.md](../docs/service_api/README.md) (per-app service API index).

## Main command: `run_slack_event_handler`

Starts the unified **Socket Mode** listener (huddle AI note / transcript tracking and Slack PR-comment bot). Requires Slack app tokens configured in Django settings (see command module and `core.operations.slack_ops`).

| Option | Description |
| --- | --- |
| `--dry-run` | Validate `SLACK_BOT_TOKEN_<id>` / `SLACK_APP_TOKEN_<id>` per configured team; **do not** start the listener. |

## Management commands

| Command | Purpose |
| --- | --- |
| `run_slack_event_handler` | Long-running Slack event handling entrypoint (see module docstring and `--help`). |

Run `python manage.py COMMAND --help` for options.

## Tests

```bash
python -m pytest slack_event_handler/tests/ -v
```

(from repo root; see root [README](../README.md#running-tests) for `DATABASE_URL` and prerequisites.)
