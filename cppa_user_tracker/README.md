# CPPA User Tracker

## Overview

Tracks **CPPA user and GitHub account** linkage: profiles, org membership, and related metadata used elsewhere in the project. Feeds dashboards and permission-style workflows.

**Automatic user classification and identity linking are not implemented yet** — `run_cppa_user_tracker` is still a stub; profiles are created or updated by other collectors via [`services.py`](services.py).

## Data workflow

Today, **domain data is populated indirectly**: other apps call into [`services.py`](services.py) while ingesting Slack/GitHub identities. The management command remains a **stub** until merge/staging logic ships. Schema: [docs/Schema.md](../docs/Schema.md).

### Where we fetch data

**No standalone external fetch in `run_cppa_user_tracker` yet.** Identity-bearing collectors (Slack, GitHub, and so on) retrieve user records from their respective APIs and pass normalized fields into this app’s services/models.

### How data is saved to the database

When implemented, staging tables (**`TmpIdentity`**, **`TempProfileIdentityRelation`**, and related rows) will hold merge candidates; today most durable writes happen **from other apps** invoking `services.py` helpers during their own runs.

### How content is published to GitHub

**Not applicable** for the stub command. There is no Markdown or git push phase in `run_cppa_user_tracker`.

### How vectors sync to Pinecone

**Not applicable today.** The stub collector does not call `cppa_pinecone_sync`. If identity-aware search is added later, follow [docs/Pinecone_preprocess_guideline.md](../docs/Pinecone_preprocess_guideline.md) and wire a preprocessor plus `run_cppa_pinecone_sync`.

## Common tasks

- Run the tracker: `python manage.py run_cppa_user_tracker --help`.
- If you see missing tables locally, run migrations (root [README](../README.md#initial-setup)).

## Main command: `run_cppa_user_tracker`

Runs the identity/profile staging pipeline (**collector stub today**—see `management/commands/run_cppa_user_tracker.py`). No app-specific CLI flags beyond Django’s defaults (`--verbosity`, etc.); Pinecone and GitHub publish hooks are **not** active until real collect logic lands.

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
