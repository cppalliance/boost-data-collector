# WG21 Paper Tracker

## Overview

Tracks **ISO C++ committee (WG21) mailing** paper metadata: fetch pipeline, DB updates, and optional **GitHub `repository_dispatch`** for downstream automation. Collector logic lives in [`collectors.py`](collectors.py) and the pipeline module.

## Data workflow

`run_wg21_paper_tracker` scrapes or imports committee mailings into PostgreSQL, then can signal automation hosts via **GitHub’s repository_dispatch** API when configured—distinct from publishing Markdown repos.

### Where we fetch data

**WG21 mailing archives / metadata endpoints** (HTTP) for the configured month window (`--from-date` / `--to-date`). CSV imports via `import_wg21_metadata_from_csv` read **local files** instead of the network.

### How data is saved to the database

Papers, revisions, authors, and mailing metadata are upserted into this app’s models. Intermediate HTML or parse artifacts may land under `WORKSPACE_DIR` depending on pipeline settings.

### How content is published to GitHub

When enabled in settings, the tracker posts a **`repository_dispatch`** event to a configured GitHub repository (for downstream workflows). It does **not** bulk-upload Markdown corpora like the Boost GitHub activity pipeline.

### How vectors sync to Pinecone

**Not applicable** in this app today. If committee text should become searchable vectors, add a preprocessor and invoke [`cppa_pinecone_sync`](../cppa_pinecone_sync/README.md) following [docs/Pinecone_preprocess_guideline.md](../docs/Pinecone_preprocess_guideline.md).

## Common tasks

- Run tracker: `python manage.py run_wg21_paper_tracker --help`
- Import metadata from CSV: `python manage.py import_wg21_metadata_from_csv --help`

## Main command: `run_wg21_paper_tracker`

Runs the WG21 mailing scrape / DB pipeline and optional **`repository_dispatch`** to GitHub when enabled in settings.

| Option | Description |
| --- | --- |
| `--dry-run` | Log planned work only; no pipeline or dispatch. |
| `--from-date` | Lower bound mailing month `YYYY-MM` (inclusive backfill from that month). |
| `--to-date` | Upper bound `YYYY-MM`; with `--from-date` forms an inclusive range. |

## Package

- **Django app label:** `wg21_paper_tracker`
- **Path (from repo root):** `wg21_paper_tracker/`
- **Registration:** Listed under `INSTALLED_APPS` in [`config/settings.py`](../config/settings.py) as `wg21_paper_tracker`.

## Management commands

| Command | Description |
| --- | --- |
| `import_wg21_metadata_from_csv` | Import WG21 mailing, paper, and author metadata from CSV. |
| `run_wg21_paper_tracker` | Run WG21 paper tracker and optionally trigger GitHub repository_dispatch. |

Run `python manage.py <command> --help` for options.

## Tests

Typical invocation (from repo root, after [README prerequisites](../README.md#running-tests)):

```bash
python -m pytest wg21_paper_tracker/tests/ -v
```
