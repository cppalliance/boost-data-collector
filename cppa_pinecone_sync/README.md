# CPPA Pinecone Sync

## Overview

Syncs preprocessed documents into **Pinecone** for search/RAG flows. The management command expects an **app type**, **namespace**, and **preprocessor dotted path**—see the command docstring for the exact contract and usage examples.

## Data workflow

This app is the **shared vector upsert pipeline**. Other collectors populate PostgreSQL (and sometimes the workspace); they call `sync_to_pinecone()` or schedule `run_cppa_pinecone_sync`. Background: [docs/Architecture_data_flow.md](../docs/Architecture_data_flow.md), preprocessor contract: [docs/Pinecone_preprocess_guideline.md](../docs/Pinecone_preprocess_guideline.md).

### Where we fetch data

**Upstream sources vary by caller.** This app does not scrape GitHub or Slack itself. It loads **sync state** from its own Django models (`PineconeSyncStatus`, `PineconeFailList`), then runs the registered **preprocessor** (Python import path you pass in), which reads the relevant rows and/or files for that `app_type` and builds document payloads for embedding and upsert.

### How data is saved to the database

The sync run **updates** `cppa_pinecone_sync` tables: last-success timestamps, retry metadata, and failed vector IDs—so the next run can resume safely. It does **not** replace other apps’ domain tables; those remain the system of record for messages, issues, docs, and so on.

### How content is published to GitHub

**Not applicable.** This app only talks to the Pinecone API (and the embedding path configured for sync). Markdown or git pushes belong to other apps.

### How vectors sync to Pinecone

`run_cppa_pinecone_sync` (or a direct `sync_to_pinecone()` call) **embeds and upserts** vectors into the given **namespace**, using the **public** or **private** Pinecone credentials from Django settings (`--pinecone-instance`). Failed chunks are recorded for retry; successful runs advance sync status.

## Common tasks

- Single sync invocation (three required args): `python manage.py run_cppa_pinecone_sync --help`
- Wire new namespaces from other apps via their preprocessors (see [docs/Architecture_data_flow.md](../docs/Architecture_data_flow.md)).

## Main command: `run_cppa_pinecone_sync`

Runs `sync_to_pinecone` for **one** preprocessor + namespace. **`--app-type`, `--namespace`, and `--preprocessor` are required together** (validated in the command).

| Option | Description |
| --- | --- |
| `--app-type` | Logical source id (e.g. mailing-list app type string). |
| `--namespace` | Pinecone namespace to upsert into. |
| `--preprocessor` | Dotted import path to the preprocess callable (e.g. `myapp.preprocessors.foo`). |
| `--pinecone-instance` | `public` (default) or `private` — selects which Pinecone API credentials to use. |

## Package

- **Django app label:** `cppa_pinecone_sync`
- **Path (from repo root):** `cppa_pinecone_sync/`
- **Registration:** Listed under `INSTALLED_APPS` in [`config/settings.py`](../config/settings.py) as `cppa_pinecone_sync`.

## Management commands

| Command | Description |
| --- | --- |
| `run_cppa_pinecone_sync` | Management command: run_cppa_pinecone_sync |

Run `python manage.py <command> --help` for options.

## Tests

Typical invocation (from repo root, after [README prerequisites](../README.md#running-tests)):

```bash
python -m pytest cppa_pinecone_sync/tests/ -v
```
