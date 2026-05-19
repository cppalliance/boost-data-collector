# Boost Mailing List Tracker

## Overview

Tracks **Boost mailing list** activity (messages, threads, archives) into the database for dashboards and search. Runs as a standard collector app behind Celery / `run_scheduled_collectors`.

## Common tasks

- Run the tracker: `python manage.py run_boost_mailing_list_tracker --help`.
- Scheduling: [docs/Workflow.md](../docs/Workflow.md) and [`config/boost_collector_schedule.yaml`](../config/boost_collector_schedule.yaml).

## Main command: `run_boost_mailing_list_tracker`

Processes existing workspace JSONs (persist → delete), then fetches new mail from the API (write JSON → persist → remove). Optional Pinecone step uses `run_cppa_pinecone_sync` with the configured app type/namespace.

| Option | Description |
| --- | --- |
| `--start-date` | Fetch lower bound (ISO date, e.g. `2025-09-01`). Default: no lower bound (fetch all). |
| `--end-date` | Fetch upper bound (ISO). Default: no upper bound. |
| `--dry-run` | Fetch and report counts only; no DB or workspace writes. |
| `--pinecone-app-type` | Passed to `run_cppa_pinecone_sync`; default from `BOOST_MAILING_LIST_PINECONE_APP_TYPE`. |
| `--pinecone-namespace` | Pinecone namespace; default from `BOOST_MAILING_LIST_PINECONE_NAMESPACE`. |

## Management commands

| Command | Purpose |
| --- | --- |
| `run_boost_mailing_list_tracker` | Primary scheduled collector for mailing list ingestion. |

Run `python manage.py COMMAND --help` for options.

## Tests

```bash
python -m pytest boost_mailing_list_tracker/tests/ -v
```

(from repo root; see root [README](../README.md#running-tests).)
