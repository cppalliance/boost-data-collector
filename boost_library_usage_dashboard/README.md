# Boost Library Usage Dashboard

## Overview

Maintains **usage and dashboard-oriented** data for Boost libraries (aggregates and refresh commands consumed by reporting). Command surface is small; most business rules live in services and models.

## Common tasks

- Run the tracker: `python manage.py run_boost_library_usage_dashboard --help`.
- Schema and relationships: [docs/Schema.md](../docs/Schema.md).

## Main command: `run_boost_library_usage_dashboard`

Builds metrics from PostgreSQL, renders HTML, and optionally publishes to the configured GitHub repo.

| Option | Description |
| --- | --- |
| `--skip-collect` | Skip PostgreSQL collection + Markdown report generation. |
| `--skip-render` | Skip HTML rendering. |
| `--skip-publish` | Skip push to GitHub. |
| `--owner` | Publish repo owner (overrides `BOOST_LIBRARY_USAGE_DASHBOARD_PUBLISH_OWNER`). |
| `--repo` | Publish repo name (overrides `BOOST_LIBRARY_USAGE_DASHBOARD_PUBLISH_REPO`). |
| `--branch` | Publish branch (overrides `BOOST_LIBRARY_USAGE_DASHBOARD_PUBLISH_BRANCH`; default `main`). |

## Management commands

| Command | Purpose |
| --- | --- |
| `run_boost_library_usage_dashboard` | Primary scheduled job for this app. |

Run `python manage.py COMMAND --help` for options.

## Tests

```bash
python -m pytest boost_library_usage_dashboard/tests/ -v
```

(from repo root; see root [README](../README.md#running-tests).)
