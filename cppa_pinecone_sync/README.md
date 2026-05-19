# CPPA Pinecone Sync

## Overview

Syncs preprocessed documents into **Pinecone** for search/RAG flows. The management command expects an **app type**, **namespace**, and **preprocessor dotted path**—see the command docstring for the exact contract and usage examples.

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
