# CPPA User Tracker

## Overview

Tracks **CPPA user and GitHub account** linkage: profiles, org membership, and related metadata used elsewhere in the project. Feeds dashboards and permission-style workflows.

**Automatic user classification and identity linking are not implemented yet** — `run_cppa_user_tracker` is still a stub; profiles are created or updated by other collectors via [`services.py`](services.py).

## Common tasks

- Run the tracker: `python manage.py run_cppa_user_tracker --help`.
- If you see missing tables locally, run migrations (root [README](../README.md#initial-setup)).

## Main command: `run_cppa_user_tracker`

Runs the identity/profile staging pipeline (collector stub today—see `management/commands/run_cppa_user_tracker.py`). Uses the standard collector **run** then **Pinecone** phase hooks from `BaseCollectorCommand`; no app-specific CLI flags beyond Django’s defaults (`--verbosity`, etc.).

| Option | Description |
| --- | --- |
| _(none)_ | No custom arguments; behavior is fixed in code until staging/merge logic grows flags. |

## Management commands

| Command | Purpose |
| --- | --- |
| `run_cppa_user_tracker` | Primary scheduled collector for user/GitHub data. |

Run `python manage.py COMMAND --help` for options.

## Tests

```bash
python -m pytest cppa_user_tracker/tests/ -v
```

(from repo root; see root [README](../README.md#running-tests).)
